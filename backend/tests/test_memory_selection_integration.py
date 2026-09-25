"""Retrieval boundary tests; model and database doubles do not assert live quality."""

import json
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from backend.app.services.conversation_memory import (
    ConversationMemoryService,
    PrivacySettingsResponse,
)
from backend.app.services.embeddings import EmbeddingBatch
from backend.app.services.ai_job_contracts import AiJobCancelled
from backend.app.services.model_execution import (
    ModelExecutionContext,
    model_execution_scope,
)


def row(i):
    return SimpleNamespace(
        id=i,
        summary=f"独立历史{i}",
        session_id=10 + i,
        user_message_id=20 + i,
        assistant_message_id=30 + i,
        topic="队列",
        created_at=datetime.now(UTC),
    )


class SearchDb:
    def __init__(self):
        self.calls = []
        self.on_candidates = lambda: None

    def scalars(self, statement):
        self.calls.append(str(statement))
        if len(self.calls) % 2 == 0:
            self.on_candidates()
            return [row(1), row(2)]
        return [row(1)]


class Memory(ConversationMemoryService):
    state = PrivacySettingsResponse()

    def get_settings(self, user):
        return self.state.model_copy()

    def confirmed_context(self, user):
        return "已确认的偏好"

    def schedule_pair(self, **kwargs):
        return False


class Model:
    def __init__(
        self, raw='{"state":"matched","selected_ids":["c1"]}', effect=lambda: None
    ):
        self.raw, self.effect, self.calls = raw, effect, []

    def chat_completion_for_task(self, user, messages, profile):
        self.calls.append((messages, profile))
        self.effect()
        return self.raw


@pytest.fixture
def setup(monkeypatch):
    config = SimpleNamespace(
        conversation_memory_min_similarity=0.72,
        conversation_memory_semantic_selection_enabled=True,
    )
    monkeypatch.setattr(
        "backend.app.services.conversation_memory.get_settings", lambda: config
    )
    model, db = Model(), SearchDb()
    embedding = SimpleNamespace(
        embed_query=lambda *_: EmbeddingBatch(
            vectors=[[1, 0, 0]],
            source="synthetic",
            model="test",
            dimension=3,
            profile_hash="test",
            status="completed",
        )
    )
    memory = Memory(db, embedding, selection_model=model)
    return memory, model, db, config


def search(memory):
    return memory.search(
        user=SimpleNamespace(id=7), current_session_id=100, query="以前那道题"
    )


def test_disabled_flag_preserves_baseline_without_model_call(setup):
    memory, model, db, config = setup
    config.conversation_memory_semantic_selection_enabled = False
    result = search(memory)
    assert [r["memory_id"] for r in result] == ["1"]
    assert "selection_state" not in result[0]
    assert not model.calls and len(db.calls) == 1


@pytest.mark.parametrize(
    "raw,expected,state",
    [
        ('{"state":"matched","selected_ids":["c1"]}', ["2"], "matched"),
        ('{"state":"ambiguous","selected_ids":["c0","c1"]}', ["1", "2"], "ambiguous"),
        ('{"state":"none","selected_ids":[]}', [], None),
        ('{"state":"matched","selected_ids":["unknown"]}', ["1"], None),
        ("invalid", ["1"], None),
    ],
)
def test_selection_and_fallback_are_distinct(setup, raw, expected, state):
    memory, model, _, _ = setup
    model.raw = raw
    result = search(memory)
    assert [r["memory_id"] for r in result] == expected
    assert all(r.get("selection_state") == state for r in result)
    assert len(model.calls) == 1
    profile = model.calls[0][1]
    assert profile.timeout_seconds == 12 and profile.max_attempts == 1


@pytest.mark.parametrize("exception", [TimeoutError, RuntimeError])
def test_provider_failure_returns_only_threshold_baseline(setup, exception):
    memory, model, _, _ = setup

    def fail():
        raise exception("do not log private text")

    model.effect = fail
    assert [r["memory_id"] for r in search(memory)] == ["1"]


def test_missing_selector_uses_original_query(setup):
    memory, model, db, _ = setup
    memory.selection_model = None
    assert search(memory)
    assert not model.calls and len(db.calls) == 1


@pytest.mark.parametrize(
    "phase", ["embedding", "before_send", "after_return", "failed_call"]
)
@pytest.mark.parametrize("enabled", [True, False])
def test_privacy_revision_invalidates_results_at_each_boundary(setup, phase, enabled):
    memory, model, db, _ = setup

    def change():
        memory.state = PrivacySettingsResponse(
            conversation_memory_enabled=enabled, memory_revision=1
        )

    if phase == "embedding":
        old = memory.embedding_service.embed_query

        def embed(*args):
            value = old(*args)
            change()
            return value

        memory.embedding_service.embed_query = embed
    elif phase == "before_send":
        db.on_candidates = change
    else:

        def during_call():
            change()
            if phase == "failed_call":
                raise TimeoutError()

        model.effect = during_call
    assert search(memory) == []
    assert len(model.calls) == (1 if phase in {"after_return", "failed_call"} else 0)


@pytest.mark.parametrize("phase", ["before", "during", "after"])
def test_cancellation_is_not_fallback(setup, phase):
    memory, model, _, _ = setup
    cancelled = phase == "before"

    def check():
        if cancelled:
            raise AiJobCancelled()

    def effect():
        nonlocal cancelled
        if phase == "during":
            raise AiJobCancelled()
        cancelled = True

    model.effect = effect
    with model_execution_scope(ModelExecutionContext(cancel_check=check)):
        with pytest.raises(AiJobCancelled):
            search(memory)


def test_messages_are_bounded(setup):
    from backend.app.services.memory_selection import messages_for

    messages = messages_for("问" * 9000, [{"id": "c0", "summary": "答" * 9000}])
    payload = json.loads(messages[1]["content"])
    assert len(payload["question"]) == 4000
    assert len(payload["candidates"][0]["summary"]) == 1600


def test_context_discards_long_term_facts_when_selection_changes_revision(setup):
    from backend.tests.test_tutor_sessions import FakeTutorRepository, make_user
    from backend.app.services.tutor import TutorSessionService

    memory, model, _, _ = setup

    def change():
        memory.state = PrivacySettingsResponse(memory_revision=1)

    model.effect = change
    user = make_user(7)
    service = TutorSessionService(
        FakeTutorRepository(), conversation_memory_service=memory
    )
    session = service.create_session(
        user=user, scope="home", course_id=None, mode="chat", title="测试"
    )
    context = service._build_conversation_context(
        session, user=user, current_question="以前那道题"
    )
    assert "已确认" not in context.summary and not context.history_citations


def test_context_propagates_cancellation(setup):
    from backend.tests.test_tutor_sessions import FakeTutorRepository, make_user
    from backend.app.services.tutor import TutorSessionService

    memory, model, _, _ = setup

    def cancel():
        raise AiJobCancelled()

    model.effect = cancel
    user = make_user(7)
    service = TutorSessionService(
        FakeTutorRepository(), conversation_memory_service=memory
    )
    session = service.create_session(
        user=user, scope="home", course_id=None, mode="chat", title="测试"
    )
    with pytest.raises(AiJobCancelled):
        service._build_conversation_context(
            session, user=user, current_question="以前那道题"
        )


@pytest.mark.parametrize("streaming", [False, True])
@pytest.mark.parametrize("scope", ["home", "course"])
def test_http_graph_passes_only_selected_memory_to_answer(setup, streaming, scope):
    from fastapi.testclient import TestClient
    from backend.app.main import create_app
    from backend.app.api.v1.deps import get_current_user
    from backend.app.api.v1.tutor import get_tutor_session_service
    from backend.tests.test_tutor_sessions import (
        FakeTutorRepository,
        FakeCourseAnswerGenerator,
        make_user,
        FakeCourseCitationSearcher,
    )
    from backend.app.services.tutor import TutorSessionService

    memory, model, _, _ = setup
    user = make_user(7)
    repo = FakeTutorRepository(allowed_course_ids={1})
    generator = FakeCourseAnswerGenerator()
    service = TutorSessionService(
        repo,
        course_answer_generator=generator,
        conversation_memory_service=memory,
        course_citation_searcher=FakeCourseCitationSearcher(
            results=[
                {
                    "chunk_id": 1,
                    "course_id": 1,
                    "material_id": 1,
                    "knowledge_point_id": None,
                    "content": "启发式搜索使用启发函数估计剩余代价。",
                    "source_title": "测试讲义",
                    "page_number": 1,
                    "section_title": "启发式搜索",
                    "score": 9.5,
                }
            ]
        ),
    )
    session = service.create_session(
        user=user,
        scope=scope,
        course_id=1 if scope == "course" else None,
        mode="chat",
        title="验证",
    )
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_tutor_session_service] = lambda: service
    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/tutor/sessions/{session.id}/messages"
            + ("/stream" if streaming else ""),
            json={"message": "以前启发式搜索那道题怎么理解启发函数？"},
        )
    assert response.status_code == 200, response.text
    if streaming:
        assert (
            response.text.count("event: done") == 1
            and "event: error" not in response.text
        )
    assert len(model.calls) == 1
    context = generator.calls[0]["conversation_context"]
    assert [r["memory_id"] for r in context.history_citations] == ["2"]
    assert "独立历史2" in context.summary and "独立历史1" not in context.summary
    assert repo.messages[-1].role == "assistant"


@pytest.mark.parametrize("scope", ["home", "course"])
def test_stream_cancellation_never_generates_or_persists_answer(setup, scope):
    from backend.tests.test_tutor_sessions import (
        FakeTutorRepository,
        FakeCourseAnswerGenerator,
        make_user,
    )
    from backend.app.services.tutor import TutorSessionService

    memory, model, _, _ = setup

    def cancel():
        raise AiJobCancelled()

    model.effect = cancel
    user, repo, generator = (
        make_user(7),
        FakeTutorRepository(allowed_course_ids={1}),
        FakeCourseAnswerGenerator(),
    )
    service = TutorSessionService(
        repo, course_answer_generator=generator, conversation_memory_service=memory
    )
    session = service.create_session(
        user=user,
        scope=scope,
        course_id=1 if scope == "course" else None,
        mode="chat",
        title="验证",
    )
    events = list(
        service.stream_message(user=user, session_id=session.id, content="以前那道题")
    )
    assert [
        e["event"] for e in events if e["event"] in {"done", "error", "cancelled"}
    ] == ["cancelled"]
    assert not generator.calls
    assert all(m.role != "assistant" for m in repo.messages)


def test_long_question_skips_selection_without_silent_loss_of_tail(setup):
    memory, model, db, _ = setup
    result = memory.search(
        user=SimpleNamespace(id=7), current_session_id=100, query="问" * 4001
    )
    assert [r["memory_id"] for r in result] == ["1"]
    assert not model.calls and len(db.calls) == 1


def test_ambiguous_alternatives_survive_full_long_term_summary(setup):
    from backend.tests.test_tutor_sessions import FakeTutorRepository, make_user
    from backend.app.services.tutor import TutorSessionService

    memory, model, _, _ = setup
    memory.confirmed_context = lambda _: "偏好" * 600
    model.raw = '{"state":"ambiguous","selected_ids":["c0","c1"]}'
    user = make_user(7)
    service = TutorSessionService(
        FakeTutorRepository(), conversation_memory_service=memory
    )
    session = service.create_session(
        user=user, scope="home", course_id=None, mode="chat", title="验证"
    )
    context = service._build_conversation_context(
        session, user=user, current_question="以前那道题"
    )
    assert "先澄清" in context.summary
    assert "独立历史1" in context.summary and "独立历史2" in context.summary
    assert len(context.summary) <= 1500


def test_semantic_selection_defaults_on_and_allows_explicit_opt_out(monkeypatch):
    from backend.app.core.config import Settings

    monkeypatch.delenv("CONVERSATION_MEMORY_SEMANTIC_SELECTION_ENABLED", raising=False)
    assert Settings(_env_file=None).conversation_memory_semantic_selection_enabled is True
    monkeypatch.setenv("CONVERSATION_MEMORY_SEMANTIC_SELECTION_ENABLED", "false")
    assert Settings(_env_file=None).conversation_memory_semantic_selection_enabled is False

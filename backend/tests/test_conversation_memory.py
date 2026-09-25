from __future__ import annotations

from types import SimpleNamespace
from datetime import UTC, datetime

from backend.app.models import ConversationMemoryEntry
from backend.app.services.conversation_memory import ConversationMemoryService, PrivacySettingsResponse
from backend.app.services.embeddings import EmbeddingBatch


class FakeQueue:
    def __init__(self) -> None:
        self.calls: list[dict[str, int]] = []

    def enqueue(self, **ids: int) -> None:
        self.calls.append(ids)

    def enqueue_backfill(self, *, user_id: int) -> None:
        pass


class EnabledMemoryService(ConversationMemoryService):
    def get_settings(self, user):
        return PrivacySettingsResponse(conversation_memory_enabled=True, indexed_memory_count=0)


class FakeDb:
    def __init__(self, existing: ConversationMemoryEntry | None = None) -> None:
        self.existing = existing
        self.commits = 0

    def scalar(self, query):
        sql = str(query)
        if "FROM memory_suppressions" in sql:
            return None
        if "FROM chat_messages" in sql:
            return SimpleNamespace(created_at=datetime.now(UTC))
        return self.existing

    def add(self, _value) -> None:
        raise AssertionError("the migration test should update the existing entry")

    def commit(self) -> None:
        self.commits += 1


def test_new_memory_pair_is_scheduled_with_ids_instead_of_raw_text() -> None:
    queue = FakeQueue()
    service = EnabledMemoryService(SimpleNamespace(), queue=queue)

    scheduled = service.schedule_pair(
        user=SimpleNamespace(id=7),
        session=SimpleNamespace(id=11),
        user_message=SimpleNamespace(id=13, content="私人问题"),
        assistant_message=SimpleNamespace(id=14, content="私人回答"),
    )

    assert scheduled is True
    assert queue.calls == [{
        "user_id": 7,
        "session_id": 11,
        "user_message_id": 13,
        "assistant_message_id": 14,
        "expected_revision": 0,
    }]
    assert "私人问题" not in str(queue.calls)


def test_memory_summary_redacts_common_secrets() -> None:
    summary = ConversationMemoryService._safe_summary(
        "邮箱 me@example.com，手机号 13800138000",
        "api_key=secret-value",
    )

    assert "me@example.com" not in summary
    assert "13800138000" not in summary
    assert "secret-value" not in summary


def test_stale_memory_profile_is_reembedded_and_dimension_migrated(monkeypatch) -> None:
    monkeypatch.setattr("backend.app.services.conversation_memory.lock_memory_settings", lambda *_: SimpleNamespace(
        conversation_memory_enabled=True, memory_revision=0, memory_cleared_before=None))
    existing = ConversationMemoryEntry(
        user_id=7,
        session_id=11,
        user_message_id=13,
        assistant_message_id=14,
        summary="旧摘要",
        revision=1,
        embedding=[0.1, 0.2],
        embedding_provider="openai_compatible",
        embedding_model="old-embedding",
        embedding_dimension=2,
        embedding_profile_hash="old-profile",
    )
    db = FakeDb(existing)
    embedding = SimpleNamespace(
        embed_documents=lambda _user, _texts: EmbeddingBatch(
            vectors=[[0.5] * 2048],
            source="openai_compatible",
            model="text-embedding-v4",
            dimension=2048,
            status="completed",
            profile_hash="new-profile",
        )
    )
    service = EnabledMemoryService(db, embedding_service=embedding)

    migrated = service.index_pair(
        user=SimpleNamespace(id=7),
        session=SimpleNamespace(id=11, user_id=7),
        user_message=SimpleNamespace(id=13, session_id=11, role="user", content="新的问题"),
        assistant_message=SimpleNamespace(id=14, session_id=11, role="assistant", content="新的回答"),
    )

    assert migrated is True
    assert db.commits == 1
    assert existing.embedding_dimension == 2048
    assert len(existing.embedding) == 2048
    assert existing.embedding_model == "text-embedding-v4"
    assert existing.embedding_profile_hash == "new-profile"
    assert existing.summary == "旧摘要"


def test_first_message_retrieves_memory_and_confirmed_information():
    from backend.app.services.tutor_context import TutorContextMixin
    calls = []
    service = TutorContextMixin()
    service.repository = SimpleNamespace(list_messages=lambda _: [])
    service.conversation_memory_service = SimpleNamespace(
        confirmed_context=lambda _: "preference：先给例子",
        search=lambda **kwargs: calls.append(kwargs) or [{"snippet": "之前学过队列", "source_type": "history"}],
    )
    result = service._build_conversation_context(SimpleNamespace(id=11), user=SimpleNamespace(id=7), current_question="队列怎么用？")
    assert calls[0]["current_session_id"] == 11
    assert result.message_count == 0
    assert "先给例子" in result.summary and "之前学过队列" in result.summary
    assert "不是事实或评分依据" in result.summary


def test_stale_queued_job_and_mismatched_owner_do_not_embed():
    embedding = SimpleNamespace(embed_documents=lambda *_: (_ for _ in ()).throw(AssertionError("must not embed")))
    service = EnabledMemoryService(SimpleNamespace(), embedding_service=embedding)
    args = dict(user=SimpleNamespace(id=7), session=SimpleNamespace(id=11, user_id=99),
                user_message=SimpleNamespace(session_id=11, role="user"),
                assistant_message=SimpleNamespace(session_id=11, role="assistant"))
    assert service.index_pair(**args, expected_revision=1) is False
    assert service.index_pair(**args) is False


def test_confirmed_memory_requires_explicit_confirmation_and_bounds_content():
    import pytest
    from pydantic import ValidationError
    from backend.app.schemas.memory import ConfirmedMemoryRequest, MemoryCorrectionRequest
    for payload in ({"content": "目标", "category": "goal"},
                    {"content": "目标", "category": "goal", "confirmed": False},
                    {"content": " ", "category": "goal", "confirmed": True},
                    {"content": "x" * 501, "category": "goal", "confirmed": True}):
        with pytest.raises(ValidationError):
            ConfirmedMemoryRequest(**payload)
    with pytest.raises(ValidationError):
        MemoryCorrectionRequest(content="更正", revision=0, confirmed=True)

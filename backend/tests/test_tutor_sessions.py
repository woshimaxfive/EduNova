from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.app.api.v1.deps import get_auth_service
from backend.app.core.config import Settings
from backend.app.core.security import create_access_token
from backend.app.main import create_app
from backend.app.models import ChatMessage, ChatSession, Material, User
from backend.app.services.auth import AuthService
from backend.app.services.tutor import HomeTutorGraphRunner


NOW = datetime(2026, 7, 3, 16, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    "answer",
    [
        "抱歉，我无法记住之前的对话内容。",
        "很抱歉，我无法直接回忆或访问之前的对话内容。",
        "很抱歉，目前我没有获取到您之前学习的具体内容记录。",
    ],
)
def test_history_denial_is_rejected_when_context_is_available(answer: str) -> None:
    flags = HomeTutorGraphRunner._deterministic_risk_flags(
        question="还记得上面说过什么吗？",
        answer=answer,
        citations=[],
        history_available=True,
    )
    assert "history_denial" in flags


def load_tutor_module():
    try:
        return importlib.import_module("backend.app.services.tutor")
    except ModuleNotFoundError as exc:
        pytest.fail(f"缺少 tutor session 服务模块: {exc.name}")


def load_tutor_api_module():
    try:
        return importlib.import_module("backend.app.api.v1.tutor")
    except ModuleNotFoundError as exc:
        pytest.fail(f"缺少 tutor session API 模块: {exc.name}")


@dataclass
class FakeTutorRepository:
    sessions: list[ChatSession] = field(default_factory=list)
    messages: list[ChatMessage] = field(default_factory=list)
    agent_logs: list[Any] = field(default_factory=list)
    materials: list[Material] = field(default_factory=list)
    allowed_course_ids: set[int] = field(default_factory=set)
    course_titles: dict[int, str] = field(default_factory=dict)
    next_session_id: int = 1
    next_message_id: int = 1
    committed: bool = False
    rolled_back: bool = False

    def list_sessions(self, user_id: int, scope: str, course_id: int | None = None) -> list[ChatSession]:
        candidates = [
            session
            for session in self.sessions
            if session.user_id == user_id and session.scope == scope and not session.archived_from_home
        ]
        if course_id is not None:
            candidates = [session for session in candidates if session.course_id == course_id]
        return sorted(candidates, key=lambda session: session.updated_at, reverse=True)

    def get_session_for_user(self, session_id: int, user_id: int) -> ChatSession | None:
        return next(
            (
                session
                for session in self.sessions
                if session.id == session_id and session.user_id == user_id and not session.archived_from_home
            ),
            None,
        )

    def list_home_history(self, user_id: int, page: int, page_size: int, query: str) -> tuple[list[ChatSession], int]:
        candidates = [
            session
            for session in self.sessions
            if session.user_id == user_id and session.scope == "home" and not session.archived_from_home
        ]
        if query:
            normalized = query.casefold()
            candidates = [
                session
                for session in candidates
                if normalized in session.title.casefold()
                or any(normalized in message.content.casefold() for message in self.messages if message.session_id == session.id)
            ]
        candidates.sort(key=lambda session: (session.updated_at, session.id), reverse=True)
        start = (page - 1) * page_size
        return candidates[start : start + page_size], len(candidates)

    def find_history_match(self, session_id: int, query: str) -> str | None:
        return next(
            (
                message.content
                for message in reversed(self.list_messages(session_id))
                if query.casefold() in message.content.casefold()
            ),
            None,
        )

    def user_can_access_course(self, user_id: int, course_id: int) -> bool:
        return course_id in self.allowed_course_ids

    def get_course_for_user(self, user_id: int, course_id: int) -> SimpleNamespace | None:
        if not self.user_can_access_course(user_id, course_id):
            return None
        return SimpleNamespace(id=course_id, title=self.course_titles.get(course_id, ""))

    def list_messages(self, session_id: int) -> list[ChatMessage]:
        return sorted(
            [message for message in self.messages if message.session_id == session_id],
            key=lambda message: message.created_at,
        )

    def add_session(self, session: ChatSession) -> None:
        session.id = self.next_session_id
        self.next_session_id += 1
        session.created_at = NOW + timedelta(minutes=session.id)
        session.updated_at = session.created_at
        self.sessions.append(session)

    def add_message(self, message: ChatMessage) -> None:
        message.id = self.next_message_id
        self.next_message_id += 1
        message.created_at = NOW + timedelta(minutes=message.id)
        self.messages.append(message)

    def add_agent_log(self, log: Any) -> None:
        log.id = len(self.agent_logs) + 1
        log.created_at = NOW + timedelta(minutes=log.id)
        self.agent_logs.append(log)

    def list_home_materials_for_user(self, user_id: int, material_ids: list[int]) -> list[Material]:
        material_id_set = set(material_ids)
        return [
            material
            for material in self.materials
            if material.user_id == user_id and material.id in material_id_set and material.parse_status == "completed"
        ]

    def touch_session(self, session: ChatSession) -> None:
        session.updated_at = NOW + timedelta(minutes=self.next_message_id + 5)

    def flush(self) -> None:
        return None

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True


@dataclass
class FakeCourseCitationSearcher:
    results: list[dict[str, Any]] = field(default_factory=list)
    calls: list[dict[str, Any]] = field(default_factory=list)

    def search(self, user: User, course_id: int, query: str, top_k: int) -> SimpleNamespace:
        self.calls.append(
            {
                "user_id": user.id,
                "course_id": course_id,
                "query": query,
                "top_k": top_k,
            }
        )
        return SimpleNamespace(results=[SimpleNamespace(**item) for item in self.results])


@dataclass
class FakeMaterialCitationSearcher:
    citations: list[dict[str, Any]] = field(default_factory=list)
    retrieval_mode: str = "hybrid"
    embedding_status: str = "local_fallback"
    calls: list[dict[str, Any]] = field(default_factory=list)

    def search(self, user: User, material_ids: list[int], query: str, top_k: int) -> SimpleNamespace:
        self.calls.append(
            {
                "user_id": user.id,
                "material_ids": material_ids,
                "query": query,
                "top_k": top_k,
            }
        )
        return SimpleNamespace(
            citations=self.citations,
            retrieval_mode=self.retrieval_mode,
            embedding_status=self.embedding_status,
        )


@dataclass
class FakeCourseAnswerGenerator:
    content: str = "模型回答：启发式搜索要先理解启发函数，再练 A 星算法。"
    tokens: list[str] = field(default_factory=lambda: ["模型回答：", "启发式搜索要先理解启发函数。"])
    trace_id: str | None = "trace_model_test"
    should_raise: Exception | None = None
    calls: list[dict[str, Any]] = field(default_factory=list)
    review_status: str = "passed"
    review_risk_flags: list[str] = field(default_factory=list)
    review_safety_summary: str | None = None
    review_available: bool = True
    repair_content: str | None = None
    plan_calls: list[dict[str, Any]] = field(default_factory=list)
    review_calls: list[dict[str, Any]] = field(default_factory=list)
    repair_calls: list[dict[str, Any]] = field(default_factory=list)

    def generate(
        self,
        user: User,
        question: str,
        citations: list[dict[str, Any]],
        conversation_context: Any | None = None,
    ) -> SimpleNamespace:
        call: dict[str, Any] = {"user_id": user.id, "question": question, "citations": citations}
        if conversation_context is not None:
            call["conversation_context"] = conversation_context
        self.calls.append(call)
        if self.should_raise is not None:
            raise self.should_raise
        return SimpleNamespace(content=self.content, trace_id=self.trace_id)

    def generate_home(
        self,
        user: User,
        question: str,
        citations: list[dict[str, Any]] | None = None,
        use_web_search: bool = False,
        deep_thinking: bool = False,
        warnings: list[str] | None = None,
        conversation_context: Any | None = None,
        plan_summary: str | None = None,
    ) -> SimpleNamespace:
        call = {
            "user_id": user.id,
            "question": question,
            "citations": citations or [],
        }
        if conversation_context is not None:
            call["conversation_context"] = conversation_context
        if use_web_search or deep_thinking or citations or warnings:
            call.update(
                {
                    "use_web_search": use_web_search,
                    "deep_thinking": deep_thinking,
                    "warnings": warnings or [],
                }
            )
        self.calls.append(call)
        if self.should_raise is not None:
            raise self.should_raise
        return SimpleNamespace(content=self.content, trace_id=self.trace_id)

    def stream_home(
        self,
        user: User,
        question: str,
        citations: list[dict[str, Any]] | None = None,
        use_web_search: bool = False,
        deep_thinking: bool = False,
        warnings: list[str] | None = None,
        conversation_context: Any | None = None,
        plan_summary: str | None = None,
    ) -> SimpleNamespace:
        self.calls.append(
            {
                "user_id": user.id,
                "question": question,
                "citations": citations or [],
                "stream": True,
                "use_web_search": use_web_search,
                "deep_thinking": deep_thinking,
                "warnings": warnings or [],
                **({"conversation_context": conversation_context} if conversation_context is not None else {}),
            }
        )
        if self.should_raise is not None:
            raise self.should_raise
        return SimpleNamespace(tokens=iter(self.tokens), trace_id=self.trace_id, used_model=self.trace_id is not None)

    def plan_home(self, user: User, question: str, citations: list[dict[str, Any]]) -> str:
        self.plan_calls.append({"user_id": user.id, "question": question, "citation_count": len(citations)})
        return "目标：直接回答问题\n证据需求：使用可用来源\n回答结构：定义、解释、下一步"

    def review_home(
        self,
        user: User,
        question: str,
        answer: str,
        citations: list[dict[str, Any]],
        warnings: list[str] | None = None,
    ) -> SimpleNamespace:
        self.review_calls.append(
            {
                "user_id": user.id,
                "question": question,
                "answer": answer,
                "citation_count": len(citations),
                "warnings": warnings or [],
            }
        )
        if not self.review_available:
            return None
        return SimpleNamespace(
            review_status=self.review_status,
            confidence=0.9 if self.review_status == "passed" else 0.45,
            risk_flags=self.review_risk_flags,
            safety_summary=self.review_safety_summary
            or ("测试审核通过。" if self.review_status == "passed" else "测试审核要求修订。"),
        )

    def repair_home(
        self,
        user: User,
        question: str,
        draft: str,
        citations: list[dict[str, Any]],
        risk_flags: list[str],
    ) -> str:
        self.repair_calls.append(
            {
                "user_id": user.id,
                "question": question,
                "draft": draft,
                "citation_count": len(citations),
                "risk_flags": risk_flags,
            }
        )
        return self.repair_content if self.repair_content is not None else draft

    def stream(
        self,
        user: User,
        question: str,
        citations: list[dict[str, Any]],
        conversation_context: Any | None = None,
    ) -> SimpleNamespace:
        self.calls.append(
            {
                "user_id": user.id,
                "question": question,
                "citations": citations,
                "stream": True,
                **({"conversation_context": conversation_context} if conversation_context is not None else {}),
            }
        )
        if self.should_raise is not None:
            raise self.should_raise
        return SimpleNamespace(tokens=iter(self.tokens), trace_id=self.trace_id)


@dataclass
class FakeProfileEventRecorder:
    calls: list[dict[str, Any]] = field(default_factory=list)

    def ingest_course_question_signal(
        self,
        *,
        user: User,
        session: ChatSession,
        user_message: ChatMessage,
        message_text: str,
        citation_json: list[dict[str, Any]],
        trace_id: str | None,
        suggested_updates: dict[str, Any],
        suggested_confidence: dict[str, float],
    ) -> None:
        self.calls.append(
            {
                "user_id": user.id,
                "scope": session.scope,
                "course_id": session.course_id,
                "user_message_id": user_message.id,
                "message_text": message_text,
                "citation_count": len(citation_json),
                "trace_id": trace_id,
                "suggested_updates": suggested_updates,
                "suggested_confidence": suggested_confidence,
            }
        )

    def record_course_question_event(
        self,
        *,
        user: User,
        session: ChatSession,
        user_message: ChatMessage,
        assistant_message: ChatMessage,
        message_text: str,
        citation_json: list[dict[str, Any]],
        trace_id: str | None,
    ) -> None:
        self.calls.append(
            {
                "user_id": user.id,
                "scope": session.scope,
                "course_id": session.course_id,
                "user_message_id": user_message.id,
                "assistant_message_id": assistant_message.id,
                "message_text": message_text,
                "citation_count": len(citation_json),
                "trace_id": trace_id,
            }
        )


@dataclass
class TokenAuthRepository:
    user: User

    def get_user_by_id(self, user_id: int) -> User | None:
        return self.user if self.user.id == user_id else None


def make_user(user_id: int, display_name: str = "测试学生") -> User:
    return User(
        id=user_id,
        account=f"user{user_id}",
        hashed_password="not-used",
        display_name=display_name,
        role="student",
        starter_mode="blank",
    )


def add_history_message(repo: FakeTutorRepository, session: ChatSession, role: str, content: str) -> ChatMessage:
    message = ChatMessage(
        id=repo.next_message_id,
        session_id=session.id,
        user_id=session.user_id,
        role=role,
        content=content,
        citation_json=[],
        trace_id=None,
        created_at=NOW + timedelta(minutes=repo.next_message_id),
    )
    repo.next_message_id += 1
    repo.messages.append(message)
    return message


def make_home_material(material_id: int = 301, user_id: int = 1) -> Material:
    return Material(
        id=material_id,
        user_id=user_id,
        filename="主页复习资料.pdf",
        content_type="application/pdf",
        storage_path=f"user_{user_id}/home.pdf",
        parse_status="completed",
        extracted_text="主页资料提示：启发式搜索要结合 A* 和估价函数一起复习。",
        metadata_json={"size_label": "12 KB", "extension": "PDF"},
    )


@dataclass
class FakeWebSearchService:
    results: list[dict[str, Any]] = field(
        default_factory=lambda: [
            {
                "source_type": "web",
                "title": "A* search overview",
                "url": "https://example.com/a-star",
                "snippet": "A* search combines path cost and a heuristic estimate.",
            }
        ]
    )
    warning: str | None = None
    calls: list[dict[str, Any]] = field(default_factory=list)

    def search(self, query: str, max_results: int = 5) -> SimpleNamespace:
        self.calls.append({"query": query, "max_results": max_results})
        return SimpleNamespace(citations=self.results, warning=self.warning)


@dataclass
class FakeSemanticDecisionService:
    search_required: bool = False
    reasoning_mode: str = "auto"
    intent: str = "general_learning"
    search_query: str = ""
    course_related: bool = False
    profile_updates: dict[str, Any] = field(default_factory=dict)
    profile_confidence: dict[str, float] = field(default_factory=dict)
    calls: list[dict[str, Any]] = field(default_factory=list)
    evidence_calls: list[dict[str, Any]] = field(default_factory=list)

    def decide(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        forced_search = bool(kwargs.get("force_search"))
        forced_deep = bool(kwargs.get("force_deep"))
        return SimpleNamespace(
            search_required=self.search_required or forced_search,
            reasoning_mode="deep" if self.reasoning_mode == "deep" or forced_deep else "auto",
            reason_codes=("semantic_test",),
            reason_summary="模型语义测试决策。",
            intent=self.intent,
            search_query=self.search_query or kwargs["question"],
            confidence=0.92,
            decision_mode="model_forced" if forced_search or forced_deep else "model",
            course_related=self.course_related,
            profile_updates=self.profile_updates,
            profile_confidence=self.profile_confidence,
            warning=None,
        )

    def assess_course_evidence(self, **kwargs: Any) -> None:
        self.evidence_calls.append(kwargs)
        return None


def as_dict(value: Any) -> dict[str, Any]:
    return value.model_dump() if hasattr(value, "model_dump") else value


def make_token(user: User, settings: Settings) -> str:
    return create_access_token(str(user.id), settings=settings)


def test_tutor_sessions_route_requires_login() -> None:
    client = TestClient(create_app())

    response = client.get("/api/v1/tutor/sessions?scope=home")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_home_history_paginates_and_searches_titles_and_message_content() -> None:
    module = load_tutor_module()
    repo = FakeTutorRepository()
    user = make_user(1)
    for index in range(35):
        session = module.TutorSessionService(repo).create_session(
            user=user,
            scope="home",
            course_id=None,
            mode="chat",
            title=f"历史会话 {index:02d}",
        )
        if index == 2:
            add_history_message(repo, session, "user", "这里讨论了独特的链式法则关键词")
    repo.sessions[0].archived_from_home = True
    repo.sessions.append(
        ChatSession(
            id=99,
            user_id=2,
            scope="home",
            title="别人的链式法则会话",
            mode="chat",
            archived_from_home=False,
            selected_material_ids=[],
            created_at=NOW,
            updated_at=NOW,
        )
    )
    service = module.TutorSessionService(repo)

    first = service.list_home_history(user, page=1, page_size=30)
    second = service.list_home_history(user, page=2, page_size=30)
    searched = service.list_home_history(user, page=1, page_size=30, query="链式法则")

    assert first.total == 34
    assert len(first.items) == 30
    assert first.has_more is True
    assert len(second.items) == 4
    assert second.has_more is False
    assert searched.total == 1
    assert searched.items[0].match_snippet is not None
    assert "链式法则" in searched.items[0].match_snippet
    assert len(searched.items[0].match_snippet) <= 120


def test_home_session_persists_material_context_and_reuses_it_when_message_omits_ids() -> None:
    module = load_tutor_module()
    repo = FakeTutorRepository(materials=[make_home_material(301, 1)])
    searcher = FakeMaterialCitationSearcher(
        citations=[{"source_type": "material", "material_id": "301", "title": "主页复习资料.pdf", "snippet": "链式法则"}]
    )
    service = module.TutorSessionService(
        repo,
        material_citation_searcher=searcher,
        course_answer_generator=FakeCourseAnswerGenerator(),
    )
    user = make_user(1)
    session = service.create_session(user, "home", None, "chat", "资料会话", selected_material_ids=[301])

    detail = service.append_message(user, session.id, "继续讲解")
    cleared = service.update_session(user, session.id, selected_material_ids=[])

    assert detail.session.selected_material_ids == [301]
    assert searcher.calls[0]["material_ids"] == [301]
    assert cleared.selected_material_ids == []


def test_material_context_rejects_unavailable_materials_and_course_sessions() -> None:
    module = load_tutor_module()
    repo = FakeTutorRepository(materials=[make_home_material(301, 1)], allowed_course_ids={101})
    service = module.TutorSessionService(repo)
    user = make_user(1)

    with pytest.raises(module.InvalidMaterialContextError):
        service.create_session(user, "home", None, "chat", "无效资料", selected_material_ids=[999])
    with pytest.raises(module.InvalidMaterialContextError):
        service.create_session(user, "course", 101, "chat", "课程会话", selected_material_ids=[301])


def test_material_context_rejects_more_than_ten_distinct_materials() -> None:
    module = load_tutor_module()
    materials = [make_home_material(300 + index, 1) for index in range(1, 12)]
    service = module.TutorSessionService(FakeTutorRepository(materials=materials))

    with pytest.raises(module.InvalidMaterialContextError, match="最多选择 10 份"):
        service.create_session(make_user(1), "home", None, "chat", "资料太多", selected_material_ids=[item.id for item in materials])


def test_home_session_ignores_stale_material_context_with_safe_warning() -> None:
    module = load_tutor_module()
    repo = FakeTutorRepository(materials=[make_home_material(301, 1)])
    generator = FakeCourseAnswerGenerator()
    service = module.TutorSessionService(repo, course_answer_generator=generator)
    user = make_user(1)
    session = service.create_session(user, "home", None, "chat", "资料会话", selected_material_ids=[301])
    repo.materials.clear()

    service.append_message(user, session.id, "继续讲解")

    assert generator.calls[0]["warnings"] == ["部分历史参考资料已失效，已从本次检索中忽略。"]


def test_create_home_session_and_list_it_for_current_user() -> None:
    module = load_tutor_module()
    user = make_user(1)
    other = make_user(2)
    repo = FakeTutorRepository()
    service = module.TutorSessionService(repo)

    session = service.create_session(
        user=user,
        scope="home",
        course_id=None,
        mode="chat",
        title="神经网络反向传播怎么复习才能做题",
    )
    repo.sessions.append(
        ChatSession(
            id=99,
            user_id=other.id,
            course_id=None,
            scope="home",
            title="别人的历史",
            mode="chat",
            archived_from_home=False,
        )
    )
    repo.sessions[-1].created_at = NOW
    repo.sessions[-1].updated_at = NOW + timedelta(hours=1)

    listed = [as_dict(item) for item in service.list_sessions(user=user, scope="home")]

    assert session.id == 1
    assert session.user_id == user.id
    assert session.scope == "home"
    assert session.course_id is None
    assert session.mode == "chat"
    assert repo.committed is True
    assert [item["title"] for item in listed] == ["神经网络反向传播怎么复习才能做题"]


def test_create_course_session_requires_course_id_and_accessible_course() -> None:
    module = load_tutor_module()
    user = make_user(1)
    repo = FakeTutorRepository(allowed_course_ids={7})
    service = module.TutorSessionService(repo)

    with pytest.raises(module.InvalidSessionScopeError):
        service.create_session(user=user, scope="course", course_id=None, mode="chat", title="课程答疑")

    with pytest.raises(module.SessionNotFoundError):
        service.create_session(user=user, scope="course", course_id=8, mode="chat", title="越权课程")

    session = service.create_session(user=user, scope="course", course_id=7, mode="chat", title="课程答疑")

    assert session.scope == "course"
    assert session.course_id == 7


def test_rename_session_updates_title_for_current_user() -> None:
    module = load_tutor_module()
    user = make_user(1)
    repo = FakeTutorRepository()
    service = module.TutorSessionService(repo)
    session = service.create_session(user=user, scope="home", course_id=None, mode="chat", title="旧会话名")
    repo.committed = False

    renamed = as_dict(service.rename_session(user=user, session_id=session.id, title="  反向传播复习计划  "))

    assert renamed["id"] == str(session.id)
    assert renamed["title"] == "反向传播复习计划"
    assert repo.sessions[0].title == "反向传播复习计划"
    assert repo.committed is True


def test_rename_session_rejects_blank_title() -> None:
    module = load_tutor_module()
    user = make_user(1)
    repo = FakeTutorRepository()
    service = module.TutorSessionService(repo)
    session = service.create_session(user=user, scope="home", course_id=None, mode="chat", title="旧会话名")

    with pytest.raises(module.EmptyMessageError):
        service.rename_session(user=user, session_id=session.id, title="   ")


def test_delete_session_archives_and_hides_it_from_history() -> None:
    module = load_tutor_module()
    user = make_user(1)
    repo = FakeTutorRepository()
    service = module.TutorSessionService(repo)
    session = service.create_session(user=user, scope="home", course_id=None, mode="chat", title="要删除的会话")
    add_history_message(repo, session, "user", "这轮学习先做什么？")
    repo.committed = False

    deleted = as_dict(service.delete_session(user=user, session_id=session.id))

    assert deleted["id"] == str(session.id)
    assert deleted["archived_from_home"] is True
    assert repo.sessions[0].archived_from_home is True
    assert service.list_sessions(user=user, scope="home") == []
    with pytest.raises(module.SessionNotFoundError):
        service.get_session(user=user, session_id=session.id)
    assert repo.committed is True


def test_append_message_writes_user_and_model_assistant_messages_in_order() -> None:
    module = load_tutor_module()
    user = make_user(1)
    repo = FakeTutorRepository()
    answer_generator = FakeCourseAnswerGenerator(content="模型回答：先把目标拆成三步，再按资料和题型复习。")
    service = module.TutorSessionService(repo, course_answer_generator=answer_generator)
    session = service.create_session(user=user, scope="home", course_id=None, mode="chat", title="期末复习")

    detail = as_dict(service.append_message(user=user, session_id=session.id, content="为什么反向传播要用链式法则？"))

    assert [message["role"] for message in detail["messages"]] == ["user", "assistant"]
    assert detail["messages"][0]["content"] == "为什么反向传播要用链式法则？"
    assert detail["messages"][1]["content"] == "模型回答：先把目标拆成三步，再按资料和题型复习。"
    assert detail["messages"][1]["citation_json"] == []
    assert detail["messages"][1]["trace_id"].startswith("trace_")
    assert detail["messages"][1]["trace_id"] != "trace_model_test"
    assert answer_generator.calls == [{"user_id": 1, "question": "为什么反向传播要用链式法则？", "citations": []}]
    assert detail["session"]["updated_at"] > detail["session"]["created_at"]
    assert repo.committed is True


def test_append_home_message_passes_recent_session_context_to_model_and_safe_trace() -> None:
    module = load_tutor_module()
    user = make_user(1)
    repo = FakeTutorRepository()
    answer_generator = FakeCourseAnswerGenerator(content="模型回答：反向传播算梯度，梯度下降用梯度更新参数。")
    service = module.TutorSessionService(repo, course_answer_generator=answer_generator)
    session = service.create_session(user=user, scope="home", course_id=None, mode="chat", title="反向传播")
    add_history_message(repo, session, "user", "反向传播是什么？")
    add_history_message(repo, session, "assistant", "反向传播用链式法则计算各层梯度。")

    service.append_message(user=user, session_id=session.id, content="那它和梯度下降什么关系？")

    context = answer_generator.calls[0]["conversation_context"]
    assert context.message_count == 2
    assert context.summary_used is False
    assert context.messages == [
        {"role": "user", "content": "反向传播是什么？"},
        {"role": "assistant", "content": "反向传播用链式法则计算各层梯度。"},
    ]
    assert repo.agent_logs[0].metadata_json["context_message_count"] == 2
    assert repo.agent_logs[0].metadata_json["context_summary_used"] is False
    assert repo.agent_logs[0].metadata_json["retrieval_query_mode"] == "direct"
    assert "反向传播是什么" not in str(repo.agent_logs[0].metadata_json)


def test_append_home_message_summarizes_and_truncates_long_history_without_sensitive_markers() -> None:
    module = load_tutor_module()
    user = make_user(1)
    repo = FakeTutorRepository()
    answer_generator = FakeCourseAnswerGenerator(content="模型回答：我会参考前文，但不暴露隐私。")
    service = module.TutorSessionService(repo, course_answer_generator=answer_generator)
    session = service.create_session(user=user, scope="home", course_id=None, mode="chat", title="长对话")
    long_text = "系统提示词 SECRET API Key 完整资料原文 " + ("反向传播和梯度下降的关系 " * 80)
    for index in range(10):
        add_history_message(repo, session, "user", f"第 {index} 个问题：" + long_text)
        add_history_message(repo, session, "assistant", f"第 {index} 个回答：" + long_text)

    service.append_message(user=user, session_id=session.id, content="继续总结一下。")

    context = answer_generator.calls[0]["conversation_context"]
    total_chars = len(context.summary) + sum(len(message["content"]) for message in context.messages)
    assert context.summary_used is True
    assert context.message_count <= 12
    assert len(context.summary) <= 1500
    assert total_chars <= 6000
    assert all(len(message["content"]) <= 1200 for message in context.messages)
    serialized_context = f"{context.summary} {context.messages}"
    assert "SECRET" not in serialized_context
    assert "API Key" not in serialized_context
    assert "系统提示词" not in serialized_context
    assert "完整资料原文" not in serialized_context
    assert repo.agent_logs[0].metadata_json["context_summary_used"] is True


def test_append_course_message_persists_real_citations_from_course_knowledge() -> None:
    module = load_tutor_module()
    user = make_user(1)
    repo = FakeTutorRepository(allowed_course_ids={7})
    citation_searcher = FakeCourseCitationSearcher(
        results=[
            {
                "chunk_id": 501,
                "course_id": 7,
                "material_id": 301,
                "knowledge_point_id": 401,
                "content": "启发式搜索利用启发函数估计路径代价。",
                "source_title": "人工智能导论讲义.md",
                "page_number": None,
                "section_title": "启发式搜索",
                "score": 9.5,
            }
        ]
    )
    answer_generator = FakeCourseAnswerGenerator()
    service = module.TutorSessionService(
        repo,
        course_citation_searcher=citation_searcher,
        course_answer_generator=answer_generator,
    )
    session = service.create_session(user=user, scope="course", course_id=7, mode="chat", title="课程答疑")

    detail = as_dict(service.append_message(user=user, session_id=session.id, content="启发式搜索怎么复习？"))

    assert citation_searcher.calls == [
        {
            "user_id": 1,
            "course_id": 7,
            "query": "启发式搜索怎么复习？",
            "top_k": 5,
        }
    ]
    assert answer_generator.calls == [
        {
            "user_id": 1,
            "question": "启发式搜索怎么复习？",
            "citations": [
                {
                    "chunk_id": 501,
                    "course_id": 7,
                    "material_id": 301,
                    "knowledge_point_id": 401,
                    "content": "启发式搜索利用启发函数估计路径代价。",
                    "source_title": "人工智能导论讲义.md",
                    "page_number": None,
                    "section_title": "启发式搜索",
                    "score": 9.5,
                }
            ],
        }
    ]
    assert [message["role"] for message in detail["messages"]] == ["user", "assistant"]
    assert detail["messages"][1]["content"] == "模型回答：启发式搜索要先理解启发函数，再练 A 星算法。"
    assert detail["messages"][1]["citation_json"][0]["chunk_id"] == 501
    assert detail["messages"][1]["citation_json"][0]["source_title"] == "人工智能导论讲义.md"
    assert detail["messages"][1]["trace_id"] == "trace_model_test"
    assert [log.agent_name for log in repo.agent_logs] == [
        "profile",
        "route",
        "retriever",
        "web_search",
        "planner",
        "tutor",
        "weakness",
        "review",
        "next_action",
    ]
    assert {log.trace_id for log in repo.agent_logs} == {"trace_model_test"}
    assert repo.agent_logs[0].metadata_json["workflow"] == "course_tutor"
    assert repo.agent_logs[0].metadata_json["artifact_type"] == "chat_message"
    assert repo.agent_logs[0].metadata_json["artifact_id"] == str(repo.messages[1].id)
    assert repo.agent_logs[2].metadata_json["citation_count"] == 1
    assert repo.agent_logs[7].metadata_json["review_status"] == "passed"


def test_append_course_message_uses_recent_user_questions_for_retrieval_and_model_context() -> None:
    module = load_tutor_module()
    user = make_user(1)
    repo = FakeTutorRepository(allowed_course_ids={7})
    citation_searcher = FakeCourseCitationSearcher(
        results=[
            {
                "chunk_id": 501,
                "course_id": 7,
                "material_id": 301,
                "knowledge_point_id": 401,
                "content": "A 星算法用估价函数选择更可能接近目标的节点。",
                "source_title": "人工智能导论讲义.md",
                "page_number": None,
                "section_title": "启发式搜索",
                "score": 9.5,
            }
        ]
    )
    answer_generator = FakeCourseAnswerGenerator()
    service = module.TutorSessionService(
        repo,
        course_citation_searcher=citation_searcher,
        course_answer_generator=answer_generator,
    )
    session = service.create_session(user=user, scope="course", course_id=7, mode="chat", title="课程答疑")
    add_history_message(repo, session, "user", "启发式搜索是什么？")
    add_history_message(repo, session, "assistant", "它用启发函数估计搜索方向。")
    add_history_message(repo, session, "user", "A 星算法为什么要估价函数？")
    add_history_message(repo, session, "assistant", "估价函数帮助排序待扩展节点。")

    service.append_message(user=user, session_id=session.id, content="这个怎么做题？")

    assert citation_searcher.calls[0]["query"] == "启发式搜索是什么？\nA 星算法为什么要估价函数？\n这个怎么做题？"
    context = answer_generator.calls[0]["conversation_context"]
    assert context.message_count == 4
    assert context.messages[-2:] == [
        {"role": "user", "content": "A 星算法为什么要估价函数？"},
        {"role": "assistant", "content": "估价函数帮助排序待扩展节点。"},
    ]
    assert repo.agent_logs[0].metadata_json["context_message_count"] == 4
    assert repo.agent_logs[0].metadata_json["retrieval_query_mode"] == "contextual"
    assert "A 星算法为什么" not in str(repo.agent_logs[0].metadata_json)


def test_append_course_message_does_not_pollute_retrieval_after_topic_switch() -> None:
    module = load_tutor_module()
    user = make_user(1)
    repo = FakeTutorRepository(allowed_course_ids={7})
    citation_searcher = FakeCourseCitationSearcher(results=[])
    service = module.TutorSessionService(
        repo,
        course_citation_searcher=citation_searcher,
        course_answer_generator=FakeCourseAnswerGenerator(),
    )
    session = service.create_session(user=user, scope="course", course_id=7, mode="chat", title="课程答疑")
    add_history_message(repo, session, "user", "A 星算法为什么要估价函数？")
    add_history_message(repo, session, "assistant", "估价函数帮助排序待扩展节点。")

    service.append_message(user=user, session_id=session.id, content="反向传播中的链式法则怎么计算？")

    assert citation_searcher.calls[0]["query"] == "反向传播中的链式法则怎么计算？"
    assert repo.agent_logs[0].metadata_json["retrieval_query_mode"] == "direct"


def test_append_course_message_does_not_treat_a_normal_why_question_as_profile_evidence() -> None:
    module = load_tutor_module()
    user = make_user(1)
    repo = FakeTutorRepository(allowed_course_ids={7})
    profile_recorder = FakeProfileEventRecorder()
    service = module.TutorSessionService(
        repo,
        course_citation_searcher=FakeCourseCitationSearcher(
            results=[
                {
                    "chunk_id": 501,
                    "course_id": 7,
                    "material_id": 301,
                    "knowledge_point_id": 401,
                    "content": "启发式搜索利用启发函数估计路径代价。",
                    "source_title": "人工智能导论讲义.md",
                    "page_number": None,
                    "section_title": "启发式搜索",
                    "score": 9.5,
                }
            ]
        ),
        course_answer_generator=FakeCourseAnswerGenerator(),
        profile_event_recorder=profile_recorder,
    )
    session = service.create_session(user=user, scope="course", course_id=7, mode="chat", title="课程答疑")

    service.append_message(user=user, session_id=session.id, content="为什么启发式搜索这么难？")

    assert profile_recorder.calls == []


def test_append_course_message_records_insufficient_evidence_without_fabricated_citations() -> None:
    module = load_tutor_module()
    user = make_user(1)
    repo = FakeTutorRepository(allowed_course_ids={7})
    answer_generator = FakeCourseAnswerGenerator()
    service = module.TutorSessionService(
        repo,
        course_citation_searcher=FakeCourseCitationSearcher(results=[]),
        course_answer_generator=answer_generator,
    )
    session = service.create_session(user=user, scope="course", course_id=7, mode="chat", title="课程答疑")

    detail = as_dict(service.append_message(user=user, session_id=session.id, content="量子通信怎么复习？"))

    assert answer_generator.calls == []
    assert "还没有足够依据" in detail["messages"][1]["content"]
    assert detail["messages"][1]["citation_json"] == []


def test_course_message_automatically_uses_external_supplement_without_profile_evidence() -> None:
    module = load_tutor_module()
    user = make_user(1)
    repo = FakeTutorRepository(allowed_course_ids={7}, course_titles={7: "数据结构与算法"})
    web_searcher = FakeWebSearchService()
    profile_recorder = FakeProfileEventRecorder()
    answer_generator = FakeCourseAnswerGenerator(content="模型回答：这是课程主题的最新外部补充。")
    service = module.TutorSessionService(
        repo,
        course_citation_searcher=FakeCourseCitationSearcher(results=[]),
        course_answer_generator=answer_generator,
        web_search_service=web_searcher,
        profile_event_recorder=profile_recorder,
        semantic_decision_service=FakeSemanticDecisionService(course_related=True, intent="material_question"),
    )
    session = service.create_session(user=user, scope="course", course_id=7, mode="chat", title="课程答疑")

    detail = as_dict(service.append_message(user=user, session_id=session.id, content="数据结构有哪些应用？"))

    assistant = detail["messages"][1]
    assert web_searcher.calls == [{"query": "数据结构有哪些应用？", "max_results": 5}]
    assert assistant["citation_json"][0]["source_type"] == "web"
    assert assistant["citation_json"][0]["evidence_role"] == "external_supplement"
    assert profile_recorder.calls == []
    assert repo.agent_logs[3].metadata_json["course_citation_count"] == 0
    assert repo.agent_logs[3].metadata_json["web_citation_count"] == 1
    assert "course_evidence_gap" in repo.agent_logs[3].metadata_json["tool_reason_codes"]


def test_course_message_reuses_semantic_route_when_stable_course_evidence_is_already_sufficient() -> None:
    module = load_tutor_module()
    user = make_user(1)
    repo = FakeTutorRepository(allowed_course_ids={7}, course_titles={7: "数据结构与算法"})
    semantic = FakeSemanticDecisionService(course_related=True, intent="material_question")
    service = module.TutorSessionService(
        repo,
        course_citation_searcher=FakeCourseCitationSearcher(results=[{
            "chunk_id": 501,
            "course_id": 7,
            "material_id": 301,
            "knowledge_point_id": 401,
            "content": "二叉树遍历按照根结点访问时机分为前序、中序和后序。",
            "source_title": "数据结构讲义.md",
            "page_number": 8,
            "section_title": "二叉树遍历",
            "score": 9.5,
        }]),
        course_answer_generator=FakeCourseAnswerGenerator(),
        semantic_decision_service=semantic,
    )
    session = service.create_session(user=user, scope="course", course_id=7, mode="chat", title="课程答疑")

    service.append_message(user=user, session_id=session.id, content="解释二叉树的三种遍历")

    assert semantic.evidence_calls == []
    assert repo.agent_logs[3].status == "skipped"
    assert "无需联网补充" in repo.agent_logs[3].output_summary


def test_home_message_automatically_searches_fresh_information_without_legacy_flags() -> None:
    module = load_tutor_module()
    user = make_user(1)
    repo = FakeTutorRepository()
    web_searcher = FakeWebSearchService()
    answer_generator = FakeCourseAnswerGenerator(content="模型回答：这是核实后的最新信息。")
    service = module.TutorSessionService(
        repo,
        course_answer_generator=answer_generator,
        web_search_service=web_searcher,
    )
    session = service.create_session(user=user, scope="home", course_id=None, mode="chat", title="主页答疑")

    service.append_message(user=user, session_id=session.id, content="请核实这个算法今年的最新应用")

    assert web_searcher.calls == [{"query": "请核实这个算法今年的最新应用", "max_results": 5}]
    assert answer_generator.calls[0]["use_web_search"] is True
    assert repo.agent_logs[1].metadata_json["search_required"] is True
    assert "explicit_search" in repo.agent_logs[1].metadata_json["tool_reason_codes"]


def test_append_home_message_uses_model_reply_but_does_not_call_course_searcher() -> None:
    module = load_tutor_module()
    user = make_user(1)
    repo = FakeTutorRepository(allowed_course_ids={7})
    citation_searcher = FakeCourseCitationSearcher(
        results=[
            {
                "chunk_id": 501,
                "course_id": 7,
                "material_id": 301,
                "knowledge_point_id": 401,
                "content": "不应该用于主页会话。",
                "source_title": "课程资料.md",
                "page_number": None,
                "section_title": "课程切片",
                "score": 9.5,
            }
        ]
    )
    answer_generator = FakeCourseAnswerGenerator()
    service = module.TutorSessionService(
        repo,
        course_citation_searcher=citation_searcher,
        course_answer_generator=answer_generator,
    )
    session = service.create_session(user=user, scope="home", course_id=None, mode="chat", title="主页答疑")

    detail = as_dict(service.append_message(user=user, session_id=session.id, content="主页怎么复习？"))

    assert citation_searcher.calls == []
    assert answer_generator.calls == [
        {
            "user_id": 1,
            "question": "主页怎么复习？",
            "citations": [],
        }
    ]
    assert detail["messages"][1]["content"] == "模型回答：启发式搜索要先理解启发函数，再练 A 星算法。"
    assert detail["messages"][1]["citation_json"] == []
    assert detail["messages"][1]["trace_id"].startswith("trace_")
    assert detail["messages"][1]["trace_id"] != "trace_model_test"


def test_append_home_message_with_tools_persists_material_web_citations_and_trace() -> None:
    module = load_tutor_module()
    user = make_user(1)
    repo = FakeTutorRepository(materials=[make_home_material()])
    web_searcher = FakeWebSearchService()
    material_searcher = FakeMaterialCitationSearcher(
        citations=[
            {
                "source_type": "material",
                "material_id": "301",
                "title": "主页复习资料.pdf",
                "section_title": "启发式搜索",
                "page_number": 3,
                "snippet": "主页资料提示：启发式搜索要结合 A* 和估价函数一起复习。",
                "score": 8.75,
                "retrieval_source": "hybrid",
                "embedding_status": "local_fallback",
            }
        ]
    )
    answer_generator = FakeCourseAnswerGenerator(content="模型回答：先看 A* 的估价函数，再做三道搜索题。")
    service = module.TutorSessionService(
        repo,
        course_answer_generator=answer_generator,
        web_search_service=web_searcher,
        material_citation_searcher=material_searcher,
    )
    session = service.create_session(user=user, scope="home", course_id=None, mode="chat", title="主页答疑")

    detail = as_dict(
        service.append_message(
            user=user,
            session_id=session.id,
            content="启发式搜索怎么复习？",
            use_web_search=True,
            deep_thinking=True,
            selected_material_ids=[301],
        )
    )

    assert web_searcher.calls == [{"query": "启发式搜索怎么复习？", "max_results": 5}]
    assert answer_generator.calls == [
        {
            "user_id": 1,
            "question": "启发式搜索怎么复习？",
            "citations": [
                {
                    "source_type": "material",
                    "material_id": "301",
                    "title": "主页复习资料.pdf",
                    "section_title": "启发式搜索",
                    "page_number": 3,
                    "snippet": "主页资料提示：启发式搜索要结合 A* 和估价函数一起复习。",
                    "score": 8.75,
                    "retrieval_source": "hybrid",
                    "embedding_status": "local_fallback",
                },
                {
                    "source_type": "web",
                    "title": "A* search overview",
                    "url": "https://example.com/a-star",
                    "snippet": "A* search combines path cost and a heuristic estimate.",
                    "access_scope": "global_source",
                },
            ],
            "use_web_search": True,
            "deep_thinking": True,
            "warnings": [],
        }
    ]
    assistant = detail["messages"][1]
    assert assistant["citation_json"][0]["source_type"] == "material"
    assert assistant["citation_json"][1]["source_type"] == "web"
    assert assistant["trace_id"].startswith("trace_")
    assert assistant["trace_id"] != "trace_model_test"
    assert material_searcher.calls == [
        {
            "user_id": 1,
            "material_ids": [301],
            "query": "启发式搜索怎么复习？",
            "top_k": 5,
        }
    ]
    assert [log.agent_name for log in repo.agent_logs] == [
        "context",
        "route",
        "material_retriever",
        "web_search",
        "planner",
        "answer",
        "review",
        "persist",
    ]
    assert repo.agent_logs[0].metadata_json["workflow"] == "home_tutor"
    assert repo.agent_logs[2].metadata_json["source_count"] == 1
    assert repo.agent_logs[2].metadata_json["retrieval_mode"] == "hybrid"
    assert repo.agent_logs[2].metadata_json["embedding_status"] == "local_fallback"
    assert repo.agent_logs[3].metadata_json["source_count"] == 2
    assert repo.agent_logs[6].metadata_json["review_status"] == "passed"


def test_append_home_message_uses_contextual_query_for_web_search() -> None:
    module = load_tutor_module()
    user = make_user(1)
    repo = FakeTutorRepository()
    web_searcher = FakeWebSearchService()
    answer_generator = FakeCourseAnswerGenerator(content="模型回答：结合上一问继续解释。")
    service = module.TutorSessionService(
        repo,
        course_answer_generator=answer_generator,
        web_search_service=web_searcher,
    )
    session = service.create_session(user=user, scope="home", course_id=None, mode="chat", title="主页答疑")
    add_history_message(repo, session, "user", "A 星算法为什么要估价函数？")
    add_history_message(repo, session, "assistant", "估价函数帮助排序待扩展节点。")

    service.append_message(user=user, session_id=session.id, content="这个有没有最新例子？", use_web_search=True)

    assert web_searcher.calls == [{"query": "A 星算法为什么要估价函数？\n这个有没有最新例子？", "max_results": 5}]
    assert answer_generator.calls[0]["conversation_context"].message_count == 2
    assert repo.agent_logs[0].metadata_json["retrieval_query_mode"] == "contextual"


def test_append_home_message_does_not_record_profile_candidate_event() -> None:
    module = load_tutor_module()
    user = make_user(1)
    repo = FakeTutorRepository()
    profile_recorder = FakeProfileEventRecorder()
    service = module.TutorSessionService(
        repo,
        course_answer_generator=FakeCourseAnswerGenerator(),
        profile_event_recorder=profile_recorder,
    )
    session = service.create_session(user=user, scope="home", course_id=None, mode="chat", title="主页答疑")

    service.append_message(user=user, session_id=session.id, content="为什么我不会反向传播？")

    assert profile_recorder.calls == []


def test_home_graph_repairs_prompt_echo_once_and_persists_only_reviewed_answer() -> None:
    module = load_tutor_module()
    user = make_user(1)
    repo = FakeTutorRepository()
    answer_generator = FakeCourseAnswerGenerator(
        content=(
            "学生问题：什么是机器学习？ 工具状态：联网未配置 "
            "可用来源摘要：资料开头 工具提示：无。"
        ),
        repair_content="## 机器学习\n\n机器学习让系统从数据中归纳规律，并用新数据检验规律。",
    )
    service = module.TutorSessionService(repo, course_answer_generator=answer_generator)
    session = service.create_session(user=user, scope="home", course_id=None, mode="chat", title="机器学习")

    detail = as_dict(service.append_message(user=user, session_id=session.id, content="什么是机器学习？"))

    assistant = detail["messages"][1]
    assert assistant["content"].startswith("## 机器学习")
    assert "工具状态" not in assistant["content"]
    assert len(answer_generator.repair_calls) == 1
    assert answer_generator.repair_calls[0]["risk_flags"] == ["prompt_echo"]
    assert len(answer_generator.review_calls) == 2
    assert [log.agent_name for log in repo.agent_logs] == [
        "context",
        "route",
        "material_retriever",
        "web_search",
        "planner",
        "answer",
        "review",
        "repair",
        "review",
        "persist",
    ]
    assert [log.step_index for log in repo.agent_logs] == [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    assert repo.agent_logs[6].metadata_json["review_status"] == "revise"
    assert repo.agent_logs[8].metadata_json["review_status"] == "passed"


def test_home_graph_marks_unavailable_model_review_as_warning_instead_of_passed() -> None:
    module = load_tutor_module()
    user = make_user(1)
    repo = FakeTutorRepository()
    answer_generator = FakeCourseAnswerGenerator(
        content="## 梯度下降\n\n梯度下降沿损失函数下降方向更新参数。",
        review_available=False,
    )
    service = module.TutorSessionService(repo, course_answer_generator=answer_generator)
    session = service.create_session(user=user, scope="home", course_id=None, mode="chat", title="梯度下降")

    detail = as_dict(service.append_message(user=user, session_id=session.id, content="什么是梯度下降？"))

    assert detail["messages"][1]["content"].startswith("## 梯度下降")
    assert answer_generator.repair_calls == []
    assert repo.agent_logs[6].status == "warning"
    assert repo.agent_logs[6].metadata_json["review_status"] == "warning"
    assert "模型审核结论不可用" in repo.agent_logs[6].metadata_json["safety_summary"]


def test_home_graph_does_not_reject_answer_when_model_review_flag_conflicts_with_positive_summary() -> None:
    module = load_tutor_module()
    user = make_user(1)
    repo = FakeTutorRepository()
    answer_generator = FakeCourseAnswerGenerator(
        content="## 机器学习\n\n机器学习从数据中归纳规律，并用新数据检验泛化能力。",
        review_status="revise",
        review_risk_flags=["off_topic"],
        review_safety_summary="回答全面、准确且直接解释了机器学习。",
    )
    service = module.TutorSessionService(repo, course_answer_generator=answer_generator)
    session = service.create_session(user=user, scope="home", course_id=None, mode="chat", title="机器学习")

    detail = as_dict(service.append_message(user=user, session_id=session.id, content="什么是机器学习？"))

    assert detail["messages"][1]["content"].startswith("## 机器学习")
    assert answer_generator.repair_calls == []
    assert repo.agent_logs[6].status == "warning"
    assert repo.agent_logs[6].metadata_json["review_status"] == "warning"
    assert repo.agent_logs[6].metadata_json["risk_flags"] == []


def test_home_graph_chinese_relevance_check_accepts_paraphrased_comparison_and_rejects_unrelated_answer() -> None:
    module = load_tutor_module()
    relevant_answer = (
        "监督学习使用带标签的数据训练模型，适合分类和回归；无监督学习处理没有标签的数据，"
        "更常用于聚类、降维和结构发现。两者最关键的区别是训练数据是否提供目标标签，"
        "因此评估方法和典型任务也不同。做题时可以先看数据有没有标签，再判断题目属于哪一种学习范式。"
        "例如预测房价属于监督学习，因为训练样本带有真实房价；把用户按行为自动分群通常属于无监督学习，"
        "因为系统需要从没有预设类别的数据中发现结构。实际项目也可能先用无监督学习探索数据，再用监督学习完成预测。"
    )
    unrelated_answer = "启发式搜索通过估价函数选择节点。" * 20

    assert len(relevant_answer) > 180
    relevant_flags = module.HomeTutorGraphRunner._deterministic_risk_flags(
        question="那监督学习和无监督学习有什么区别？",
        answer=relevant_answer,
        citations=[],
    )
    unrelated_flags = module.HomeTutorGraphRunner._deterministic_risk_flags(
        question="量子通信的基本原理是什么？",
        answer=unrelated_answer,
        citations=[],
    )

    assert "off_topic" not in relevant_flags
    assert "off_topic" in unrelated_flags


def test_home_graph_review_summary_does_not_treat_negated_risk_as_support() -> None:
    module = load_tutor_module()

    assert module.HomeTutorGraphRunner._review_summary_supports_flag("回答没有回显内部输入。", "prompt_echo") is False
    assert module.HomeTutorGraphRunner._review_summary_supports_flag("回答没有敏感信息或隐私内容。", "sensitive_output") is False
    assert module.HomeTutorGraphRunner._review_summary_supports_flag("回答泄露了系统提示词。", "sensitive_output") is True


def test_append_home_message_without_model_config_saves_clear_prompt() -> None:
    module = load_tutor_module()
    user = make_user(1)
    repo = FakeTutorRepository()
    service = module.TutorSessionService(repo)
    session = service.create_session(user=user, scope="home", course_id=None, mode="chat", title="主页答疑")

    detail = as_dict(service.append_message(user=user, session_id=session.id, content="主页怎么复习？"))

    assert "当前未配置可用模型" in detail["messages"][1]["content"]
    assert detail["messages"][1]["citation_json"] == []
    assert detail["messages"][1]["trace_id"].startswith("trace_")
    assert [log.agent_name for log in repo.agent_logs] == [
        "context",
        "route",
        "material_retriever",
        "web_search",
        "planner",
        "answer",
        "review",
        "persist",
    ]
    assert repo.agent_logs[5].status == "warning"
    assert repo.agent_logs[6].metadata_json["review_status"] == "warning"


def test_append_home_message_model_failure_does_not_persist_half_messages() -> None:
    module = load_tutor_module()
    answer_module = importlib.import_module("backend.app.services.course_answers")
    user = make_user(1)
    repo = FakeTutorRepository()
    answer_generator = FakeCourseAnswerGenerator(
        should_raise=answer_module.CourseAnswerGenerationError("模型暂不可用，请检查设置或稍后重试。")
    )
    service = module.TutorSessionService(repo, course_answer_generator=answer_generator)
    session = service.create_session(user=user, scope="home", course_id=None, mode="chat", title="主页答疑")

    with pytest.raises(answer_module.CourseAnswerGenerationError):
        service.append_message(user=user, session_id=session.id, content="主页怎么复习？")

    assert repo.messages == []
    assert repo.rolled_back is False


def test_append_course_message_with_citations_and_missing_model_config_saves_clear_prompt() -> None:
    module = load_tutor_module()
    user = make_user(1)
    repo = FakeTutorRepository(allowed_course_ids={7})
    citation_searcher = FakeCourseCitationSearcher(
        results=[
            {
                "chunk_id": 501,
                "course_id": 7,
                "material_id": 301,
                "knowledge_point_id": 401,
                "content": "启发式搜索利用启发函数估计路径代价。",
                "source_title": "人工智能导论讲义.md",
                "page_number": None,
                "section_title": "启发式搜索",
                "score": 9.5,
            }
        ]
    )
    answer_generator = FakeCourseAnswerGenerator(content="已找到资料依据，但当前未配置可用模型。", trace_id=None)
    service = module.TutorSessionService(
        repo,
        course_citation_searcher=citation_searcher,
        course_answer_generator=answer_generator,
    )
    session = service.create_session(user=user, scope="course", course_id=7, mode="chat", title="课程答疑")

    detail = as_dict(service.append_message(user=user, session_id=session.id, content="启发式搜索怎么复习？"))

    assert "当前未配置可用模型" in detail["messages"][1]["content"]
    assert detail["messages"][1]["citation_json"][0]["chunk_id"] == 501
    assert detail["messages"][1]["trace_id"].startswith("trace_")
    assert repo.agent_logs[7].metadata_json["risk_flags"] == ["model_not_configured"]


def test_append_course_message_model_failure_rolls_back_without_half_messages() -> None:
    module = load_tutor_module()
    answer_module = importlib.import_module("backend.app.services.course_answers")
    user = make_user(1)
    repo = FakeTutorRepository(allowed_course_ids={7})
    citation_searcher = FakeCourseCitationSearcher(
        results=[
            {
                "chunk_id": 501,
                "course_id": 7,
                "material_id": 301,
                "knowledge_point_id": 401,
                "content": "启发式搜索利用启发函数估计路径代价。",
                "source_title": "人工智能导论讲义.md",
                "page_number": None,
                "section_title": "启发式搜索",
                "score": 9.5,
            }
        ]
    )
    answer_generator = FakeCourseAnswerGenerator(
        should_raise=answer_module.CourseAnswerGenerationError("模型暂不可用，请检查设置或稍后重试。")
    )
    service = module.TutorSessionService(
        repo,
        course_citation_searcher=citation_searcher,
        course_answer_generator=answer_generator,
    )
    session = service.create_session(user=user, scope="course", course_id=7, mode="chat", title="课程答疑")

    with pytest.raises(answer_module.CourseAnswerGenerationError):
        service.append_message(user=user, session_id=session.id, content="启发式搜索怎么复习？")

    assert repo.messages == []
    assert repo.rolled_back is False
    assert [log.agent_name for log in repo.agent_logs] == ["profile", "route", "retriever", "web_search", "planner", "tutor"]
    assert repo.agent_logs[-1].status == "failed"
    assert repo.agent_logs[-1].metadata_json["workflow"] == "course_tutor"
    assert repo.agent_logs[-1].metadata_json["error_code"] == "CourseAnswerGenerationError"


def test_stream_course_message_emits_tokens_and_persists_final_messages() -> None:
    module = load_tutor_module()
    user = make_user(1)
    repo = FakeTutorRepository(allowed_course_ids={7})
    citation_searcher = FakeCourseCitationSearcher(
        results=[
            {
                "chunk_id": 501,
                "course_id": 7,
                "material_id": 301,
                "knowledge_point_id": 401,
                "content": "启发式搜索利用启发函数估计路径代价。",
                "source_title": "人工智能导论讲义.md",
                "page_number": None,
                "section_title": "启发式搜索",
                "score": 9.5,
            }
        ]
    )
    answer_generator = FakeCourseAnswerGenerator(tokens=["模型回答：", "先看启发函数，再练 A*。"])
    service = module.TutorSessionService(
        repo,
        course_citation_searcher=citation_searcher,
        course_answer_generator=answer_generator,
    )
    session = service.create_session(user=user, scope="course", course_id=7, mode="chat", title="课程答疑")

    events = list(service.stream_message(user=user, session_id=session.id, content="启发式搜索怎么复习？"))

    assert [event["event"] for event in events] == [
        "status", "status", "status", "status", "status", "status",
        "metadata", "token", "token", "done",
    ]
    assert [event["data"]["stage"] for event in events[:6]] == [
        "profile", "route", "retriever", "web_search", "planner", "tutor",
    ]
    assert events[6]["data"] == {
        "session_id": str(session.id),
        "trace_id": "trace_model_test",
        "workflow": "course_tutor",
        "artifact_type": "chat_message",
        "citation_count": 1,
        "used_model": True,
        "steps": ["profile", "route", "retriever", "web_search", "planner", "tutor", "weakness", "review", "next_action"],
    }
    assert "".join(event["data"]["content"] for event in events if event["event"] == "token") == "模型回答：先看启发函数，再练 A*。"
    assert [message.role for message in repo.messages] == ["user", "assistant"]
    assert repo.messages[1].content == "模型回答：先看启发函数，再练 A*。"
    assert repo.messages[1].citation_json[0]["chunk_id"] == 501
    assert repo.messages[1].trace_id == "trace_model_test"
    assert events[-1]["data"]["messages"][1]["content"] == repo.messages[1].content
    assert repo.agent_logs[5].duration_ms >= 1
    assert [log.agent_name for log in repo.agent_logs] == [
        "profile",
        "route",
        "retriever",
        "web_search",
        "planner",
        "tutor",
        "weakness",
        "review",
        "next_action",
    ]
    assert repo.agent_logs[0].metadata_json["artifact_id"] == str(repo.messages[1].id)
    assert repo.agent_logs[7].metadata_json["risk_flags"] == []


def test_stream_course_message_passes_context_to_retrieval_model_and_metadata() -> None:
    module = load_tutor_module()
    user = make_user(1)
    repo = FakeTutorRepository(allowed_course_ids={7})
    citation_searcher = FakeCourseCitationSearcher(
        results=[
            {
                "chunk_id": 501,
                "course_id": 7,
                "material_id": 301,
                "knowledge_point_id": 401,
                "content": "A 星算法用估价函数选择更可能接近目标的节点。",
                "source_title": "人工智能导论讲义.md",
                "page_number": None,
                "section_title": "启发式搜索",
                "score": 9.5,
            }
        ]
    )
    answer_generator = FakeCourseAnswerGenerator(tokens=["模型回答：", "结合刚才的 A* 继续做题。"])
    service = module.TutorSessionService(
        repo,
        course_citation_searcher=citation_searcher,
        course_answer_generator=answer_generator,
    )
    session = service.create_session(user=user, scope="course", course_id=7, mode="chat", title="课程答疑")
    add_history_message(repo, session, "user", "A 星算法为什么要估价函数？")
    add_history_message(repo, session, "assistant", "估价函数帮助排序待扩展节点。")

    events = list(service.stream_message(user=user, session_id=session.id, content="那这个怎么做题？"))

    assert citation_searcher.calls[0]["query"] == "A 星算法为什么要估价函数？\n那这个怎么做题？"
    context = answer_generator.calls[0]["conversation_context"]
    assert context.message_count == 2
    assert context.messages[0]["content"] == "A 星算法为什么要估价函数？"
    metadata = next(event["data"] for event in events if event["event"] == "metadata")
    assert metadata["context_message_count"] == 2
    assert metadata["context_summary_used"] is False
    assert metadata["retrieval_query_mode"] == "contextual"
    assert repo.agent_logs[0].metadata_json["context_message_count"] == 2
    assert repo.agent_logs[0].metadata_json["retrieval_query_mode"] == "contextual"


def test_stream_course_message_records_only_explicit_model_profile_signal_on_done() -> None:
    module = load_tutor_module()
    user = make_user(1)
    repo = FakeTutorRepository(allowed_course_ids={7})
    profile_recorder = FakeProfileEventRecorder()
    service = module.TutorSessionService(
        repo,
        course_citation_searcher=FakeCourseCitationSearcher(
            results=[
                {
                    "chunk_id": 501,
                    "course_id": 7,
                    "material_id": 301,
                    "knowledge_point_id": 401,
                    "content": "启发式搜索利用启发函数估计路径代价。",
                    "source_title": "人工智能导论讲义.md",
                    "page_number": None,
                    "section_title": "启发式搜索",
                    "score": 9.5,
                }
            ]
        ),
        course_answer_generator=FakeCourseAnswerGenerator(tokens=["模型回答：", "先看启发函数。"]),
            profile_event_recorder=profile_recorder,
            semantic_decision_service=FakeSemanticDecisionService(
                intent="material_question",
                course_related=True,
                profile_updates={"weak_points": ["启发式搜索"]},
                profile_confidence={"weak_points": 0.88},
            ),
    )
    session = service.create_session(user=user, scope="course", course_id=7, mode="chat", title="课程答疑")

    events = list(service.stream_message(user=user, session_id=session.id, content="启发式搜索怎么复习才不难？"))

    assert events[-1]["event"] == "done"
    assert profile_recorder.calls == [
        {
            "user_id": 1,
            "scope": "course",
            "course_id": 7,
            "user_message_id": 1,
                "message_text": "启发式搜索怎么复习才不难？",
                "citation_count": 1,
                "trace_id": "trace_model_test",
                "suggested_updates": {"weak_points": ["启发式搜索"]},
                "suggested_confidence": {"weak_points": 0.88},
        }
    ]


def test_stream_course_message_without_citations_does_not_call_model_and_persists_insufficient_evidence() -> None:
    module = load_tutor_module()
    user = make_user(1)
    repo = FakeTutorRepository(allowed_course_ids={7})
    answer_generator = FakeCourseAnswerGenerator()
    service = module.TutorSessionService(
        repo,
        course_citation_searcher=FakeCourseCitationSearcher(results=[]),
        course_answer_generator=answer_generator,
    )
    session = service.create_session(user=user, scope="course", course_id=7, mode="chat", title="课程答疑")

    events = list(service.stream_message(user=user, session_id=session.id, content="量子通信怎么复习？"))

    assert answer_generator.calls == []
    assert [event["event"] for event in events] == [
        "status", "status", "status", "status", "status", "status", "metadata", "token", "done",
    ]
    metadata = events[6]["data"]
    assert metadata["used_model"] is False
    assert metadata["workflow"] == "course_tutor"
    assert metadata["steps"][-1] == "next_action"
    assert metadata["citation_count"] == 0
    assert "还没有足够依据" in events[7]["data"]["content"]
    assert repo.messages[1].citation_json == []


def test_stream_home_message_returns_graph_events_without_model_config() -> None:
    module = load_tutor_module()
    user = make_user(1)
    repo = FakeTutorRepository()
    service = module.TutorSessionService(repo)
    session = service.create_session(user=user, scope="home", course_id=None, mode="chat", title="主页答疑")

    events = list(service.stream_message(user=user, session_id=session.id, content="主页问题"))

    event_names = [event["event"] for event in events]
    assert event_names[0] == "metadata"
    assert "sources" in event_names
    assert "token" in event_names
    assert [name for name in event_names if name in {"done", "error", "cancelled"}] == ["done"]
    assert events[0]["data"]["workflow"] == "home_tutor"
    assert "当前未配置可用模型" in next(event["data"]["content"] for event in events if event["event"] == "token")


def test_stream_home_message_emits_replace_after_review_repair() -> None:
    module = load_tutor_module()
    user = make_user(1)
    repo = FakeTutorRepository()
    answer_generator = FakeCourseAnswerGenerator(
        tokens=[
            "<final_answer>学生问题：什么是机器学习？ 工具状态：未联网 "
            "可用来源摘要：资料开头</final_answer>"
        ],
        repair_content="## 机器学习\n\n机器学习通过数据学习可泛化的规律。",
    )
    service = module.TutorSessionService(repo, course_answer_generator=answer_generator)
    session = service.create_session(user=user, scope="home", course_id=None, mode="chat", title="机器学习")

    events = list(service.stream_message(user=user, session_id=session.id, content="什么是机器学习？"))

    event_names = [event["event"] for event in events]
    assert event_names[0] == "metadata"
    assert "sources" in event_names
    assert "replace" in event_names
    assert [name for name in event_names if name in {"done", "error", "cancelled"}] == ["done"]
    replacement = next(event["data"] for event in events if event["event"] == "replace")
    assert replacement == {
        "content": "## 机器学习\n\n机器学习通过数据学习可泛化的规律。",
        "reason": "review_repair",
    }
    assert len(answer_generator.repair_calls) == 1
    assert repo.messages[1].content == replacement["content"]


def test_stream_home_model_failure_emits_error_without_persisting_partial_messages() -> None:
    module = load_tutor_module()
    answer_module = importlib.import_module("backend.app.services.course_answers")
    user = make_user(1)
    repo = FakeTutorRepository()
    answer_generator = FakeCourseAnswerGenerator(
        should_raise=answer_module.CourseAnswerGenerationError("模型暂不可用，请检查设置或稍后重试。")
    )
    service = module.TutorSessionService(repo, course_answer_generator=answer_generator)
    session = service.create_session(user=user, scope="home", course_id=None, mode="chat", title="失败测试")

    events = list(service.stream_message(user=user, session_id=session.id, content="什么是机器学习？"))

    assert [event["event"] for event in events if event["event"] in {"done", "error", "cancelled"}] == ["error"]
    assert events[-1]["data"]["code"] == "MODEL_PROVIDER_ERROR"
    assert repo.messages == []
    assert [log.agent_name for log in repo.agent_logs] == [
        "context",
        "route",
        "material_retriever",
        "web_search",
        "planner",
        "answer",
    ]
    assert repo.agent_logs[-1].status == "failed"


def test_stream_course_message_model_failure_emits_error_without_half_messages() -> None:
    module = load_tutor_module()
    answer_module = importlib.import_module("backend.app.services.course_answers")
    user = make_user(1)
    repo = FakeTutorRepository(allowed_course_ids={7})
    citation_searcher = FakeCourseCitationSearcher(
        results=[
            {
                "chunk_id": 501,
                "course_id": 7,
                "material_id": 301,
                "knowledge_point_id": 401,
                "content": "启发式搜索利用启发函数估计路径代价。",
                "source_title": "人工智能导论讲义.md",
                "page_number": None,
                "section_title": "启发式搜索",
                "score": 9.5,
            }
        ]
    )
    answer_generator = FakeCourseAnswerGenerator(
        should_raise=answer_module.CourseAnswerGenerationError("模型暂不可用，请检查设置或稍后重试。")
    )
    service = module.TutorSessionService(
        repo,
        course_citation_searcher=citation_searcher,
        course_answer_generator=answer_generator,
    )
    session = service.create_session(user=user, scope="course", course_id=7, mode="chat", title="课程答疑")

    events = list(service.stream_message(user=user, session_id=session.id, content="启发式搜索怎么复习？"))

    assert [event["event"] for event in events if event["event"] in {"done", "error", "cancelled"}] == ["error"]
    assert events[-1]["data"]["code"] == "MODEL_PROVIDER_ERROR"
    assert repo.messages == []
    assert [log.agent_name for log in repo.agent_logs] == ["profile", "route", "retriever", "web_search", "planner", "tutor"]
    assert repo.agent_logs[-1].status == "failed"
    assert repo.agent_logs[-1].metadata_json["error_code"] == "CourseAnswerGenerationError"


def test_stream_course_message_model_failure_does_not_record_profile_candidate_event() -> None:
    module = load_tutor_module()
    answer_module = importlib.import_module("backend.app.services.course_answers")
    user = make_user(1)
    repo = FakeTutorRepository(allowed_course_ids={7})
    profile_recorder = FakeProfileEventRecorder()
    service = module.TutorSessionService(
        repo,
        course_citation_searcher=FakeCourseCitationSearcher(
            results=[
                {
                    "chunk_id": 501,
                    "course_id": 7,
                    "material_id": 301,
                    "knowledge_point_id": 401,
                    "content": "启发式搜索利用启发函数估计路径代价。",
                    "source_title": "人工智能导论讲义.md",
                    "page_number": None,
                    "section_title": "启发式搜索",
                    "score": 9.5,
                }
            ]
        ),
        course_answer_generator=FakeCourseAnswerGenerator(
            should_raise=answer_module.CourseAnswerGenerationError("模型暂不可用，请检查设置或稍后重试。")
        ),
        profile_event_recorder=profile_recorder,
    )
    session = service.create_session(user=user, scope="course", course_id=7, mode="chat", title="课程答疑")

    events = list(service.stream_message(user=user, session_id=session.id, content="启发式搜索怎么复习才不难？"))

    assert events[-1]["event"] == "error"
    assert profile_recorder.calls == []


def test_get_session_and_append_message_reject_other_users_session() -> None:
    module = load_tutor_module()
    user = make_user(1)
    other_session = ChatSession(
        id=42,
        user_id=2,
        course_id=None,
        scope="home",
        title="别人的主页会话",
        mode="chat",
        archived_from_home=False,
    )
    other_session.created_at = NOW
    other_session.updated_at = NOW
    service = module.TutorSessionService(FakeTutorRepository(sessions=[other_session]))

    with pytest.raises(module.SessionNotFoundError):
        service.get_session(user=user, session_id=42)

    with pytest.raises(module.SessionNotFoundError):
        service.append_message(user=user, session_id=42, content="越权追问")


def test_tutor_session_routes_create_send_and_read_messages() -> None:
    module = load_tutor_module()
    api_module = load_tutor_api_module()
    user = make_user(1, "接口学生")
    settings = Settings(
        _env_file=None,
        jwt_secret="tutor-session-test-secret-with-32-bytes",
        jwt_expire_minutes=30,
    )
    repo = FakeTutorRepository()
    app = create_app()
    app.dependency_overrides[get_auth_service] = lambda: AuthService(
        repository=TokenAuthRepository(user),
        settings=settings,
    )
    app.dependency_overrides[api_module.get_tutor_session_service] = lambda: module.TutorSessionService(repo)
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {make_token(user, settings)}"}

    create_response = client.post(
        "/api/v1/tutor/sessions",
        headers=headers,
        json={"scope": "home", "course_id": None, "mode": "chat", "title": "主页第一问"},
    )
    assert create_response.status_code == 200
    session_id = create_response.json()["data"]["id"]

    send_response = client.post(
        f"/api/v1/tutor/sessions/{session_id}/messages",
        headers=headers,
        json={"message": "我应该先看概念还是先刷题？"},
    )
    assert send_response.status_code == 200
    assert [item["role"] for item in send_response.json()["data"]["messages"]] == ["user", "assistant"]

    detail_response = client.get(f"/api/v1/tutor/sessions/{session_id}", headers=headers)
    assert detail_response.status_code == 200
    assert detail_response.json()["data"]["session"]["title"] == "主页第一问"
    assert detail_response.json()["data"]["messages"][0]["content"] == "我应该先看概念还是先刷题？"

    history_response = client.get("/api/v1/tutor/sessions/history?page=1&page_size=30&q=概念", headers=headers)
    assert history_response.status_code == 200
    assert history_response.json()["data"]["total"] == 1
    assert "概念" in history_response.json()["data"]["items"][0]["match_snippet"]

    list_response = client.get("/api/v1/tutor/sessions?scope=home", headers=headers)
    assert list_response.status_code == 200
    assert [item["title"] for item in list_response.json()["data"]] == ["主页第一问"]

    rename_response = client.patch(
        f"/api/v1/tutor/sessions/{session_id}",
        headers=headers,
        json={"title": "  改名后的主页历史  "},
    )
    assert rename_response.status_code == 200
    assert rename_response.json()["data"]["title"] == "改名后的主页历史"

    renamed_list_response = client.get("/api/v1/tutor/sessions?scope=home", headers=headers)
    assert renamed_list_response.status_code == 200
    assert [item["title"] for item in renamed_list_response.json()["data"]] == ["改名后的主页历史"]

    delete_response = client.delete(f"/api/v1/tutor/sessions/{session_id}", headers=headers)
    assert delete_response.status_code == 200
    assert delete_response.json()["data"] == {"session_id": session_id, "deleted": True}

    deleted_list_response = client.get("/api/v1/tutor/sessions?scope=home", headers=headers)
    assert deleted_list_response.status_code == 200
    assert deleted_list_response.json()["data"] == []

    deleted_detail_response = client.get(f"/api/v1/tutor/sessions/{session_id}", headers=headers)
    assert deleted_detail_response.status_code == 404


def test_tutor_message_route_accepts_home_tool_options() -> None:
    module = load_tutor_module()
    api_module = load_tutor_api_module()
    user = make_user(1, "接口学生")
    settings = Settings(
        _env_file=None,
        jwt_secret="tutor-session-test-secret-with-32-bytes",
        jwt_expire_minutes=30,
    )
    repo = FakeTutorRepository(materials=[make_home_material()])
    answer_generator = FakeCourseAnswerGenerator()
    material_searcher = FakeMaterialCitationSearcher(
        citations=[
            {
                "source_type": "material",
                "material_id": "301",
                "title": "主页复习资料.pdf",
                "section_title": "启发式搜索",
                "page_number": None,
                "snippet": "启发式搜索要结合 A* 和估价函数一起复习。",
                "score": 7.5,
                "retrieval_source": "keyword",
                "embedding_status": "local_fallback",
            }
        ]
    )
    app = create_app()
    app.dependency_overrides[get_auth_service] = lambda: AuthService(
        repository=TokenAuthRepository(user),
        settings=settings,
    )
    app.dependency_overrides[api_module.get_tutor_session_service] = lambda: module.TutorSessionService(
        repo,
        course_answer_generator=answer_generator,
        web_search_service=FakeWebSearchService(warning="联网搜索未配置。"),
        material_citation_searcher=material_searcher,
    )
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {make_token(user, settings)}"}
    session = module.TutorSessionService(repo).create_session(user=user, scope="home", course_id=None, mode="chat", title="主页第一问")

    context_response = client.patch(
        f"/api/v1/tutor/sessions/{session.id}",
        headers=headers,
        json={"selected_material_ids": [301]},
    )
    assert context_response.status_code == 200
    assert context_response.json()["data"]["selected_material_ids"] == [301]

    response = client.post(
        f"/api/v1/tutor/sessions/{session.id}/messages",
        headers=headers,
        json={
            "message": "启发式搜索怎么复习？",
            "use_web_search": True,
            "deep_thinking": True,
        },
    )

    assert response.status_code == 200
    assert answer_generator.calls[0]["use_web_search"] is True
    assert answer_generator.calls[0]["deep_thinking"] is True
    assert answer_generator.calls[0]["warnings"] == ["联网搜索未配置。"]
    assert response.json()["data"]["messages"][1]["citation_json"][0]["source_type"] == "material"


def test_tutor_stream_route_requires_login() -> None:
    client = TestClient(create_app())

    response = client.post("/api/v1/tutor/sessions/1/messages/stream", json={"message": "你好"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_tutor_stream_route_accepts_home_session() -> None:
    module = load_tutor_module()
    api_module = load_tutor_api_module()
    user = make_user(1, "接口学生")
    settings = Settings(
        _env_file=None,
        jwt_secret="tutor-session-test-secret-with-32-bytes",
        jwt_expire_minutes=30,
    )
    repo = FakeTutorRepository()
    service = module.TutorSessionService(repo, course_answer_generator=FakeCourseAnswerGenerator())
    app = create_app()
    app.dependency_overrides[get_auth_service] = lambda: AuthService(
        repository=TokenAuthRepository(user),
        settings=settings,
    )
    app.dependency_overrides[api_module.get_tutor_session_service] = lambda: service
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {make_token(user, settings)}"}
    session = service.create_session(user=user, scope="home", course_id=None, mode="chat", title="主页第一问")

    response = client.post(
        f"/api/v1/tutor/sessions/{session.id}/messages/stream",
        headers=headers,
        json={"message": "主页问题"},
    )

    assert response.status_code == 200
    assert response.headers["x-accel-buffering"] == "no"
    assert "event: metadata" in response.text
    assert response.text.count("event: done") == 1
    assert "event: error" not in response.text


def test_tutor_session_route_rejects_course_session_without_course_id() -> None:
    module = load_tutor_module()
    api_module = load_tutor_api_module()
    user = make_user(1)
    settings = Settings(
        _env_file=None,
        jwt_secret="tutor-session-test-secret-with-32-bytes",
        jwt_expire_minutes=30,
    )
    app = create_app()
    app.dependency_overrides[get_auth_service] = lambda: AuthService(
        repository=TokenAuthRepository(user),
        settings=settings,
    )
    app.dependency_overrides[api_module.get_tutor_session_service] = lambda: module.TutorSessionService(FakeTutorRepository())
    client = TestClient(app)

    response = client.post(
        "/api/v1/tutor/sessions",
        headers={"Authorization": f"Bearer {make_token(user, settings)}"},
        json={"scope": "course", "course_id": None, "mode": "chat", "title": "课程会话"},
    )

    assert response.status_code in {400, 422}

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
from backend.app.models import ChatMessage, ChatSession, User
from backend.app.services.auth import AuthService


NOW = datetime(2026, 7, 3, 16, 0, tzinfo=UTC)


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
    allowed_course_ids: set[int] = field(default_factory=set)
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
                if session.id == session_id and session.user_id == user_id
            ),
            None,
        )

    def user_can_access_course(self, user_id: int, course_id: int) -> bool:
        return course_id in self.allowed_course_ids

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
class FakeCourseAnswerGenerator:
    content: str = "模型回答：启发式搜索要先理解启发函数，再练 A 星算法。"
    tokens: list[str] = field(default_factory=lambda: ["模型回答：", "启发式搜索要先理解启发函数。"])
    trace_id: str | None = "trace_model_test"
    should_raise: Exception | None = None
    calls: list[dict[str, Any]] = field(default_factory=list)

    def generate(self, user: User, question: str, citations: list[dict[str, Any]]) -> SimpleNamespace:
        self.calls.append(
            {
                "user_id": user.id,
                "question": question,
                "citations": citations,
            }
        )
        if self.should_raise is not None:
            raise self.should_raise
        return SimpleNamespace(content=self.content, trace_id=self.trace_id)

    def generate_home(self, user: User, question: str) -> SimpleNamespace:
        self.calls.append(
            {
                "user_id": user.id,
                "question": question,
                "citations": [],
            }
        )
        if self.should_raise is not None:
            raise self.should_raise
        return SimpleNamespace(content=self.content, trace_id=self.trace_id)

    def stream(self, user: User, question: str, citations: list[dict[str, Any]]) -> SimpleNamespace:
        self.calls.append(
            {
                "user_id": user.id,
                "question": question,
                "citations": citations,
                "stream": True,
            }
        )
        if self.should_raise is not None:
            raise self.should_raise
        return SimpleNamespace(tokens=iter(self.tokens), trace_id=self.trace_id)


@dataclass
class TokenAuthRepository:
    user: User

    def get_user_by_id(self, user_id: int) -> User | None:
        return self.user if self.user.id == user_id else None


def make_user(user_id: int, display_name: str = "测试学生") -> User:
    return User(
        id=user_id,
        email=f"user{user_id}@edunova.local",
        hashed_password="not-used",
        display_name=display_name,
        role="student",
        starter_mode="blank",
    )


def as_dict(value: Any) -> dict[str, Any]:
    return value.model_dump() if hasattr(value, "model_dump") else value


def make_token(user: User, settings: Settings) -> str:
    return create_access_token(str(user.id), settings=settings)


def test_tutor_sessions_route_requires_login() -> None:
    client = TestClient(create_app())

    response = client.get("/api/v1/tutor/sessions?scope=home")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


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
    assert detail["messages"][1]["trace_id"] == "trace_model_test"
    assert answer_generator.calls == [
        {
            "user_id": 1,
            "question": "为什么反向传播要用链式法则？",
            "citations": [],
        }
    ]
    assert detail["session"]["updated_at"] > detail["session"]["created_at"]
    assert repo.committed is True


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
    assert detail["messages"][1]["trace_id"] == "trace_model_test"


def test_append_home_message_without_model_config_saves_clear_prompt() -> None:
    module = load_tutor_module()
    user = make_user(1)
    repo = FakeTutorRepository()
    service = module.TutorSessionService(repo)
    session = service.create_session(user=user, scope="home", course_id=None, mode="chat", title="主页答疑")

    detail = as_dict(service.append_message(user=user, session_id=session.id, content="主页怎么复习？"))

    assert "当前未配置可用模型" in detail["messages"][1]["content"]
    assert detail["messages"][1]["citation_json"] == []
    assert detail["messages"][1]["trace_id"] is None


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
    assert detail["messages"][1]["trace_id"] is None


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

    assert [event["event"] for event in events] == ["metadata", "token", "token", "done"]
    assert events[0]["data"] == {
        "session_id": str(session.id),
        "trace_id": "trace_model_test",
        "citation_count": 1,
        "used_model": True,
    }
    assert "".join(event["data"]["content"] for event in events if event["event"] == "token") == "模型回答：先看启发函数，再练 A*。"
    assert [message.role for message in repo.messages] == ["user", "assistant"]
    assert repo.messages[1].content == "模型回答：先看启发函数，再练 A*。"
    assert repo.messages[1].citation_json[0]["chunk_id"] == 501
    assert repo.messages[1].trace_id == "trace_model_test"
    assert events[-1]["data"]["messages"][1]["content"] == repo.messages[1].content


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
    assert [event["event"] for event in events] == ["metadata", "token", "done"]
    assert events[0]["data"]["used_model"] is False
    assert events[0]["data"]["citation_count"] == 0
    assert "还没有足够依据" in events[1]["data"]["content"]
    assert repo.messages[1].citation_json == []


def test_stream_home_message_is_rejected() -> None:
    module = load_tutor_module()
    user = make_user(1)
    repo = FakeTutorRepository()
    service = module.TutorSessionService(repo)
    session = service.create_session(user=user, scope="home", course_id=None, mode="chat", title="主页答疑")

    with pytest.raises(module.InvalidSessionScopeError):
        list(service.stream_message(user=user, session_id=session.id, content="主页问题"))


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

    assert events[-1]["event"] == "error"
    assert events[-1]["data"]["code"] == "MODEL_PROVIDER_ERROR"
    assert repo.messages == []


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

    list_response = client.get("/api/v1/tutor/sessions?scope=home", headers=headers)
    assert list_response.status_code == 200
    assert [item["title"] for item in list_response.json()["data"]] == ["主页第一问"]


def test_tutor_stream_route_requires_login() -> None:
    client = TestClient(create_app())

    response = client.post("/api/v1/tutor/sessions/1/messages/stream", json={"message": "你好"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_tutor_stream_route_rejects_home_session() -> None:
    module = load_tutor_module()
    api_module = load_tutor_api_module()
    user = make_user(1, "接口学生")
    settings = Settings(
        _env_file=None,
        jwt_secret="tutor-session-test-secret-with-32-bytes",
        jwt_expire_minutes=30,
    )
    repo = FakeTutorRepository()
    service = module.TutorSessionService(repo)
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

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


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

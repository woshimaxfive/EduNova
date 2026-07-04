from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.app.api.v1.deps import get_auth_service
from backend.app.core.config import Settings
from backend.app.core.security import create_access_token
from backend.app.main import create_app
from backend.app.models import ChatMessage, ChatSession, ProfileEvent, StudentProfile, User
from backend.app.services.auth import AuthService


NOW = datetime(2026, 7, 5, 9, 0, tzinfo=UTC)


def load_profile_module():
    try:
        return importlib.import_module("backend.app.services.profiles")
    except ModuleNotFoundError as exc:
        pytest.fail(f"缺少 profiles 服务模块: {exc.name}")


def load_profile_api_module():
    try:
        return importlib.import_module("backend.app.api.v1.profiles")
    except ModuleNotFoundError as exc:
        pytest.fail(f"缺少 profiles API 模块: {exc.name}")


@dataclass
class FakeProfileRepository:
    profiles: dict[int, StudentProfile] = field(default_factory=dict)
    events: list[ProfileEvent] = field(default_factory=list)
    next_profile_id: int = 1
    next_event_id: int = 1
    pending_profiles: list[StudentProfile] = field(default_factory=list)
    pending_events: list[ProfileEvent] = field(default_factory=list)
    committed: bool = False
    rolled_back: bool = False

    def get_profile(self, user_id: int) -> StudentProfile | None:
        return self.profiles.get(user_id)

    def add_profile(self, profile: StudentProfile) -> None:
        self.pending_profiles.append(profile)
        self.profiles[profile.user_id] = profile

    def add_event(self, event: ProfileEvent) -> None:
        self.pending_events.append(event)
        self.events.append(event)

    def list_events(self, user_id: int, limit: int) -> list[ProfileEvent]:
        return sorted(
            [event for event in self.events if event.user_id == user_id],
            key=lambda event: event.created_at,
            reverse=True,
        )[:limit]

    def count_events_for_profile(self, profile_id: int | None) -> int:
        if profile_id is None:
            return 0
        return len([event for event in self.events if event.profile_id == profile_id])

    def flush(self) -> None:
        for profile in self.pending_profiles:
            if profile.id is None:
                profile.id = self.next_profile_id
                self.next_profile_id += 1
            profile.created_at = NOW
            profile.updated_at = NOW
        self.pending_profiles.clear()
        for event in self.pending_events:
            if event.id is None:
                event.id = self.next_event_id
                self.next_event_id += 1
            event.created_at = NOW + timedelta(minutes=event.id)
        self.pending_events.clear()

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True


@dataclass
class TokenAuthRepository:
    user: User

    def get_user_by_id(self, user_id: int) -> User | None:
        return self.user if self.user.id == user_id else None


def make_user(user_id: int, display_name: str = "画像学生") -> User:
    return User(
        id=user_id,
        email=f"profile{user_id}@edunova.local",
        hashed_password="not-used",
        display_name=display_name,
        role="student",
        starter_mode="blank",
    )


def as_dict(value: Any) -> dict[str, Any]:
    return value.model_dump() if hasattr(value, "model_dump") else value


def make_token(user: User, settings: Settings) -> str:
    return create_access_token(str(user.id), settings=settings)


def test_profile_route_requires_login() -> None:
    client = TestClient(create_app())

    response = client.get("/api/v1/profiles/me")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_empty_profile_returns_stable_eight_dimension_shape() -> None:
    module = load_profile_module()
    user = make_user(1, "空白学生")
    service = module.ProfileService(FakeProfileRepository(), now=NOW)

    profile = as_dict(service.get_my_profile(user))

    assert profile["id"] is None
    assert profile["version"] == 0
    assert profile["has_profile"] is False
    assert profile["profile_json"] == {
        "major_background": "",
        "knowledge_foundation": "",
        "learning_goal": "",
        "cognitive_style": "",
        "learning_preference": "",
        "weak_points": [],
        "learning_pace": "",
        "motivation_interest": "",
    }
    assert profile["confidence_score"] == 0
    assert profile["next_question"] == "这门课你最想先解决什么问题？"


def test_profile_chat_creates_profile_and_event_from_deterministic_extraction() -> None:
    module = load_profile_module()
    user = make_user(1)
    repo = FakeProfileRepository()
    service = module.ProfileService(repo, now=NOW)

    result = as_dict(
        service.update_by_chat(
            user,
            "我是计算机专业大二学生，机器学习刚入门，数学基础一般，想期末前掌握神经网络。我喜欢案例和图解，每天 45 分钟学习。",
        )
    )

    profile_json = result["profile"]["profile_json"]
    assert profile_json["major_background"] == "计算机专业大二学生"
    assert profile_json["knowledge_foundation"] == "机器学习刚入门"
    assert profile_json["learning_goal"] == "期末前掌握神经网络"
    assert profile_json["learning_preference"] == "案例和图解"
    assert profile_json["learning_pace"] == "每天 45 分钟"
    assert profile_json["weak_points"] == ["数学基础一般"]
    assert result["event"]["dimension"] == "profile_chat"
    assert result["event"]["evidence_json"]["source_type"] == "profile_chat"
    assert "计算机专业大二学生" not in str(result["event"]["evidence_json"])
    assert result["profile"]["version"] == 1
    assert repo.events[0].profile_id == repo.profiles[user.id].id
    assert repo.committed is True


def test_profile_events_are_current_user_only_and_descending() -> None:
    module = load_profile_module()
    user = make_user(1)
    profile = StudentProfile(
        id=7,
        user_id=1,
        profile_json={"learning_goal": "期末复习"},
        confidence_score=Decimal("0.50"),
    )
    old_event = ProfileEvent(
        id=1,
        user_id=1,
        profile_id=7,
        dimension="profile_chat",
        change_summary="旧事件",
        evidence_json={"source_type": "profile_chat"},
    )
    old_event.created_at = NOW
    new_event = ProfileEvent(
        id=2,
        user_id=1,
        profile_id=7,
        dimension="weak_points",
        change_summary="新事件",
        evidence_json={"source_type": "course_question"},
    )
    new_event.created_at = NOW + timedelta(minutes=3)
    other_event = ProfileEvent(
        id=3,
        user_id=2,
        profile_id=None,
        dimension="profile_chat",
        change_summary="别人事件",
        evidence_json={},
    )
    other_event.created_at = NOW + timedelta(minutes=5)
    service = module.ProfileService(
        FakeProfileRepository(profiles={1: profile}, events=[old_event, new_event, other_event]),
        now=NOW,
    )

    events = [as_dict(event) for event in service.list_events(user)]
    profile_data = as_dict(service.get_my_profile(user))

    assert [event["change_summary"] for event in events] == ["新事件", "旧事件"]
    assert profile_data["version"] == 2


def test_course_question_profile_event_is_privacy_safe_and_signal_gated() -> None:
    module = load_profile_module()
    user = make_user(1)
    profile = StudentProfile(
        id=9,
        user_id=1,
        profile_json={"learning_goal": "复习 AI"},
        confidence_score=Decimal("0.60"),
    )
    repo = FakeProfileRepository(profiles={1: profile})
    service = module.ProfileService(repo, now=NOW)
    session = ChatSession(id=3, user_id=1, course_id=7, scope="course", title="课程答疑", mode="chat")
    user_message = ChatMessage(id=11, session_id=3, user_id=1, role="user", content="为什么启发式搜索这么难？")
    assistant_message = ChatMessage(id=12, session_id=3, user_id=1, role="assistant", content="先看启发函数。")
    citations = [
        {
            "chunk_id": 501,
            "knowledge_point_id": 401,
            "source_title": "人工智能导论讲义.md",
            "section_title": "启发式搜索",
            "content": "启发式搜索利用启发函数估计路径代价。",
        }
    ]

    event = service.record_course_question_event(
        user=user,
        session=session,
        user_message=user_message,
        assistant_message=assistant_message,
        message_text="为什么启发式搜索这么难？",
        citation_json=citations,
        trace_id="trace_model_test",
    )
    ignored = service.record_course_question_event(
        user=user,
        session=session,
        user_message=user_message,
        assistant_message=assistant_message,
        message_text="解释一下启发式搜索",
        citation_json=citations,
        trace_id="trace_model_test",
    )

    assert ignored is None
    assert event is not None
    assert event.dimension == "weak_points"
    assert event.profile_id == 9
    assert event.evidence_json == {
        "source_type": "course_question",
        "course_id": 7,
        "session_id": 3,
        "user_message_id": 11,
        "assistant_message_id": 12,
        "trace_id": "trace_model_test",
        "citations": [
            {
                "chunk_id": 501,
                "knowledge_point_id": 401,
                "source_title": "人工智能导论讲义.md",
                "section_title": "启发式搜索",
            }
        ],
    }
    assert "为什么启发式搜索这么难" not in str(event.evidence_json)
    assert "启发式搜索利用启发函数" not in str(event.evidence_json)


def test_profile_routes_read_update_and_list_current_user_profile() -> None:
    module = load_profile_module()
    api_module = load_profile_api_module()
    user = make_user(1, "接口学生")
    settings = Settings(
        _env_file=None,
        jwt_secret="profile-test-secret-with-32-bytes",
        jwt_expire_minutes=30,
    )
    repo = FakeProfileRepository()
    app = create_app()
    app.dependency_overrides[get_auth_service] = lambda: AuthService(
        repository=TokenAuthRepository(user),
        settings=settings,
    )
    app.dependency_overrides[api_module.get_profile_service] = lambda: module.ProfileService(repo, now=NOW)
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {make_token(user, settings)}"}

    empty_response = client.get("/api/v1/profiles/me", headers=headers)
    chat_response = client.post(
        "/api/v1/profiles/chat",
        headers=headers,
        json={"message": "我是计算机专业大二学生，机器学习刚入门，想期末前掌握神经网络。"},
    )
    events_response = client.get("/api/v1/profiles/events", headers=headers)
    invalid_response = client.post("/api/v1/profiles/chat", headers=headers, json={"message": ""})
    whitespace_response = client.post("/api/v1/profiles/chat", headers=headers, json={"message": "   "})

    assert empty_response.status_code == 200
    assert empty_response.json()["data"]["has_profile"] is False
    assert chat_response.status_code == 200
    assert chat_response.json()["data"]["profile"]["has_profile"] is True
    assert chat_response.json()["data"]["profile"]["profile_json"]["major_background"] == "计算机专业大二学生"
    assert events_response.status_code == 200
    assert [event["dimension"] for event in events_response.json()["data"]] == ["profile_chat"]
    assert invalid_response.status_code == 422
    assert whitespace_response.status_code == 422

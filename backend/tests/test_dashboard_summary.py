from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.app.api.v1.deps import get_auth_service
from backend.app.api.v1.dashboard import get_dashboard_service
from backend.app.core.config import Settings
from backend.app.core.security import create_access_token
from backend.app.main import create_app
from backend.app.models import (
    ChatSession,
    Course,
    CourseEnrollment,
    GeneratedResource,
    Material,
    StudentProfile,
    User,
)
from backend.app.services.auth import AuthService


NOW = datetime(2026, 7, 3, 12, 0, tzinfo=UTC)


def load_dashboard_module():
    try:
        return importlib.import_module("backend.app.services.dashboard")
    except ModuleNotFoundError as exc:
        pytest.fail(f"缺少 dashboard summary 服务模块: {exc.name}")


@dataclass
class FakeDashboardRepository:
    profiles: dict[int, StudentProfile] = field(default_factory=dict)
    courses: list[Course] = field(default_factory=list)
    enrollments: list[CourseEnrollment] = field(default_factory=list)
    materials: list[Material] = field(default_factory=list)
    linked_material_ids: set[int] = field(default_factory=set)
    conversations: list[ChatSession] = field(default_factory=list)
    resources: list[GeneratedResource] = field(default_factory=list)
    requested_user_ids: list[int] = field(default_factory=list)
    _kp_counts: dict[int, int] = field(default_factory=dict)
    _practiced_kps: dict[int, set[int]] = field(default_factory=dict)
    _latest_practice: dict[int, datetime] = field(default_factory=dict)

    def _remember(self, user_id: int) -> None:
        self.requested_user_ids.append(user_id)

    def get_profile(self, user_id: int) -> StudentProfile | None:
        self._remember(user_id)
        return self.profiles.get(user_id)

    def list_recent_courses(self, user_id: int, limit: int) -> list[Course]:
        self._remember(user_id)
        return sorted(
            [course for course in self.courses if course.owner_id == user_id],
            key=lambda course: course.updated_at,
            reverse=True,
        )[:limit]

    def list_course_enrollments(self, user_id: int, course_ids: list[int]) -> list[CourseEnrollment]:
        self._remember(user_id)
        return [
            enrollment
            for enrollment in self.enrollments
            if enrollment.user_id == user_id and enrollment.course_id in course_ids
        ]

    def list_recent_materials(self, user_id: int, limit: int) -> list[Material]:
        self._remember(user_id)
        return sorted(
            [material for material in self.materials if material.user_id == user_id],
            key=lambda material: material.created_at,
            reverse=True,
        )[:limit]

    def count_materials(self, user_id: int) -> int:
        self._remember(user_id)
        return len([material for material in self.materials if material.user_id == user_id])

    def count_unassigned_materials(self, user_id: int) -> int:
        self._remember(user_id)
        return len(
            [
                material
                for material in self.materials
                if material.user_id == user_id and material.id not in self.linked_material_ids
            ]
        )

    def list_recent_home_conversations(self, user_id: int, limit: int) -> list[ChatSession]:
        self._remember(user_id)
        return sorted(
            [
                session
                for session in self.conversations
                if session.user_id == user_id
                and session.scope == "home"
                and not session.archived_from_home
            ],
            key=lambda session: session.updated_at,
            reverse=True,
        )[:limit]

    def list_recent_resources(self, user_id: int, limit: int) -> list[GeneratedResource]:
        self._remember(user_id)
        return sorted(
            [resource for resource in self.resources if resource.user_id == user_id],
            key=lambda resource: resource.updated_at,
            reverse=True,
        )[:limit]

    def knowledge_point_counts(self, course_ids: list[int]) -> dict[int, int]:
        return {cid: self._kp_counts.get(cid, 0) for cid in course_ids}

    def practiced_knowledge_point_ids(self, user_id: int, course_ids: list[int]) -> dict[int, set[int]]:
        return {cid: self._practiced_kps.get(cid, set()) for cid in course_ids}

    def latest_practice_times(self, user_id: int, course_ids: list[int]) -> dict[int, datetime]:
        return {cid: self._latest_practice.get(cid) for cid in course_ids if cid in self._latest_practice}


@dataclass
class TokenAuthRepository:
    user: User

    def get_user_by_id(self, user_id: int) -> User | None:
        return self.user if self.user.id == user_id else None


def make_user(user_id: int, starter_mode: str, display_name: str = "测试学生") -> User:
    return User(
        id=user_id,
        account=f"user{user_id}",
        hashed_password="not-used",
        display_name=display_name,
        role="student",
        starter_mode=starter_mode,
    )


def as_dict(summary: Any) -> dict[str, Any]:
    return summary.model_dump() if hasattr(summary, "model_dump") else summary


def test_dashboard_summary_route_requires_login() -> None:
    client = TestClient(create_app())

    response = client.get("/api/v1/dashboard/summary")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_dashboard_summary_route_returns_current_user_summary() -> None:
    module = load_dashboard_module()
    user = make_user(1, "blank", "接口学生")
    settings = Settings(
        _env_file=None,
        jwt_secret="dashboard-test-secret-with-32-bytes",
        jwt_expire_minutes=30,
    )
    app = create_app()
    app.dependency_overrides[get_auth_service] = lambda: AuthService(
        repository=TokenAuthRepository(user),
        settings=settings,
    )
    app.dependency_overrides[get_dashboard_service] = lambda: module.DashboardService(FakeDashboardRepository())
    client = TestClient(app)
    token = create_access_token(str(user.id), settings=settings)

    response = client.get(
        "/api/v1/dashboard/summary",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["profile_summary"]["display_name"] == "接口学生"
    assert response.json()["data"]["empty_state"]["kind"] == "blank"


def test_blank_user_dashboard_summary_stays_empty_and_stable() -> None:
    module = load_dashboard_module()
    user = make_user(1, "blank", "空白学习者")
    summary = as_dict(module.DashboardService(FakeDashboardRepository()).build_summary(user))

    assert summary["profile_summary"] == {
        "display_name": "空白学习者",
        "starter_mode": "blank",
        "has_profile": False,
        "knowledge_foundation": None,
        "learning_goal": None,
    }
    assert summary["recent_conversations"] == []
    assert summary["recent_courses"] == []
    assert summary["material_library_summary"] == {"material_count": 0, "unassigned_count": 0}
    assert summary["recent_materials"] == []
    assert summary["recent_resources"] == []
    assert summary["empty_state"]["kind"] == "blank"
    assert summary["empty_state"]["title"] == "还没有课程"


def test_data_structures_user_summary_uses_internal_course_without_library_material() -> None:
    module = load_dashboard_module()
    user = make_user(1, "data_structures", "课程学习者")
    course = Course(
        id=101,
        owner_id=1,
        title="数据结构与算法",
        description="数据结构核心课程",
        subject="计算机科学",
        source_type="builtin",
        visibility="private",
        status="ready",
    )
    course.created_at = NOW - timedelta(days=1)
    course.updated_at = NOW - timedelta(hours=2)

    summary = as_dict(
        module.DashboardService(
            FakeDashboardRepository(courses=[course]),
            now=NOW,
        ).build_summary(user)
    )

    assert summary["recent_courses"] == [
        {
            "id": "101",
            "title": "数据结构与算法",
            "source_type": "builtin",
            "progress_label": "未开始",
            "practiced_knowledge_point_count": 0,
            "knowledge_point_count": 0,
            "focus": "计算机科学",
            "next": "开始学习",
        }
    ]
    assert summary["recent_materials"] == []
    assert summary["material_library_summary"] == {"material_count": 0, "unassigned_count": 0}
    assert summary["empty_state"]["kind"] == "starter"
    assert summary["command_suggestions"] == [
        "继续学习《数据结构与算法》",
        "帮我复习《数据结构与算法》的薄弱点",
        "先帮我拆解下一步复习计划",
    ]


def test_dashboard_summary_uses_real_progress_profile_conversations_and_resources() -> None:
    module = load_dashboard_module()
    user = make_user(1, "data_structures", "进阶学生")
    profile = StudentProfile(
        id=301,
        user_id=1,
        profile_json={"knowledge_foundation": "会 Python 基础", "learning_goal": "两周复习 AI"},
        confidence_score=Decimal("0.82"),
    )
    course = Course(
        id=102,
        owner_id=1,
        title="机器学习复习",
        description="监督学习与模型评估",
        subject=None,
        source_type="generated",
        visibility="private",
        status="ready",
    )
    course.created_at = NOW - timedelta(days=2)
    course.updated_at = NOW - timedelta(minutes=10)
    enrollment = CourseEnrollment(
        id=401,
        user_id=1,
        course_id=102,
        role="learner",
        progress_percent=Decimal("35.00"),
    )
    conversation = ChatSession(
        id=501,
        user_id=1,
        course_id=None,
        scope="home",
        title="期末复习怎么开始",
        mode="chat",
        archived_from_home=False,
    )
    conversation.created_at = NOW - timedelta(hours=1)
    conversation.updated_at = NOW - timedelta(minutes=3)
    resource = GeneratedResource(
        id=601,
        user_id=1,
        course_id=102,
        knowledge_point_id=None,
        resource_type="practice",
        title="监督学习练习",
        content_json={"items": 3},
        citation_json=[{"material_id": 201}],
        status="draft",
        review_status="pending",
        confidence_score=Decimal("0.91"),
    )
    resource.created_at = NOW - timedelta(minutes=20)
    resource.updated_at = NOW - timedelta(minutes=20)

    summary = as_dict(
        module.DashboardService(
            FakeDashboardRepository(
                profiles={1: profile},
                courses=[course],
                enrollments=[enrollment],
                conversations=[conversation],
                resources=[resource],
                _kp_counts={102: 20},
                _practiced_kps={102: {1, 2, 3, 4, 5, 6, 7}},
            ),
            now=NOW,
        ).build_summary(user)
    )

    assert summary["profile_summary"]["has_profile"] is True
    assert summary["profile_summary"]["knowledge_foundation"] == "会 Python 基础"
    assert summary["profile_summary"]["learning_goal"] == "两周复习 AI"
    assert summary["recent_courses"][0]["progress_label"] == "35%"
    assert summary["recent_courses"][0]["next"] == "继续学习"
    assert summary["recent_conversations"] == [
        {
            "id": "501",
            "title": "期末复习怎么开始",
            "meta": "刚刚",
            "scope": "home",
            "updated_at": "2026-07-03T11:57:00Z",
        }
    ]
    assert summary["recent_resources"][0]["title"] == "监督学习练习"
    assert summary["evidence_summary"]["citation_count"] == 1
    assert summary["empty_state"]["kind"] == "active"


def test_dashboard_summary_requests_only_current_user_data() -> None:
    module = load_dashboard_module()
    user = make_user(1, "blank")
    other_course = Course(
        id=999,
        owner_id=2,
        title="别人的课程",
        description=None,
        subject="不应出现",
        source_type="generated",
        visibility="private",
        status="ready",
    )
    other_course.created_at = NOW
    other_course.updated_at = NOW
    repo = FakeDashboardRepository(courses=[other_course])

    summary = as_dict(module.DashboardService(repo).build_summary(user))

    assert summary["recent_courses"] == []
    assert set(repo.requested_user_ids) == {1}

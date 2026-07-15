from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from backend.app.api.v1.deps import get_auth_service
from backend.app.api.v1.learning import get_learning_next_action_service
from backend.app.core.config import Settings
from backend.app.core.security import create_access_token
from backend.app.main import create_app
from backend.app.models import (
    AiJob,
    AssessmentReport,
    Course,
    LearningPath,
    LearningTask,
    Material,
    PracticeSession,
    User,
    WeaknessReviewItem,
)
from backend.app.schemas.learning import LearningNextAction
from backend.app.services.auth import AuthService
from backend.app.services.learning_actions import LearningActionCourseNotFoundError, LearningNextActionService


NOW = datetime(2026, 7, 15, 12, 0, tzinfo=UTC)


def make_user(user_id: int = 1) -> User:
    return User(id=user_id, account=f"student{user_id}", display_name="学生", hashed_password="hash", starter_mode="blank")


def make_course() -> Course:
    return Course(id=10, owner_id=1, title="机器学习", status="ready", source_type="uploaded", created_at=NOW, updated_at=NOW)


def make_path() -> LearningPath:
    return LearningPath(id=20, user_id=1, course_id=10, title="学习路径", status="active", plan_json={}, created_at=NOW, updated_at=NOW)


def make_task(status: str = "todo") -> LearningTask:
    return LearningTask(
        id=30,
        path_id=20,
        user_id=1,
        course_id=10,
        knowledge_point_id=40,
        title="理解监督学习",
        task_type="learn",
        reason="先理解基本概念",
        recommended_resource_ids=[50],
        status=status,
        created_at=NOW,
        updated_at=NOW,
    )


def mastery(*points: object) -> SimpleNamespace:
    return SimpleNamespace(points=list(points))


def point(point_id: int, title: str, score: int | None, order_index: int = 0) -> SimpleNamespace:
    return SimpleNamespace(id=str(point_id), title=title, score=score, order_index=order_index)


def service_with(db: MagicMock, mastery_map: SimpleNamespace) -> LearningNextActionService:
    course_service = MagicMock()
    course_service.get_mastery_map.return_value = mastery_map
    return LearningNextActionService(db, course_service)


def test_material_actions_cover_upload_wait_review_retry_and_course_creation() -> None:
    service = service_with(MagicMock(), mastery())
    assert service._material_action(None).kind == "upload_material"

    material = Material(id=1, user_id=1, filename="教材.pdf", content_type="application/pdf", storage_path="x", parse_status="uploaded", ingestion_status="pending", created_at=NOW)
    assert service._material_action(material).kind == "wait_for_material"
    assert service._material_action(material).status == "waiting"

    material.parse_status = "completed"
    material.ingestion_status = "awaiting_confirmation"
    assert service._material_action(material).kind == "review_material"

    material.ingestion_status = "confirmed"
    assert service._material_action(material).kind == "create_course"

    material.parse_status = "failed"
    material.ingestion_status = "failed"
    assert service._material_action(material).kind == "retry_material"
    assert service._material_action(material).status == "blocked"


def test_path_job_is_exposed_as_waiting_next_action() -> None:
    service = service_with(MagicMock(), mastery())
    job = AiJob(
        id=90,
        user_id=1,
        course_id=10,
        workflow="path_planning",
        status="running",
        progress_percent=38,
        stage="deterministic_rank",
        label="已生成安全路径底稿",
        agent_trace_id="trace-path",
        idempotency_key="path-10",
        request_json={"course_id": 10},
        progress_json={},
        result_json={},
    )

    action = service._job_action(job)

    assert action is not None
    assert action.kind == "wait_for_path"
    assert action.status == "waiting"
    assert action.course_id == "10"


def test_course_action_prioritizes_pending_weakness_then_current_path_task() -> None:
    pending = WeaknessReviewItem(id=60, user_id=1, course_id=10, knowledge_point_id=40, title="梯度下降", source_type="tutor", status="pending", updated_at=NOW, created_at=NOW)
    db = MagicMock()
    db.scalars.return_value = [pending]
    action = service_with(db, mastery())._course_action(make_user(), make_course())
    assert action.kind == "confirm_weakness"
    assert action.knowledge_point_id == "40"

    db = MagicMock()
    db.scalars.side_effect = [[], [make_task()]]
    db.scalar.return_value = make_path()
    action = service_with(db, mastery())._course_action(make_user(), make_course())
    assert action.kind == "continue_path_task"
    assert action.path_task_id == "30"
    assert action.resource_id == "50"


def test_course_action_uses_mastery_then_generates_missing_path() -> None:
    db = MagicMock()
    db.scalars.return_value = []
    db.scalar.return_value = None
    action = service_with(db, mastery(point(41, "线性回归", 52)))._course_action(make_user(), make_course())
    assert action.kind == "practice_weakness"
    assert action.knowledge_point_id == "41"

    db = MagicMock()
    db.scalars.return_value = []
    db.scalar.return_value = None
    action = service_with(db, mastery(point(41, "线性回归", None)))._course_action(make_user(), make_course())
    assert action.kind == "generate_path"


def test_completed_path_with_new_practice_recommends_report() -> None:
    path = make_path()
    task = make_task("completed")
    practice = PracticeSession(id=70, user_id=1, course_id=10, title="练习", status="completed", assessment_json={}, created_at=NOW, updated_at=NOW)
    report = AssessmentReport(id=80, user_id=1, course_id=10, practice_session_id=69, report_json={}, created_at=NOW - timedelta(hours=1))
    db = MagicMock()
    db.scalars.side_effect = [[], [task]]
    db.scalar.side_effect = [path, practice, report]
    action = service_with(db, mastery(point(41, "线性回归", 90)))._course_action(make_user(), make_course())
    assert action.kind == "update_report"


@dataclass
class TokenAuthRepository:
    user: User

    def get_user_by_id(self, user_id: int) -> User | None:
        return self.user if user_id == self.user.id else None


class StubLearningActionService:
    def __init__(self, action: LearningNextAction | None = None, *, missing: bool = False) -> None:
        self.action = action
        self.missing = missing

    def get_next_action(self, user: User, course_id: int | None = None) -> LearningNextAction:
        if self.missing:
            raise LearningActionCourseNotFoundError("课程不存在或当前用户无权访问。")
        assert user.id == 1
        assert course_id in {None, 10}
        assert self.action is not None
        return self.action


def make_client(service: StubLearningActionService) -> tuple[TestClient, dict[str, str]]:
    user = make_user()
    settings = Settings(jwt_secret_key="test-secret", database_url="sqlite://")
    app = create_app()
    app.dependency_overrides[get_auth_service] = lambda: AuthService(TokenAuthRepository(user), settings)
    app.dependency_overrides[get_learning_next_action_service] = lambda: service
    token = create_access_token(str(user.id), settings)
    return TestClient(app), {"Authorization": f"Bearer {token}"}


def test_learning_next_action_route_is_typed_and_user_scoped() -> None:
    expected = LearningNextAction(kind="generate_path", status="ready", label="生成路径", description="开始规划", course_id="10")
    client, headers = make_client(StubLearningActionService(expected))
    response = client.get("/api/v1/learning/next-action?course_id=10", headers=headers)
    assert response.status_code == 200
    assert response.json()["data"] == expected.model_dump()

    anonymous = client.get("/api/v1/learning/next-action")
    assert anonymous.status_code == 401


def test_learning_next_action_route_hides_foreign_courses() -> None:
    client, headers = make_client(StubLearningActionService(missing=True))
    response = client.get("/api/v1/learning/next-action?course_id=10", headers=headers)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"

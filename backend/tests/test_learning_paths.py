from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.app.api.v1.deps import get_auth_service
from backend.app.core.config import Settings
from backend.app.core.security import create_access_token
from backend.app.main import create_app
from backend.app.models import (
    Course,
    GeneratedResource,
    KnowledgePoint,
    LearningPath,
    LearningTask,
    StudentProfile,
    User,
    WeaknessReviewItem,
)
from backend.app.services.auth import AuthService
from backend.app.services.paths import PathService


NOW = datetime(2026, 7, 5, 9, 0, tzinfo=UTC)


@dataclass
class TokenAuthRepository:
    user: User

    def get_user_by_id(self, user_id: int) -> User | None:
        return self.user if self.user.id == user_id else None


@dataclass
class FakePathRepository:
    courses: list[Course] = field(default_factory=list)
    knowledge_points: list[KnowledgePoint] = field(default_factory=list)
    profiles: dict[int, StudentProfile] = field(default_factory=dict)
    weakness_items: list[WeaknessReviewItem] = field(default_factory=list)
    resources: list[GeneratedResource] = field(default_factory=list)
    paths: list[LearningPath] = field(default_factory=list)
    tasks: list[LearningTask] = field(default_factory=list)
    next_path_id: int = 901
    next_task_id: int = 1001

    def get_course_for_user(self, user_id: int, course_id: int) -> Course | None:
        return next((course for course in self.courses if course.owner_id == user_id and course.id == course_id), None)

    def list_knowledge_points(self, course_id: int) -> list[KnowledgePoint]:
        return sorted(
            [point for point in self.knowledge_points if point.course_id == course_id],
            key=lambda point: (point.order_index, point.id),
        )

    def get_profile(self, user_id: int) -> StudentProfile | None:
        return self.profiles.get(user_id)

    def list_weakness_review_items(self, user_id: int, course_id: int) -> list[WeaknessReviewItem]:
        return sorted(
            [item for item in self.weakness_items if item.user_id == user_id and item.course_id == course_id],
            key=lambda item: (item.created_at, item.id),
            reverse=True,
        )

    def list_generated_resources(self, user_id: int, course_id: int) -> list[GeneratedResource]:
        return sorted(
            [resource for resource in self.resources if resource.user_id == user_id and resource.course_id == course_id],
            key=lambda resource: (resource.updated_at, resource.id),
            reverse=True,
        )

    def get_active_path(self, user_id: int, course_id: int) -> LearningPath | None:
        active_paths = [
            path for path in self.paths if path.user_id == user_id and path.course_id == course_id and path.status == "active"
        ]
        return sorted(active_paths, key=lambda path: (path.updated_at, path.id), reverse=True)[0] if active_paths else None

    def list_tasks_for_path(self, path_id: int) -> list[LearningTask]:
        return sorted([task for task in self.tasks if task.path_id == path_id], key=lambda task: (task.due_at or NOW, task.id))

    def archive_active_paths(self, user_id: int, course_id: int) -> None:
        for path in self.paths:
            if path.user_id == user_id and path.course_id == course_id and path.status == "active":
                path.status = "archived"
                path.updated_at = NOW

    def add_path(self, path: LearningPath) -> LearningPath:
        path.id = self.next_path_id
        self.next_path_id += 1
        path.created_at = NOW
        path.updated_at = NOW
        self.paths.append(path)
        return path

    def add_task(self, task: LearningTask) -> LearningTask:
        task.id = self.next_task_id
        self.next_task_id += 1
        task.created_at = NOW
        task.updated_at = NOW
        self.tasks.append(task)
        return task

    def get_task_for_user(self, user_id: int, task_id: int) -> LearningTask | None:
        return next((task for task in self.tasks if task.user_id == user_id and task.id == task_id), None)

    def commit(self) -> None:
        return None

    def rollback(self) -> None:
        return None

    def refresh(self, _instance: object) -> None:
        return None


def make_user(user_id: int = 1) -> User:
    return User(
        id=user_id,
        email=f"user{user_id}@edunova.local",
        hashed_password="not-used",
        display_name=f"用户 {user_id}",
        role="student",
        starter_mode="blank",
    )


def make_course(course_id: int = 101, owner_id: int = 1) -> Course:
    return Course(
        id=course_id,
        owner_id=owner_id,
        title="AI 搜索复习",
        description="由资料生成",
        subject="人工智能",
        source_type="uploaded",
        visibility="private",
        status="ready",
    )


def make_point(point_id: int, title: str, order_index: int) -> KnowledgePoint:
    return KnowledgePoint(
        id=point_id,
        course_id=101,
        title=title,
        summary=f"{title} 摘要",
        chapter="第一章",
        order_index=order_index,
        difficulty=None,
        prerequisites_json=[],
    )


def make_weakness(item_id: int, status: str, knowledge_point_id: int | None, title: str) -> WeaknessReviewItem:
    item = WeaknessReviewItem(
        id=item_id,
        user_id=1,
        course_id=101,
        knowledge_point_id=knowledge_point_id,
        title=title,
        source_type="course_question",
        status=status,
        recommended_resource_ids=[],
        next_review_at=None,
    )
    item.created_at = NOW
    item.updated_at = NOW
    return item


def make_resource(resource_id: int, knowledge_point_id: int | None, title: str) -> GeneratedResource:
    return GeneratedResource(
        id=resource_id,
        user_id=1,
        course_id=101,
        knowledge_point_id=knowledge_point_id,
        resource_type="doc",
        title=title,
        content_json={"markdown": "安全摘要", "metadata": {"agent_trace_id": "trace_resource"}},
        citation_json=[],
        status="completed",
        review_status="passed",
        confidence_score=Decimal("0.88"),
        created_at=NOW,
        updated_at=NOW,
    )


def as_dict(model: Any) -> dict[str, Any]:
    return model.model_dump() if hasattr(model, "model_dump") else model


def make_repo() -> FakePathRepository:
    return FakePathRepository(
        courses=[make_course(), make_course(202, owner_id=2)],
        knowledge_points=[
            make_point(401, "启发式搜索", 0),
            make_point(402, "A* 搜索", 1),
            make_point(403, "局部搜索", 2),
        ],
        profiles={
            1: StudentProfile(
                id=9,
                user_id=1,
                profile_json={
                    "learning_goal": "期末前掌握搜索算法",
                    "knowledge_foundation": "机器学习刚入门",
                    "weak_points": ["启发式搜索"],
                },
                confidence_score=Decimal("0.71"),
                updated_reason="画像对话",
            )
        },
        weakness_items=[
            make_weakness(701, "reviewing", 402, "A* 搜索"),
            make_weakness(702, "confirmed", 401, "启发式搜索"),
            make_weakness(703, "pending", 403, "局部搜索"),
            make_weakness(704, "dismissed", None, "已忽略弱点"),
        ],
        resources=[
            make_resource(801, 401, "启发式搜索讲解"),
            make_resource(802, 402, "A* 搜索练习"),
            make_resource(803, None, "局部搜索整课资源"),
        ],
    )


def test_generate_path_archives_previous_active_path_and_prioritizes_confirmed_reviewing_items() -> None:
    previous_path = LearningPath(
        id=800,
        user_id=1,
        course_id=101,
        title="旧路径",
        goal="旧目标",
        status="active",
        plan_json={},
    )
    previous_path.created_at = NOW
    previous_path.updated_at = NOW
    repo = make_repo()
    repo.paths.append(previous_path)
    service = PathService(repo)

    result = as_dict(service.generate_path(make_user(), course_id=101, duration_days=7, goal="搜索算法冲刺"))

    assert previous_path.status == "archived"
    assert result["status"] == "active"
    assert result["path"]["course_id"] == "101"
    assert result["path"]["goal"] == "搜索算法冲刺"
    assert result["path"]["plan_json"]["duration_days"] == 7
    assert result["path"]["plan_json"]["source_counts"]["confirmed_or_reviewing_weaknesses"] == 2
    assert [task["knowledge_point_id"] for task in result["tasks"][:3]] == ["402", "401", "403"]
    assert [task["task_type"] for task in result["tasks"]] == ["review", "review", "learn"]
    assert result["tasks"][0]["status"] == "doing"
    assert result["tasks"][1]["status"] == "todo"
    assert result["tasks"][0]["recommended_resource_ids"] == ["802"]
    assert result["tasks"][1]["recommended_resource_ids"] == ["801"]
    serialized = str(result)
    assert "系统提示词" not in serialized
    assert "模型输入" not in serialized
    assert "API Key" not in serialized


def test_get_current_path_returns_empty_state_and_scopes_course() -> None:
    repo = make_repo()
    service = PathService(repo)

    empty = as_dict(service.get_current_path(make_user(), 101))

    assert empty["status"] == "not_started"
    assert empty["path"] is None
    assert empty["tasks"] == []
    assert empty["message"] == "学习路径尚未生成。"

    from backend.app.services.paths import PathNotFoundError

    with pytest.raises(PathNotFoundError):
        service.get_current_path(make_user(1), 202)


def test_update_task_status_is_user_scoped_and_validated() -> None:
    repo = make_repo()
    service = PathService(repo)
    generated = as_dict(service.generate_path(make_user(), course_id=101, duration_days=3, goal=""))
    task_id = int(generated["tasks"][1]["id"])

    updated = as_dict(service.update_task_status(make_user(), task_id, "completed"))

    assert updated["status"] == "completed"
    assert repo.tasks[1].status == "completed"

    from backend.app.services.paths import PathNotFoundError, PathValidationError

    with pytest.raises(PathNotFoundError):
        service.update_task_status(make_user(2), task_id, "completed")

    with pytest.raises(PathValidationError):
        service.update_task_status(make_user(1), task_id, "done")


def test_paths_routes_require_login_and_return_envelopes() -> None:
    from backend.app.api.v1.paths import get_path_service

    repo = make_repo()
    user = make_user()
    settings = Settings(_env_file=None, jwt_secret="paths-test-secret-with-32-bytes-long", jwt_expire_minutes=30)
    app = create_app()
    app.dependency_overrides[get_auth_service] = lambda: AuthService(
        repository=TokenAuthRepository(user),
        settings=settings,
    )
    app.dependency_overrides[get_path_service] = lambda: PathService(repo)
    client = TestClient(app)
    token = create_access_token(str(user.id), settings=settings)
    headers = {"Authorization": f"Bearer {token}"}

    unauthorized = client.post("/api/v1/paths/generate", json={"course_id": 101, "duration_days": 7, "goal": ""})
    generated = client.post(
        "/api/v1/paths/generate",
        headers=headers,
        json={"course_id": 101, "duration_days": 7, "goal": "搜索算法冲刺"},
    )
    current = client.get("/api/v1/paths/current?course_id=101", headers=headers)
    updated = client.patch(
        f"/api/v1/paths/tasks/{generated.json()['data']['tasks'][0]['id']}",
        headers=headers,
        json={"status": "completed"},
    )
    missing = client.get("/api/v1/paths/current?course_id=202", headers=headers)

    assert unauthorized.status_code == 401
    assert generated.status_code == 200
    assert generated.json()["data"]["path"]["goal"] == "搜索算法冲刺"
    assert current.status_code == 200
    assert current.json()["data"]["status"] == "active"
    assert updated.status_code == 200
    assert updated.json()["data"]["status"] == "completed"
    assert missing.status_code == 404

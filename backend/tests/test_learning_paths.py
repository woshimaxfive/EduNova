from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
import json
from typing import Any
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend.app.api.v1.deps import get_auth_service
from backend.app.agents.runtime import AgentTraceRecorder
from backend.app.core.config import Settings
from backend.app.core.security import create_access_token
from backend.app.main import create_app
from backend.app.models import (
    Course,
    GeneratedResource,
    KnowledgePoint,
    LearningPath,
    LearningTask,
    ResourceInteraction,
    StudentProfile,
    User,
    WeaknessReviewItem,
)
from backend.app.services.auth import AuthService
from backend.app.services.paths import PathService, PathValidationError


NOW = datetime(2026, 7, 5, 9, 0, tzinfo=UTC)


@dataclass
class FakeModelService:
    responses: list[str]
    calls: list[list[dict[str, str]]] = field(default_factory=list)

    def chat_completion(self, _user: User, messages: list[dict[str, str]]) -> str:
        self.calls.append(messages)
        return self.responses.pop(0)


class DefaultPathModelService:
    def __init__(self) -> None:
        self.calls: list[list[dict[str, str]]] = []

    def chat_completion(self, _user: User, messages: list[dict[str, str]]) -> str:
        self.calls.append(messages)
        payload = json.loads(messages[-1]["content"])
        choices = []
        for item in payload["candidate_tasks"][:8]:
            choices.append(
                {
                    "task_key": item["task_key"],
                    "rationale": f"优先解决{item['title']}的当前学习问题",
                    "bundle_types": list(item.get("bundle_types") or ["doc", "quiz"])[:4],
                    "resource_ids": list(item.get("resource_ids") or [])[:2],
                    "teaching_strategy": "证据讲解后进行迁移练习",
                    "learning_problem": f"理解并应用{item['title']}",
                    "example_direction": "使用当前课程中的典型案例",
                    "difficulty": "medium",
                    "used_profile_factor_codes": [],
                }
            )
        return json.dumps({"priority_tasks": choices}, ensure_ascii=False)


class TaskProfilePathModelService(DefaultPathModelService):
    def __init__(self) -> None:
        super().__init__()
        self.task_profiles: list[Any] = []

    def chat_completion_for_task(self, user: User, messages: list[dict[str, str]], profile: Any) -> str:
        self.task_profiles.append(profile)
        return self.chat_completion(user, messages)


def make_path_service(repo: FakePathRepository) -> PathService:
    return PathService(repo, model_service=DefaultPathModelService())


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
    interactions: list[ResourceInteraction] = field(default_factory=list)
    next_path_id: int = 901
    next_task_id: int = 1001

    def get_course_for_user(self, user_id: int, course_id: int) -> Course | None:
        return next((course for course in self.courses if course.owner_id == user_id and course.id == course_id), None)

    def is_course_active(self, user_id: int, course_id: int) -> bool:
        return self.get_course_for_user(user_id, course_id) is not None

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
        return sorted([task for task in self.tasks if task.path_id == path_id], key=lambda task: task.id)

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

    def list_resource_interactions_for_path(self, user_id: int, path_id: int) -> list[ResourceInteraction]:
        task_ids = {task.id for task in self.tasks if task.path_id == path_id and task.user_id == user_id}
        return [
            item for item in self.interactions
            if item.user_id == user_id and item.path_task_id in task_ids
        ]

    def commit(self) -> None:
        return None

    def rollback(self) -> None:
        return None

    def refresh(self, _instance: object) -> None:
        return None


def make_user(user_id: int = 1) -> User:
    return User(
        id=user_id,
        account=f"user{user_id}",
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
                    "learning_goal": "掌握搜索算法",
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


def make_trace_recorder(logs: list[Any]) -> AgentTraceRecorder:
    def add_log(log):
        logs.append(log)
        return log

    return AgentTraceRecorder(repository_add_log=add_log)


def test_path_graph_persists_the_profile_version_from_learner_context(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = make_repo()
    learner_context = SimpleNamespace(
        global_context=SimpleNamespace(profile_applied_version=4),
        context_hash="course-context-v4",
        prompt_summary=lambda: {
            "learning_goal": "掌握搜索算法",
            "knowledge_foundation": "机器学习刚入门",
            "learning_preference": "案例与练习",
        },
        trace_metadata=lambda: {
            "profile_applied_version": 4,
            "trusted_dimension_count": 3,
            "profile_context_used": True,
        },
    )
    context_service = SimpleNamespace(course_context=lambda _user_id, _course_id: learner_context)
    monkeypatch.setattr(
        "backend.app.agents.path_planning.context_service_from_repository",
        lambda _repository: context_service,
    )

    detail = make_path_service(repo).generate_path(make_user(), 101)

    assert detail.path is not None
    assert detail.path.plan_json["profile_applied_version"] == 4
    assert detail.path.plan_json["course_context_hash"] == "course-context-v4"


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
    service = make_path_service(repo)

    result = as_dict(service.generate_path(make_user(), course_id=101))

    assert previous_path.status == "archived"
    assert result["status"] == "active"
    assert result["path"]["course_id"] == "101"
    assert result["path"]["goal"] == "掌握搜索算法"
    assert result["path"]["plan_json"]["schema_version"] == 5
    assert result["path"]["plan_json"]["path_mode"] == "ordered"
    assert "daily_task_capacity" not in result["path"]["plan_json"]["personalization"]
    assert result["path"]["plan_json"]["source_counts"]["confirmed_or_reviewing_weaknesses"] == 2
    assert [task["knowledge_point_id"] for task in result["tasks"][:3]] == ["402", "401", "403"]
    assert [task["task_type"] for task in result["tasks"]] == ["review", "review", "learn"]
    assert result["tasks"][0]["status"] == "doing"
    assert result["tasks"][1]["status"] == "todo"
    assert result["tasks"][0]["recommended_resource_ids"] == ["802"]
    assert result["tasks"][1]["recommended_resource_ids"] == ["801"]
    assert "due_at" not in result["tasks"][0]
    assert "next_review_at" not in result["tasks"][0]
    assert [item["resource_type"] for item in result["tasks"][0]["learning_bundle"]["items"]] == [
        "doc", "mindmap", "quiz"
    ]
    assert all(task.due_at is None and task.next_review_at is None for task in repo.list_tasks_for_path(int(result["path"]["id"])))
    serialized = str(result)
    assert "系统提示词" not in serialized
    assert "模型输入" not in serialized
    assert "API Key" not in serialized


def test_manual_path_update_preserves_completed_and_current_progress() -> None:
    repo = make_repo()
    service = make_path_service(repo)
    first = service.generate_path(make_user(), 101)
    assert first.path is not None
    old_tasks = repo.list_tasks_for_path(int(first.path.id))
    old_tasks[0].status = "completed"
    old_tasks[1].status = "doing"

    updated = service.generate_path(make_user(), 101)

    assert updated.path is not None
    assert updated.path.plan_json["trigger"] == "manual"
    assert updated.path.plan_json["preserved_task_count"] == 1
    assert updated.tasks[0].status == "completed"
    assert sum(task.status == "doing" for task in updated.tasks) == 1


def test_manual_path_generation_reuses_model_path_when_learning_state_is_unchanged() -> None:
    repo = make_repo()
    model = DefaultPathModelService()
    service = PathService(repo, model_service=model)

    first = service.generate_path(make_user(), 101)
    second = service.generate_path(make_user(), 101)

    assert first.path is not None
    assert second.path is not None
    assert second.path.id == first.path.id
    assert second.path.plan_json["generation_mode"] == "model_generated"
    assert second.path.plan_json["planning_input_hash"]
    assert len(model.calls) == 1
    assert len([path for path in repo.paths if path.status == "active"]) == 1


def test_get_current_path_returns_empty_state_and_scopes_course() -> None:
    repo = make_repo()
    service = make_path_service(repo)

    empty = as_dict(service.get_current_path(make_user(), 101))

    assert empty["status"] == "not_started"
    assert empty["path"] is None
    assert empty["tasks"] == []
    assert empty["message"] == "学习路径尚未生成。"

    from backend.app.services.paths import PathNotFoundError

    with pytest.raises(PathNotFoundError):
        service.get_current_path(make_user(1), 202)


def test_learning_bundle_status_comes_from_scoped_resource_interactions() -> None:
    repo = make_repo()
    next(resource for resource in repo.resources if resource.id == 801).resource_type = "mindmap"
    service = make_path_service(repo)
    generated = as_dict(service.generate_path(make_user(), course_id=101))
    task = repo.tasks[0]
    task.learning_bundle_json = {
        **task.learning_bundle_json,
        "items": [
            {"resource_type": "doc", "resource_id": 802, "status": "ready"},
            {"resource_type": "mindmap", "resource_id": 801, "status": "ready"},
            {"resource_type": "quiz", "status": "missing"},
        ],
    }
    repo.interactions.extend(
        [
            ResourceInteraction(
                id=1101,
                event_id="opened-doc",
                user_id=1,
                course_id=101,
                resource_id=802,
                path_task_id=task.id,
                event_type="opened",
                progress_percent=None,
                feedback=None,
                created_at=NOW,
            ),
            ResourceInteraction(
                id=1102,
                event_id="completed-doc",
                user_id=1,
                course_id=101,
                resource_id=802,
                path_task_id=task.id,
                event_type="completed",
                progress_percent=100,
                feedback=None,
                created_at=NOW,
            ),
            ResourceInteraction(
                id=1103,
                event_id="started-mindmap",
                user_id=1,
                course_id=101,
                resource_id=801,
                path_task_id=task.id,
                event_type="started",
                progress_percent=10,
                feedback=None,
                created_at=NOW,
            ),
            ResourceInteraction(
                id=1104,
                event_id="other-user-completed",
                user_id=2,
                course_id=101,
                resource_id=801,
                path_task_id=task.id,
                event_type="completed",
                progress_percent=100,
                feedback=None,
                created_at=NOW,
            ),
        ]
    )

    current = as_dict(service.get_current_path(make_user(), 101))
    bundle = current["tasks"][0]["learning_bundle"]

    assert generated["tasks"][0]["learning_bundle"]["completed_count"] == 0
    assert bundle["ready_count"] == 2
    assert bundle["completed_count"] == 1
    assert [item["learning_status"] for item in bundle["items"]] == [
        "completed",
        "in_progress",
        "not_started",
    ]


def test_learning_bundle_recovers_resource_links_from_recommended_ids_for_legacy_data() -> None:
    repo = make_repo()
    service = make_path_service(repo)
    service.generate_path(make_user(), course_id=101)
    task = repo.tasks[0]
    task.recommended_resource_ids = [802]
    task.learning_bundle_json = {
        **task.learning_bundle_json,
        "items": [{"resource_type": "doc", "resource_id": None, "status": "recommended"}],
    }

    current = as_dict(service.get_current_path(make_user(), 101))
    bundle = current["tasks"][0]["learning_bundle"]

    assert bundle["ready_count"] == 1
    assert bundle["items"][0]["resource_id"] == "802"
    assert bundle["items"][0]["status"] == "available"


def test_update_task_status_is_user_scoped_and_validated() -> None:
    repo = make_repo()
    service = make_path_service(repo)
    generated = as_dict(service.generate_path(make_user(), course_id=101))
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
    app.dependency_overrides[get_path_service] = lambda: make_path_service(repo)
    client = TestClient(app)
    token = create_access_token(str(user.id), settings=settings)
    headers = {"Authorization": f"Bearer {token}"}

    unauthorized = client.post("/api/v1/paths/generate", json={"course_id": 101})
    generated = client.post(
        "/api/v1/paths/generate",
        headers=headers,
        json={"course_id": 101},
    )
    current = client.get("/api/v1/paths/current?course_id=101", headers=headers)
    updated = client.patch(
        f"/api/v1/paths/tasks/{generated.json()['data']['tasks'][0]['id']}",
        headers=headers,
        json={"status": "completed"},
    )
    missing = client.get("/api/v1/paths/current?course_id=202", headers=headers)
    retired_sprint = client.get("/api/v1/exam-sprint/plans/current?course_id=101", headers=headers)

    assert unauthorized.status_code == 401
    assert generated.status_code == 200
    assert generated.json()["data"]["path"]["goal"] == "掌握搜索算法"
    assert current.status_code == 200
    assert current.json()["data"]["status"] == "active"
    assert updated.status_code == 200
    assert updated.json()["data"]["status"] == "completed"
    assert missing.status_code == 404
    assert retired_sprint.status_code == 404


def test_path_planning_graph_uses_one_structured_model_call_and_rules_review() -> None:
    repo = make_repo()
    logs: list[Any] = []
    model = FakeModelService(
        responses=['{"output":{"priority_tasks":['
            '{"task_key":"knowledge:401","rationale":"先处理确认弱点",'
            '"bundle_types":["code","doc","quiz"],"resource_ids":[801],'
            '"teaching_strategy":"先代码实验再概念复盘","difficulty":"medium",'
            '"learning_problem":"理解启发式评价","example_direction":"搜索路径代码实验",'
            '"used_profile_factor_codes":[]},'
            '{"task_key":"knowledge:402","rationale":"再巩固复习中弱点",'
            '"bundle_types":["mindmap","doc"],"resource_ids":[802],'
            '"teaching_strategy":"先图解再检索练习","difficulty":"hard",'
            '"learning_problem":"辨析代价组成","example_direction":"搜索树结构图",'
            '"used_profile_factor_codes":[]}]}}']
    )
    service = PathService(repo, model_service=model, trace_recorder=make_trace_recorder(logs))

    detail = as_dict(service.generate_path(make_user(), 101))

    assert detail["path"]["plan_json"]["schema_version"] == 5
    assert detail["path"]["plan_json"]["path_mode"] == "ordered"
    assert detail["path"]["plan_json"]["generation_mode"] == "model_generated"
    assert detail["path"]["plan_json"]["review_mode"] == "rules_only"
    assert [task["knowledge_point_id"] for task in detail["tasks"]] == ["401", "402", "403"]
    assert detail["tasks"][0]["reason"] == "先处理确认弱点"
    assert [item["resource_type"] for item in detail["tasks"][0]["learning_bundle"]["items"]] == [
        "code", "doc", "quiz"
    ]
    assert detail["tasks"][0]["learning_bundle"]["teaching_strategy"] == "先代码实验再概念复盘"
    assert detail["tasks"][0]["learning_bundle"]["difficulty"] == "medium"
    assert detail["tasks"][0]["learning_bundle"]["generation_mode"] == "model_generated"
    assert [log.agent_name for log in logs] == [
        "profile",
        "collect_evidence",
        "deterministic_rank",
        "model_plan",
        "review",
        "persist",
    ]
    assert all(log.duration_ms is not None and log.duration_ms >= 0 for log in logs)
    assert len(model.calls) == 1


def test_path_planning_reserves_the_declared_45_second_total_budget() -> None:
    repo = make_repo()
    model = TaskProfilePathModelService()

    detail = as_dict(PathService(repo, model_service=model).generate_path(make_user(), 101))

    assert detail["path"]["plan_json"]["generation_mode"] == "model_generated"
    assert len(model.task_profiles) == 1
    assert model.task_profiles[0].timeout_seconds == 40.0


def test_invalid_structured_path_decision_fails_without_persisting_template_path() -> None:
    repo = make_repo()
    repo.profiles[1].profile_json = {
        "major_background": "计算机专业",
        "learning_preference": "只看代码",
        "learning_goal": "掌握搜索算法",
    }
    model = FakeModelService(
        responses=['{"priority_tasks":[{"task_key":"knowledge:999",'
            '"rationale":"伪造任务","bundle_types":["code","quiz"],"resource_ids":[],'
            '"teaching_strategy":"代码优先","difficulty":"hard",'
            '"learning_problem":"伪造问题","example_direction":"伪造方向",'
            '"used_profile_factor_codes":["major_background"]}]}']
    )

    with pytest.raises(PathValidationError):
        PathService(repo, model_service=model).generate_path(make_user(), 101)

    assert repo.paths == []


def test_path_planning_drops_unknown_factor_codes_without_discarding_safe_model_plan() -> None:
    repo = make_repo()
    model = FakeModelService(
        responses=['{"priority_tasks":[{"task_key":"knowledge:401",'
            '"rationale":"先用合法候选完成学习","bundle_types":["doc","quiz"],"resource_ids":[801],'
            '"teaching_strategy":"先讲解再练习","difficulty":"medium",'
            '"learning_problem":"形成可迁移理解","example_direction":"课程中的搜索示例",'
            '"used_profile_factor_codes":["untrusted_private_factor"]}]}']
    )

    detail = as_dict(PathService(repo, model_service=model).generate_path(make_user(), 101))

    assert detail["path"]["plan_json"]["generation_mode"] == "model_generated"
    assert detail["tasks"][0]["learning_bundle"]["used_profile_factor_codes"] == []
    assert len(model.calls) == 1


@pytest.mark.parametrize(
    ("subject", "course_title", "bundle_types", "strategy", "example_direction"),
    [
        ("计算机科学", "算法设计", ["code", "quiz"], "代码实验后分析复杂度", "工程中的算法实现"),
        ("数学", "线性代数", ["mindmap", "quiz"], "先推导再用图像核对", "向量空间的几何图像"),
        ("英语", "学术英语表达", ["doc", "quiz"], "语义辨析后完成表达练习", "校园交流语境"),
        ("历史", "中国近现代史", ["mindmap", "slide"], "按时间线比较不同观点", "历史事件因果链"),
        ("物理", "用户上传短资料", ["animation", "quiz"], "观察状态变化后解释规律", "无版权力学实验"),
    ],
)
def test_path_planning_uses_current_course_subject_without_builtin_course_assumptions(
    subject: str,
    course_title: str,
    bundle_types: list[str],
    strategy: str,
    example_direction: str,
) -> None:
    repo = make_repo()
    repo.courses[0].subject = subject
    repo.courses[0].title = course_title
    repo.courses[0].source_type = "uploaded"
    repo.knowledge_points[0].title = "当前资料知识点"
    model = FakeModelService(
        responses=[json.dumps(
            {
                "priority_tasks": [
                    {
                        "task_key": "knowledge:401",
                        "rationale": "按当前学科证据安排近期任务",
                        "bundle_types": bundle_types,
                        "resource_ids": [],
                        "teaching_strategy": strategy,
                        "learning_problem": "理解当前资料中的核心关系",
                        "example_direction": example_direction,
                        "difficulty": "medium",
                        "used_profile_factor_codes": [],
                    }
                ]
            },
            ensure_ascii=False,
        )]
    )

    detail = as_dict(PathService(repo, model_service=model).generate_path(make_user(), 101))
    prompt = json.loads(model.calls[0][1]["content"])

    assert prompt["course_state"]["subject"] == subject
    assert prompt["course_state"]["course_title"] == course_title
    assert detail["tasks"][0]["learning_bundle"]["teaching_strategy"] == strategy
    assert [item["resource_type"] for item in detail["tasks"][0]["learning_bundle"]["items"]] == bundle_types
    if subject not in {"计算机科学"}:
        assert "code" not in bundle_types


def test_trusted_profile_weak_point_is_included_in_model_candidates(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = make_repo()
    model = FakeModelService(
        responses=['{"priority_tasks":[{"task_key":"knowledge:403",'
            '"rationale":"针对画像中的明确难点优先复习","bundle_types":["mindmap","quiz"],'
            '"resource_ids":[],"teaching_strategy":"先图解再练习","difficulty":"easy",'
            '"learning_problem":"辨析局部最优","example_direction":"局部搜索轨迹图",'
            '"used_profile_factor_codes":["profile_weak_points"]}]}']
    )
    learner_context = SimpleNamespace(
        global_context=SimpleNamespace(profile_applied_version=1),
        context_hash="profile-weak-point",
        prompt_summary=lambda: {"profile_weak_points": ["局部搜索需要结合案例加强"], "learning_goal": "期末复习"},
        trace_metadata=lambda: {
            "profile_applied_version": 1,
            "personalization_factors": ["profile_weak_points"],
            "profile_context_used": True,
        },
    )
    monkeypatch.setattr(
        "backend.app.agents.path_planning.context_service_from_repository",
        lambda _repository: SimpleNamespace(course_context=lambda _user_id, _course_id: learner_context),
    )

    detail = as_dict(PathService(repo, model_service=model).generate_path(make_user(), 101))

    assert detail["tasks"][0]["knowledge_point_id"] == "403"
    assert detail["tasks"][0]["learning_bundle"]["used_profile_factor_codes"] == ["profile_weak_points"]
    assert "knowledge:403" in model.calls[0][1]["content"]


def test_assessment_replan_preserves_completed_progress_and_does_not_create_missing_path() -> None:
    repo = make_repo()
    service = make_path_service(repo)
    assert service.replan_after_assessment(make_user(), 101, 501).status == "not_started"

    first = service.generate_path(make_user(), 101)
    assert first.path is not None
    old_path_id = int(first.path.id)
    old_tasks = repo.list_tasks_for_path(old_path_id)
    old_tasks[0].status = "completed"
    old_tasks[1].status = "doing"
    next(item for item in repo.weakness_items if item.knowledge_point_id == 403).status = "confirmed"

    replanned = service.replan_after_assessment(make_user(), 101, 501)

    assert replanned.status == "replanned"
    assert replanned.detail is not None
    assert replanned.detail.path is not None
    assert replanned.detail.path.plan_json["trigger"] == "assessment"
    assert replanned.detail.path.plan_json["revision_of"] == str(old_path_id)
    assert replanned.detail.path.goal == "掌握搜索算法"
    assert replanned.detail.path.plan_json["schema_version"] == 5
    assert replanned.detail.tasks[0].status == "completed"
    assert replanned.detail.tasks[0].knowledge_point_id == "402"
    assert any(task.knowledge_point_id == "403" and task.task_type == "review" for task in replanned.detail.tasks)
    assert next(path for path in repo.paths if path.id == old_path_id).status == "archived"


def test_legacy_v2_path_upgrades_on_replan_and_sprint_rows_are_not_current_paths() -> None:
    repo = make_repo()
    legacy = LearningPath(
        id=810,
        user_id=1,
        course_id=101,
        title="旧版普通路径",
        goal="保留旧目标",
        status="active",
        plan_json={"schema_version": 2, "duration_days": 3},
    )
    legacy.created_at = NOW
    legacy.updated_at = NOW
    sprint_history = LearningPath(
        id=811,
        user_id=1,
        course_id=101,
        title="历史冲刺计划",
        goal="历史记录",
        status="sprint_active",
        plan_json={"kind": "exam_sprint", "duration_days": 7},
    )
    sprint_history.created_at = NOW
    sprint_history.updated_at = NOW
    repo.paths.extend([legacy, sprint_history])
    repo.add_task(
        LearningTask(
            path_id=legacy.id,
            user_id=1,
            course_id=101,
            knowledge_point_id=401,
            title="学习启发式搜索",
            task_type="learn",
            reason="旧版任务",
            recommended_resource_ids=[],
            status="completed",
            due_at=NOW,
            next_review_at=None,
        )
    )

    replanned = make_path_service(repo).replan_after_assessment(make_user(), 101, 501)

    assert replanned.detail is not None
    assert replanned.detail.path is not None
    assert replanned.detail.path.plan_json["schema_version"] == 5
    assert replanned.detail.path.plan_json["path_mode"] == "ordered"
    assert "duration_days" not in replanned.detail.path.plan_json
    assert all(task.due_at is None and task.next_review_at is None for task in repo.list_tasks_for_path(int(replanned.detail.path.id)))
    assert sprint_history.status == "sprint_active"
    assert repo.get_active_path(1, 101).id != sprint_history.id

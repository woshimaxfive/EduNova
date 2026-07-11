from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.app.agents.runtime import AgentTraceRecorder
from backend.app.api.v1.deps import get_auth_service
from backend.app.core.config import Settings
from backend.app.core.security import create_access_token
from backend.app.main import create_app
from backend.app.models import (
    AssessmentReport,
    Course,
    GeneratedResource,
    KnowledgePoint,
    LearningPath,
    LearningTask,
    MaterialComparisonRun,
    PracticeAnswer,
    PracticeSession,
    User,
    WeaknessReviewItem,
)
from backend.app.services.auth import AuthService


NOW = datetime(2026, 7, 5, 11, 0, tzinfo=UTC)


@dataclass
class TokenAuthRepository:
    user: User

    def get_user_by_id(self, user_id: int) -> User | None:
        return self.user if self.user.id == user_id else None


@dataclass
class FakeExamSprintRepository:
    courses: list[Course] = field(default_factory=list)
    material_ids_by_course: dict[tuple[int, int], set[int]] = field(default_factory=dict)
    knowledge_points: list[KnowledgePoint] = field(default_factory=list)
    weakness_items: list[WeaknessReviewItem] = field(default_factory=list)
    resources: list[GeneratedResource] = field(default_factory=list)
    practice_sessions: list[PracticeSession] = field(default_factory=list)
    practice_answers: list[PracticeAnswer] = field(default_factory=list)
    reports: list[AssessmentReport] = field(default_factory=list)
    paths: list[LearningPath] = field(default_factory=list)
    tasks: list[LearningTask] = field(default_factory=list)
    comparison_runs: list[MaterialComparisonRun] = field(default_factory=list)
    next_path_id: int = 3001
    next_task_id: int = 4001
    commit_count: int = 0

    def get_course_for_user(self, user_id: int, course_id: int) -> Course | None:
        return next((course for course in self.courses if course.id == course_id and course.owner_id == user_id), None)

    def validate_material_ids(self, user_id: int, course_id: int, material_ids: list[int]) -> bool:
        allowed = self.material_ids_by_course.get((user_id, course_id), set())
        return set(material_ids).issubset(allowed)

    def list_knowledge_points(self, course_id: int) -> list[KnowledgePoint]:
        return sorted(
            [point for point in self.knowledge_points if point.course_id == course_id],
            key=lambda point: (point.order_index, point.id),
        )

    def list_weakness_review_items(self, user_id: int, course_id: int) -> list[WeaknessReviewItem]:
        return sorted(
            [item for item in self.weakness_items if item.user_id == user_id and item.course_id == course_id],
            key=lambda item: (item.updated_at, item.id),
            reverse=True,
        )

    def list_generated_resources(self, user_id: int, course_id: int) -> list[GeneratedResource]:
        return sorted(
            [resource for resource in self.resources if resource.user_id == user_id and resource.course_id == course_id],
            key=lambda resource: (resource.updated_at, resource.id),
            reverse=True,
        )

    def list_practice_answers(self, user_id: int, course_id: int) -> list[PracticeAnswer]:
        session_ids = {
            session.id
            for session in self.practice_sessions
            if session.user_id == user_id and session.course_id == course_id and session.status == "completed"
        }
        return [answer for answer in self.practice_answers if answer.user_id == user_id and answer.session_id in session_ids]

    def get_latest_report(self, user_id: int, course_id: int) -> AssessmentReport | None:
        reports = [report for report in self.reports if report.user_id == user_id and report.course_id == course_id]
        return sorted(reports, key=lambda report: (report.created_at, report.id), reverse=True)[0] if reports else None

    def get_comparison_run_for_user(self, user_id: int, comparison_id: int) -> MaterialComparisonRun | None:
        return next((run for run in self.comparison_runs if run.id == comparison_id and run.user_id == user_id), None)

    def get_current_sprint_path(self, user_id: int, course_id: int) -> LearningPath | None:
        paths = [path for path in self.paths if path.user_id == user_id and path.course_id == course_id and path.status == "sprint_active"]
        return paths[-1] if paths else None

    def archive_active_sprint_paths(self, user_id: int, course_id: int) -> None:
        for path in self.paths:
            if path.user_id == user_id and path.course_id == course_id and path.status == "sprint_active":
                path.status = "sprint_archived"
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

    def get_sprint_path_for_user(self, user_id: int, plan_id: int) -> LearningPath | None:
        return next(
            (
                path
                for path in self.paths
                if path.id == plan_id and path.user_id == user_id and path.status in {"sprint_active", "sprint_archived"}
            ),
            None,
        )

    def get_sprint_task_for_user(self, user_id: int, plan_id: int, task_id: int) -> LearningTask | None:
        return next((task for task in self.tasks if task.id == task_id and task.path_id == plan_id and task.user_id == user_id), None)

    def list_tasks_for_path(self, path_id: int) -> list[LearningTask]:
        return sorted([task for task in self.tasks if task.path_id == path_id], key=lambda task: (task.due_at or NOW, task.id))

    def commit(self) -> None:
        self.commit_count += 1

    def rollback(self) -> None:
        return None

    def refresh(self, _instance: object) -> None:
        return None


def make_user(user_id: int = 1) -> User:
    return User(
        id=user_id,
        email=f"user{user_id}@edunova.local",
        hashed_password="not-used",
        display_name=f"学生 {user_id}",
        role="student",
        starter_mode="blank",
    )


def make_course(course_id: int = 101, owner_id: int = 1) -> Course:
    return Course(
        id=course_id,
        owner_id=owner_id,
        title="人工智能导论",
        description="课程资料",
        subject="人工智能",
        source_type="uploaded",
        visibility="private",
        status="ready",
    )


def make_point(point_id: int, title: str, order_index: int, course_id: int = 101) -> KnowledgePoint:
    return KnowledgePoint(
        id=point_id,
        course_id=course_id,
        title=title,
        summary=f"{title} 的课程摘要，包含关键概念、常见误区和复习线索。",
        chapter="第一章",
        order_index=order_index,
        difficulty=None,
        prerequisites_json=[],
    )


def make_weakness(item_id: int, status: str, point_id: int, title: str, user_id: int = 1) -> WeaknessReviewItem:
    item = WeaknessReviewItem(
        id=item_id,
        user_id=user_id,
        course_id=101,
        knowledge_point_id=point_id,
        title=title,
        source_type="practice_assessment" if status == "confirmed" else "course_question",
        status=status,
        recommended_resource_ids=[],
        next_review_at=None,
    )
    item.created_at = NOW
    item.updated_at = NOW
    return item


def make_resource(resource_id: int, point_id: int, title: str, user_id: int = 1, course_id: int = 101) -> GeneratedResource:
    return GeneratedResource(
        id=resource_id,
        user_id=user_id,
        course_id=course_id,
        knowledge_point_id=point_id,
        resource_type="doc",
        title=title,
        content_json={"markdown": "安全资源摘要", "metadata": {"generation_mode": "deterministic_source"}},
        citation_json=[],
        status="completed",
        review_status="passed",
        confidence_score=Decimal("0.86"),
        created_at=NOW,
        updated_at=NOW,
    )


def make_practice_low_score() -> tuple[PracticeSession, PracticeAnswer]:
    session = PracticeSession(
        id=501,
        user_id=1,
        course_id=101,
        title="人工智能导论 练习",
        status="completed",
        score=Decimal("45"),
        created_at=NOW,
        updated_at=NOW,
    )
    answer = PracticeAnswer(
        id=601,
        session_id=501,
        user_id=1,
        question_json={
            "id": "q1",
            "knowledge_point_id": "402",
            "knowledge_point_title": "启发式搜索",
            "prompt": "安全题干",
        },
        answer_text="这是不应出现在冲刺计划里的完整原始答案",
        feedback_json={"score": 20, "message": "需要复习"},
        is_correct=False,
        created_at=NOW,
    )
    return session, answer


def make_report() -> AssessmentReport:
    return AssessmentReport(
        id=701,
        user_id=1,
        course_id=101,
        practice_session_id=501,
        report_json={
            "weakness_list": [{"knowledge_point_id": "402", "title": "启发式搜索", "source_type": "practice_assessment"}],
            "next_step_suggestions": ["先处理启发式搜索，再回看课程引用。"],
            "evidence_refs": [{"practice_answer_id": "601", "knowledge_point_id": "402", "score": 20}],
        },
        score=Decimal("45"),
        created_at=NOW,
    )


def make_repo() -> FakeExamSprintRepository:
    session, answer = make_practice_low_score()
    return FakeExamSprintRepository(
        courses=[make_course(), make_course(202, owner_id=2)],
        material_ids_by_course={(1, 101): {201, 202}},
        knowledge_points=[
            make_point(401, "人工智能概述", 0),
            make_point(402, "启发式搜索", 1),
            make_point(403, "神经网络基础", 2),
        ],
        weakness_items=[
            make_weakness(801, "reviewing", 402, "启发式搜索"),
            make_weakness(802, "pending", 403, "神经网络基础"),
            make_weakness(803, "confirmed", 401, "人工智能概述", user_id=2),
        ],
        resources=[make_resource(901, 402, "启发式搜索讲解"), make_resource(902, 401, "人工智能概述速查")],
        practice_sessions=[session],
        practice_answers=[answer],
        reports=[make_report()],
    )


def as_dict(model: Any) -> dict[str, Any]:
    return model.model_dump() if hasattr(model, "model_dump") else model


def make_trace_recorder(logs: list[Any]) -> AgentTraceRecorder:
    return AgentTraceRecorder(repository_add_log=lambda log: logs.append(log) or log)


def test_generate_exam_sprint_plan_persists_without_archiving_normal_path_and_uses_evidence() -> None:
    from backend.app.services.exam_sprint import ExamSprintService

    normal_path = LearningPath(id=1001, user_id=1, course_id=101, title="普通路径", goal="普通目标", status="active", plan_json={})
    old_sprint = LearningPath(
        id=1002,
        user_id=1,
        course_id=101,
        title="旧冲刺",
        goal="旧冲刺目标",
        status="sprint_active",
        plan_json={"kind": "exam_sprint"},
    )
    normal_path.created_at = old_sprint.created_at = NOW
    normal_path.updated_at = old_sprint.updated_at = NOW
    repo = make_repo()
    repo.paths.extend([normal_path, old_sprint])
    service = ExamSprintService(repo)

    result = as_dict(service.generate_plan(make_user(), course_id=101, duration_days=7, material_ids=[201], goal="期末 80 分"))

    assert normal_path.status == "active"
    assert old_sprint.status == "sprint_archived"
    assert result["status"] == "sprint_active"
    assert result["duration_days"] == 7
    assert result["goal"] == "期末 80 分"
    assert repo.paths[-1].plan_json["kind"] == "exam_sprint"
    assert repo.paths[-1].status == "sprint_active"
    assert repo.tasks
    assert repo.tasks[0].status == "doing"
    assert all(task.status == "todo" for task in repo.tasks[1:])
    assert result["weak_points"][0]["title"] == "启发式搜索"
    assert result["high_frequency_points"][0]["title"] == "启发式搜索"
    assert result["recommended_resources"][0]["title"] == "启发式搜索讲解"
    assert result["evidence_summary"]["practice_low_score_count"] == 1
    serialized = str(result) + str(repo.paths[-1].plan_json)
    assert "这是不应出现在冲刺计划里的完整原始答案" not in serialized
    assert "完整资料原文" not in serialized
    assert "系统提示词" not in serialized
    assert "模型输入" not in serialized
    assert "API Key" not in serialized


def test_exam_sprint_validates_scope_materials_duration_and_empty_points() -> None:
    from backend.app.services.exam_sprint import ExamSprintNotFoundError, ExamSprintService, ExamSprintValidationError

    repo = make_repo()
    service = ExamSprintService(repo)

    with pytest.raises(ExamSprintNotFoundError):
        service.generate_plan(make_user(), course_id=202, duration_days=7, material_ids=[], goal="")

    with pytest.raises(ExamSprintNotFoundError):
        service.generate_plan(make_user(), course_id=101, duration_days=7, material_ids=[999], goal="")

    with pytest.raises(ExamSprintValidationError):
        service.generate_plan(make_user(), course_id=101, duration_days=5, material_ids=[], goal="")

    repo.knowledge_points = []
    with pytest.raises(ExamSprintValidationError):
        service.generate_plan(make_user(), course_id=101, duration_days=7, material_ids=[], goal="")


def test_get_exam_sprint_plan_is_user_scoped() -> None:
    from backend.app.services.exam_sprint import ExamSprintNotFoundError, ExamSprintService

    repo = make_repo()
    service = ExamSprintService(repo)
    created = as_dict(service.generate_plan(make_user(), course_id=101, duration_days=3, material_ids=[], goal=""))

    detail = as_dict(service.get_plan(make_user(), int(created["id"])))

    assert detail["id"] == created["id"]
    assert detail["daily_tasks"][0]["day_index"] == 1

    with pytest.raises(ExamSprintNotFoundError):
        service.get_plan(make_user(2), int(created["id"]))


def test_exam_sprint_routes_require_login_and_return_envelopes() -> None:
    from backend.app.api.v1.exam_sprint import get_exam_sprint_service
    from backend.app.services.exam_sprint import ExamSprintService

    repo = make_repo()
    user = make_user()
    settings = Settings(_env_file=None, jwt_secret="exam-sprint-secret-with-32-bytes-long", jwt_expire_minutes=30)
    app = create_app()
    app.dependency_overrides[get_auth_service] = lambda: AuthService(repository=TokenAuthRepository(user), settings=settings)
    app.dependency_overrides[get_exam_sprint_service] = lambda: ExamSprintService(repo)
    client = TestClient(app)
    token = create_access_token(str(user.id), settings=settings)
    headers = {"Authorization": f"Bearer {token}"}

    unauthorized = client.post("/api/v1/exam-sprint/plans", json={"course_id": 101, "duration_days": 7})
    generated = client.post(
        "/api/v1/exam-sprint/plans",
        headers=headers,
        json={"course_id": 101, "duration_days": 14, "material_ids": [201], "goal": "期末冲刺"},
    )
    plan_id = generated.json()["data"]["id"]
    detail = client.get(f"/api/v1/exam-sprint/plans/{plan_id}", headers=headers)
    current = client.get("/api/v1/exam-sprint/plans/current?course_id=101", headers=headers)
    missing = client.get("/api/v1/exam-sprint/plans/999999", headers=headers)

    assert unauthorized.status_code == 401
    assert generated.status_code == 200
    assert generated.json()["data"]["duration_days"] == 14
    assert generated.json()["data"]["daily_tasks"]
    assert detail.status_code == 200
    assert detail.json()["data"]["id"] == plan_id
    assert current.status_code == 200
    assert current.json()["data"]["id"] == plan_id
    assert missing.status_code == 404


def test_exam_sprint_graph_consumes_comparison_and_replans_only_selected_sprint() -> None:
    from backend.app.services.exam_sprint import ExamSprintService

    repo = make_repo()
    comparison = MaterialComparisonRun(
        id=1201,
        user_id=1,
        course_id=101,
        material_ids_json=[201, 202],
        result_json={
            "priority_order": [{"knowledge_point_id": "403", "title": "神经网络基础"}],
            "exam_likely_points": [{"knowledge_point_id": "403", "title": "神经网络基础"}],
            "repeated_concepts": [],
            "missing_review_points": [],
        },
        agent_trace_id="trace_comparison",
        generation_mode="deterministic_source",
        review_mode="rules_only",
        created_at=NOW,
    )
    repo.comparison_runs.append(comparison)
    logs: list[Any] = []
    service = ExamSprintService(repo, trace_recorder=make_trace_recorder(logs))

    created = as_dict(
        service.generate_plan(
            make_user(),
            course_id=101,
            duration_days=3,
            material_ids=[201, 202],
            comparison_id=1201,
            goal="三天冲刺",
        )
    )
    practice_task = next(task for task in repo.tasks if task.path_id == int(created["id"]) and task.task_type == "sprint_practice")
    result = service.replan_after_assessment(make_user(), 101, 9001, int(created["id"]), practice_task.id)

    assert created["comparison_id"] == "1201"
    assert "神经网络基础" in [point["title"] for point in created["high_frequency_points"]]
    assert result.status == "replanned"
    assert result.detail is not None
    replanned = as_dict(result.detail)
    assert replanned["trigger"] == "assessment_reflow"
    assert replanned["revision_of"] == created["id"]
    assert replanned["preserved_task_count"] >= 1
    assert repo.get_sprint_path_for_user(1, int(created["id"])).status == "sprint_archived"
    assert [log.agent_name for log in logs[:8]] == [
        "profile",
        "collect_evidence",
        "comparison_context",
        "deterministic_rank",
        "model_plan",
        "build_tasks",
        "review",
        "persist",
    ]


def test_exam_sprint_reflow_commits_source_task_before_graph_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.app.agents.exam_sprint import ExamSprintGraphRunner
    from backend.app.services.exam_sprint import ExamSprintService

    repo = make_repo()
    service = ExamSprintService(repo)
    created = as_dict(service.generate_plan(make_user(), 101, 3, goal="冲刺"))
    practice_task = next(task for task in repo.tasks if task.path_id == int(created["id"]) and task.task_type == "sprint_practice")
    commits_before_reflow = repo.commit_count

    def fail_replan(self: ExamSprintGraphRunner, **_kwargs: Any) -> None:
        raise RuntimeError("replan failed")

    monkeypatch.setattr(ExamSprintGraphRunner, "run", fail_replan)

    with pytest.raises(RuntimeError, match="replan failed"):
        service.replan_after_assessment(make_user(), 101, 9001, int(created["id"]), practice_task.id)

    assert practice_task.status == "completed"
    assert repo.commit_count == commits_before_reflow + 1
    assert repo.get_sprint_path_for_user(1, int(created["id"])).status == "sprint_active"

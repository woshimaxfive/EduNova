from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.agents.runtime import AgentTraceRecorder
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
from backend.app.schemas.paths import (
    LearningPathDetail,
    PathEvidenceSummary,
    PathTaskStatus,
    task_to_api,
    path_to_api,
)
from backend.app.schemas.personalization import PersonalizationFreshnessResponse
from backend.app.services.learner_context import context_service_from_repository


class PathNotFoundError(Exception):
    pass


class PathValidationError(Exception):
    pass


class PathModelService(Protocol):
    def chat_completion(self, user: User, messages: list[dict[str, str]]) -> str: ...


class PathRepository(Protocol):
    def get_course_for_user(self, user_id: int, course_id: int) -> Course | None: ...

    def list_knowledge_points(self, course_id: int) -> list[KnowledgePoint]: ...

    def get_profile(self, user_id: int) -> StudentProfile | None: ...

    def list_weakness_review_items(self, user_id: int, course_id: int) -> list[WeaknessReviewItem]: ...

    def list_generated_resources(self, user_id: int, course_id: int) -> list[GeneratedResource]: ...

    def get_active_path(self, user_id: int, course_id: int) -> LearningPath | None: ...

    def list_tasks_for_path(self, path_id: int) -> list[LearningTask]: ...

    def archive_active_paths(self, user_id: int, course_id: int) -> None: ...

    def add_path(self, path: LearningPath) -> LearningPath: ...

    def add_task(self, task: LearningTask) -> LearningTask: ...

    def get_task_for_user(self, user_id: int, task_id: int) -> LearningTask | None: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...

    def refresh(self, instance: object) -> None: ...


class SqlAlchemyPathRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_course_for_user(self, user_id: int, course_id: int) -> Course | None:
        return self.db.scalar(select(Course).where(Course.id == course_id, Course.owner_id == user_id))

    def list_knowledge_points(self, course_id: int) -> list[KnowledgePoint]:
        return list(
            self.db.scalars(
                select(KnowledgePoint).where(KnowledgePoint.course_id == course_id).order_by(KnowledgePoint.order_index, KnowledgePoint.id)
            )
        )

    def get_profile(self, user_id: int) -> StudentProfile | None:
        return self.db.scalar(select(StudentProfile).where(StudentProfile.user_id == user_id))

    def list_weakness_review_items(self, user_id: int, course_id: int) -> list[WeaknessReviewItem]:
        return list(
            self.db.scalars(
                select(WeaknessReviewItem)
                .where(WeaknessReviewItem.user_id == user_id, WeaknessReviewItem.course_id == course_id)
                .order_by(WeaknessReviewItem.created_at.desc(), WeaknessReviewItem.id.desc())
            )
        )

    def list_generated_resources(self, user_id: int, course_id: int) -> list[GeneratedResource]:
        return list(
            self.db.scalars(
                select(GeneratedResource)
                .where(GeneratedResource.user_id == user_id, GeneratedResource.course_id == course_id)
                .order_by(GeneratedResource.updated_at.desc(), GeneratedResource.id.desc())
            )
        )

    def get_active_path(self, user_id: int, course_id: int) -> LearningPath | None:
        return self.db.scalar(
            select(LearningPath)
            .where(LearningPath.user_id == user_id, LearningPath.course_id == course_id, LearningPath.status == "active")
            .order_by(LearningPath.updated_at.desc(), LearningPath.id.desc())
        )

    def list_tasks_for_path(self, path_id: int) -> list[LearningTask]:
        return list(
            self.db.scalars(
                select(LearningTask)
                .where(LearningTask.path_id == path_id)
                .order_by(LearningTask.id.asc())
            )
        )

    def archive_active_paths(self, user_id: int, course_id: int) -> None:
        for path in self.db.scalars(
            select(LearningPath).where(LearningPath.user_id == user_id, LearningPath.course_id == course_id, LearningPath.status == "active")
        ):
            path.status = "archived"
            path.updated_at = datetime.now(UTC)

    def add_path(self, path: LearningPath) -> LearningPath:
        self.db.add(path)
        self.db.flush()
        return path

    def add_task(self, task: LearningTask) -> LearningTask:
        self.db.add(task)
        self.db.flush()
        return task

    def get_task_for_user(self, user_id: int, task_id: int) -> LearningTask | None:
        return self.db.scalar(select(LearningTask).where(LearningTask.id == task_id, LearningTask.user_id == user_id))

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()

    def refresh(self, instance: object) -> None:
        self.db.refresh(instance)


@dataclass(frozen=True)
class PlannedTask:
    title: str
    task_type: str
    knowledge_point_id: int | None
    reason: str
    resource_ids: list[int]
    bundle_types: tuple[str, ...] = ()
    status: str = "todo"


@dataclass(frozen=True)
class PathReplanResult:
    status: str
    trace_id: str | None
    detail: LearningPathDetail | None
    preserved_task_count: int = 0


class PathService:
    valid_statuses = {"todo", "doing", "completed"}

    def __init__(
        self,
        repository: PathRepository,
        model_service: PathModelService | None = None,
        trace_recorder: AgentTraceRecorder | None = None,
    ) -> None:
        self.repository = repository
        self.model_service = model_service
        self.trace_recorder = trace_recorder

    def generate_path(self, user: User, course_id: int) -> LearningPathDetail:
        from backend.app.agents.path_planning import PathPlanningGraphRunner

        return PathPlanningGraphRunner(self).run(
            user=user,
            course_id=course_id,
            trigger="manual",
        ).detail  # type: ignore[return-value]

    def replan_after_assessment(self, user: User, course_id: int, assessment_session_id: int) -> PathReplanResult:
        active_path = self.repository.get_active_path(user.id, course_id)
        if active_path is None:
            return PathReplanResult(status="not_started", trace_id=None, detail=None)
        from backend.app.agents.path_planning import PathPlanningGraphRunner

        return PathPlanningGraphRunner(self).run(
            user=user,
            course_id=course_id,
            goal=active_path.goal or "",
            trigger="assessment",
            assessment_session_id=assessment_session_id,
            previous_path=active_path,
        )

    def get_current_path(self, user: User, course_id: int) -> LearningPathDetail:
        course = self._require_course(user, course_id)
        knowledge_points = self.repository.list_knowledge_points(course.id)
        weakness_items = self.repository.list_weakness_review_items(user.id, course.id)
        resources = self.repository.list_generated_resources(user.id, course.id)
        path = self.repository.get_active_path(user.id, course.id)
        if path is None:
            return LearningPathDetail(
                course_id=str(course.id),
                status="not_started",
                message="学习路径尚未生成。",
                agent_trace_id=None,
                path=None,
                tasks=[],
                evidence_summary=self._build_evidence(knowledge_points, weakness_items, resources),
            )
        return self._build_detail(user, course, path, self.repository.list_tasks_for_path(path.id), resources, knowledge_points, weakness_items)

    def update_task_status(self, user: User, task_id: int, status: PathTaskStatus | str) -> object:
        if status not in self.valid_statuses:
            raise PathValidationError("任务状态只能是 todo、doing 或 completed。")
        task = self.repository.get_task_for_user(user.id, task_id)
        if task is None:
            raise PathNotFoundError("学习任务不存在或无权访问。")
        resources = self.repository.list_generated_resources(user.id, int(task.course_id or 0))
        resources_by_id = {resource.id: resource for resource in resources}
        try:
            task.status = str(status)
            task.updated_at = datetime.now(UTC)
            self.repository.commit()
            self.repository.refresh(task)
        except Exception:
            self.repository.rollback()
            raise
        return task_to_api(task, resources_by_id)

    def _require_course(self, user: User, course_id: int) -> Course:
        course = self.repository.get_course_for_user(user.id, course_id)
        if course is None:
            raise PathNotFoundError("课程不存在或无权访问。")
        return course

    def _build_planned_tasks(
        self,
        knowledge_points: list[KnowledgePoint],
        weakness_items: list[WeaknessReviewItem],
        resources: list[GeneratedResource],
    ) -> list[PlannedTask]:
        point_by_id = {point.id: point for point in knowledge_points}
        covered_point_ids: set[int] = set()
        planned: list[PlannedTask] = []
        weakness_priority = {"reviewing": 0, "confirmed": 1}
        for item in sorted(weakness_items, key=lambda value: (weakness_priority.get(value.status, 9), value.created_at, value.id)):
            point = point_by_id.get(item.knowledge_point_id or -1)
            title = point.title if point is not None else item.title
            planned.append(
                PlannedTask(
                    title=f"复习{title}",
                    task_type="review",
                    knowledge_point_id=point.id if point is not None else item.knowledge_point_id,
                    reason="来自已确认或复习中的课程薄弱点",
                    resource_ids=self._recommend_resource_ids(resources, item.knowledge_point_id, title),
                )
            )
            if item.knowledge_point_id is not None:
                covered_point_ids.add(item.knowledge_point_id)

        for point in knowledge_points:
            if point.id in covered_point_ids:
                continue
            planned.append(
                PlannedTask(
                    title=f"学习{point.title}",
                    task_type="learn",
                    knowledge_point_id=point.id,
                    reason="来自课程知识点顺序和当前路径覆盖缺口",
                    resource_ids=self._recommend_resource_ids(resources, point.id, point.title),
                )
            )
        if not planned:
            planned.append(
                PlannedTask(
                    title="整理课程资料并生成第一批学习资源",
                    task_type="resource",
                    knowledge_point_id=None,
                    reason="当前课程暂无可排序知识点，先补齐资料和资源依据",
                    resource_ids=self._recommend_resource_ids(resources, None, ""),
                )
            )
        return planned

    def _build_detail(
        self,
        user: User,
        course: Course,
        path: LearningPath,
        tasks: list[LearningTask],
        resources: list[GeneratedResource],
        knowledge_points: list[KnowledgePoint],
        weakness_items: list[WeaknessReviewItem],
    ) -> LearningPathDetail:
        resources_by_id = {resource.id: resource for resource in resources}
        trigger = str((path.plan_json or {}).get("trigger") or "manual")
        return LearningPathDetail(
            course_id=str(course.id),
            status=path.status,
            message=(
                "已根据练习结果更新学习路径。"
                if path.status == "active" and trigger == "assessment"
                else ("当前学习路径进行中。" if path.status == "active" else "学习路径已归档。")
            ),
            agent_trace_id=getattr(path, "agent_trace_id", None),
            path=path_to_api(path, self._path_freshness(user.id, path)),
            tasks=[task_to_api(task, resources_by_id) for task in tasks],
            evidence_summary=self._build_evidence(knowledge_points, weakness_items, resources),
        )

    def _path_freshness(
        self,
        user_id: int,
        path: LearningPath,
    ) -> PersonalizationFreshnessResponse | None:
        context_service = context_service_from_repository(self.repository)
        if context_service is None:
            return None
        freshness = context_service.freshness(
            path.plan_json or {},
            context_service.global_context(user_id).profile_applied_version,
        )
        return PersonalizationFreshnessResponse(**freshness.to_dict())

    @staticmethod
    def _build_evidence(
        knowledge_points: list[KnowledgePoint],
        weakness_items: list[WeaknessReviewItem],
        resources: list[GeneratedResource],
    ) -> PathEvidenceSummary:
        active_count = sum(1 for item in weakness_items if item.status in {"confirmed", "reviewing"})
        pending_count = sum(1 for item in weakness_items if item.status == "pending")
        return PathEvidenceSummary(
            knowledge_point_count=len(knowledge_points),
            confirmed_or_reviewing_weakness_count=active_count,
            pending_weakness_count=pending_count,
            resource_count=len(resources),
            basis=[
                f"课程知识点 {len(knowledge_points)} 个。",
                f"已确认或复习中的薄弱点 {active_count} 个。",
                f"可推荐课程资源 {len(resources)} 个。",
            ],
        )

    @staticmethod
    def _recommend_resource_ids(resources: list[GeneratedResource], knowledge_point_id: int | None, title: str) -> list[int]:
        title_key = " ".join(title.split()).casefold()
        matched: list[GeneratedResource] = []
        if knowledge_point_id is not None:
            matched.extend([resource for resource in resources if resource.knowledge_point_id == knowledge_point_id])
            if matched:
                return [resource.id for resource in matched[:3]]
        if len(matched) < 3 and title_key:
            matched.extend(
                [
                    resource
                    for resource in resources
                    if resource not in matched and title_key in " ".join(resource.title.split()).casefold()
                ]
            )
        if len(matched) < 3 and knowledge_point_id is None:
            matched.extend([resource for resource in resources if resource not in matched])
        return [resource.id for resource in matched[:3]]

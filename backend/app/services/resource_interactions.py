from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.errors import NotFoundDomainError, ValidationDomainError
from backend.app.models import GeneratedResource, LearningPath, LearningTask, ResourceInteraction, User
from backend.app.schemas.resources import ResourceInteractionRequest, ResourceLearningStateResponse
from backend.app.services.task_resource_binding import binding_status, exact_item, resource_snapshot


class ResourceInteractionNotFoundError(NotFoundDomainError):
    pass


class ResourceInteractionValidationError(ValidationDomainError):
    pass


class ResourceInteractionService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def record(
        self,
        user: User,
        resource_id: int,
        payload: ResourceInteractionRequest,
    ) -> ResourceLearningStateResponse:
        resource = self._resource(user.id, resource_id, for_update=True)
        existing = self.db.scalar(
            select(ResourceInteraction).where(
                ResourceInteraction.user_id == user.id,
                ResourceInteraction.event_id == payload.event_id,
            )
        )
        if existing is not None:
            if (existing.resource_id != resource.id or existing.path_task_id != payload.path_task_id
                    or existing.event_type != payload.event_type or existing.progress_percent != payload.progress_percent
                    or existing.feedback != payload.feedback):
                raise ResourceInteractionValidationError("event_id 已用于不同资源、任务或活动内容。")
            result = self.state(user, resource_id, payload.path_task_id)
            self.db.rollback()
            return result

        task = self._task(user.id, resource, payload.path_task_id)
        interaction = ResourceInteraction(
            event_id=payload.event_id,
            user_id=user.id,
            course_id=resource.course_id,
            resource_id=resource.id,
            path_task_id=task.id if task is not None else None,
            event_type=payload.event_type,
            progress_percent=payload.progress_percent,
            feedback=payload.feedback,
            evidence_json={"schema_version": 1, "kind": "resource_activity", "path_id": task.path_id if task else None,
                           "task_id": task.id if task else None, "resource": resource_snapshot(resource),
                           "binding_status": binding_status(task, exact_item(task, resource.id) or {}, resource) if task else "standalone",
                           "mastery_claim": False},
        )
        self.db.add(interaction)
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return self.state(user, resource_id, payload.path_task_id)

    def state(self, user: User, resource_id: int, path_task_id: int | None = None) -> ResourceLearningStateResponse:
        resource = self._resource(user.id, resource_id)
        events = list(
            self.db.scalars(
                select(ResourceInteraction)
                .where(ResourceInteraction.user_id == user.id, ResourceInteraction.resource_id == resource.id)
                .order_by(ResourceInteraction.created_at, ResourceInteraction.id)
            )
        )
        progress = 0
        feedback = None
        events = [event for event in events if event.path_task_id == path_task_id]
        for event in events:
            if event.progress_percent is not None:
                progress = max(progress, event.progress_percent)
            if event.feedback is not None:
                feedback = event.feedback
        completed = any(event.event_type == "completed" for event in events)
        if completed:
            progress = 100
        return ResourceLearningStateResponse(
            resource_id=str(resource.id),
            path_task_id=str(path_task_id) if path_task_id is not None else None,
            evidence=[event.evidence_json or {"binding_status": "legacy_unverified"} for event in events],
            opened=any(event.event_type == "opened" for event in events),
            started=any(event.event_type == "started" for event in events),
            completed=completed,
            progress_percent=progress,
            feedback=feedback,
            event_count=len(events),
            updated_at=(events[-1].created_at.isoformat() if events else None),
        )

    def _resource(self, user_id: int, resource_id: int, *, for_update: bool = False) -> GeneratedResource:
        statement = select(GeneratedResource).where(
                GeneratedResource.id == resource_id,
                GeneratedResource.user_id == user_id,
            )
        if for_update:
            statement = statement.with_for_update().execution_options(populate_existing=True)
        resource = self.db.scalar(statement)
        if resource is None:
            raise ResourceInteractionNotFoundError("资源不存在或无权访问。")
        return resource

    def _task(
        self,
        user_id: int,
        resource: GeneratedResource,
        path_task_id: int | None,
    ) -> LearningTask | None:
        if path_task_id is None:
            return None
        task = self.db.scalar(
            select(LearningTask).where(LearningTask.id == path_task_id, LearningTask.user_id == user_id)
        )
        if task is None or task.course_id != resource.course_id:
            raise ResourceInteractionValidationError("资源与学习路径任务不属于同一课程。")
        if self.db.scalar(select(LearningPath.id).where(LearningPath.id == task.path_id, LearningPath.status == "draft")) is not None:
            raise ResourceInteractionValidationError("请先确认计划，再记录草稿任务活动。")
        item = exact_item(task, resource.id)
        if item is None or binding_status(task, item, resource) not in {"verified", "legacy_unverified"}:
            raise ResourceInteractionValidationError("该资源未关联到指定学习路径任务。")
        return task

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.models import (
    AiJob,
    ChatMessage,
    KnowledgeChunk,
    Course,
    CourseEnrollment,
    GeneratedResource,
    KnowledgePoint,
    LearningPath,
    LearningTask,
    Material,
    PracticeSession,
    User,
)
from backend.app.services.ai_job_contracts import ACTIVE_STATUSES


class SqlAlchemyAiJobRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_user(self, user_id: int) -> User | None:
        return self.db.get(User, user_id)

    def committed_pilot_artifacts(self, job: AiJob):
        """Find domain commits even if a worker died before writing its job result."""
        model = LearningPath if job.workflow == "path_planning" else GeneratedResource
        return list(self.db.scalars(select(model).where(
            model.user_id == job.user_id, model.course_id == job.course_id,
            model.agent_trace_id == job.agent_trace_id,
        ).order_by(model.id)))

    def lock_user(self, user_id: int) -> User | None:
        return self.db.scalar(select(User).where(User.id == user_id).with_for_update())

    def get_job(self, job_id: int, *, for_update: bool = False) -> AiJob | None:
        statement = select(AiJob).where(AiJob.id == job_id).execution_options(populate_existing=True)
        if for_update:
            statement = statement.with_for_update()
        return self.db.scalar(statement)

    def get_job_for_user(self, user_id: int, job_id: int, *, for_update: bool = False) -> AiJob | None:
        statement = (
            select(AiJob)
            .where(AiJob.id == job_id, AiJob.user_id == user_id)
            .execution_options(populate_existing=True)
        )
        if for_update:
            statement = statement.with_for_update()
        return self.db.scalar(statement)

    def get_by_idempotency(self, user_id: int, idempotency_key: str) -> AiJob | None:
        return self.db.scalar(
            select(AiJob).where(AiJob.user_id == user_id, AiJob.idempotency_key == idempotency_key)
        )

    def count_active(self, user_id: int) -> int:
        return int(
            self.db.scalar(
                select(func.count(AiJob.id)).where(AiJob.user_id == user_id, AiJob.status.in_(ACTIVE_STATUSES))
            )
            or 0
        )

    def list_jobs(self, user_id: int, statuses: set[str] | None, limit: int) -> list[AiJob]:
        statement = select(AiJob).where(AiJob.user_id == user_id)
        if statuses:
            statement = statement.where(AiJob.status.in_(statuses))
        return list(self.db.scalars(statement.order_by(AiJob.updated_at.desc(), AiJob.id.desc()).limit(limit)))

    def get_course_for_user(self, user_id: int, course_id: int) -> Course | None:
        return self.db.scalar(select(Course).where(Course.id == course_id, Course.owner_id == user_id))

    def is_course_active(self, user_id: int, course_id: int) -> bool:
        return self.db.scalar(select(CourseEnrollment.id).where(
            CourseEnrollment.user_id == user_id,
            CourseEnrollment.course_id == course_id,
            CourseEnrollment.learning_status == "active",
        )) is not None

    def get_active_path_job(self, user_id: int, course_id: int) -> AiJob | None:
        return self.db.scalar(
            select(AiJob)
            .where(
                AiJob.user_id == user_id,
                AiJob.course_id == course_id,
                AiJob.workflow == "path_planning",
                AiJob.status.in_(ACTIVE_STATUSES),
            )
            .order_by(AiJob.updated_at.desc(), AiJob.id.desc())
        )

    def get_active_workflow_job(self, user_id: int, course_id: int, workflow: str) -> AiJob | None:
        return self.db.scalar(
            select(AiJob)
            .where(
                AiJob.user_id == user_id,
                AiJob.course_id == course_id,
                AiJob.workflow == workflow,
                AiJob.status.in_(ACTIVE_STATUSES),
            )
            .order_by(AiJob.updated_at.desc(), AiJob.id.desc())
        )

    def get_practice_session_for_user(self, user_id: int, session_id: int) -> PracticeSession | None:
        return self.db.scalar(
            select(PracticeSession).where(
                PracticeSession.id == session_id,
                PracticeSession.user_id == user_id,
            )
        )

    def get_active_resource_job_for_path_task(self, user_id: int, path_task_id: int) -> AiJob | None:
        return self.db.scalar(
            select(AiJob)
            .where(
                AiJob.user_id == user_id,
                AiJob.workflow == "resource_generation",
                AiJob.status.in_(ACTIVE_STATUSES),
                AiJob.request_json["path_task_id"].as_integer() == path_task_id,
            )
            .order_by(AiJob.updated_at.desc(), AiJob.id.desc())
        )

    def get_active_learning_path(self, user_id: int, course_id: int) -> LearningPath | None:
        return self.db.scalar(
            select(LearningPath)
            .where(
                LearningPath.user_id == user_id,
                LearningPath.course_id == course_id,
                LearningPath.status == "active",
            )
            .order_by(LearningPath.updated_at.desc(), LearningPath.id.desc())
        )

    def get_materials_for_user(self, user_id: int, material_ids: list[int]) -> list[Material]:
        if not material_ids:
            return []
        return list(self.db.scalars(select(Material).where(Material.user_id == user_id, Material.id.in_(material_ids))))

    def get_knowledge_point(self, course_id: int, knowledge_point_id: int) -> KnowledgePoint | None:
        return self.db.scalar(
            select(KnowledgePoint).where(
                KnowledgePoint.id == knowledge_point_id,
                KnowledgePoint.course_id == course_id,
            )
        )

    def get_resource_for_user(self, user_id: int, resource_id: int) -> GeneratedResource | None:
        return self.db.scalar(
            select(GeneratedResource).where(
                GeneratedResource.id == resource_id,
                GeneratedResource.user_id == user_id,
            )
        )

    def get_learning_task_for_user(self, user_id: int, task_id: int) -> LearningTask | None:
        return self.db.scalar(
            select(LearningTask).where(LearningTask.id == task_id, LearningTask.user_id == user_id)
        )

    def add(self, job: AiJob) -> AiJob:
        self.db.add(job)
        self.db.flush()
        return job

    def is_path_draft(self, path_id: int) -> bool:
        return self.db.scalar(select(LearningPath.id).where(
            LearningPath.id == path_id, LearningPath.status == "draft",
        )) is not None

    def has_message_for_user(self, user_id: int, message_id: int) -> bool:
        return self.db.scalar(select(ChatMessage.id).where(
            ChatMessage.id == message_id, ChatMessage.user_id == user_id,
        )) is not None

    def has_course_chunks(self, course_id: int, chunk_ids: list[int]) -> bool:
        found = set(self.db.scalars(select(KnowledgeChunk.id).where(
            KnowledgeChunk.course_id == course_id, KnowledgeChunk.id.in_(chunk_ids),
        )))
        return found == set(chunk_ids)

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()

    def refresh(self, instance: object) -> None:
        self.db.refresh(instance)

    def delete(self, job: AiJob) -> None:
        self.db.delete(job)

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.models import (
    AgentRunLog,
    Course,
    GeneratedResource,
    KnowledgeChunk,
    KnowledgePoint,
    LearningTask,
    LearningPath,
    ResourceQualityScore,
    StudentProfile,
)


class SqlAlchemyResourceRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_course_for_user(self, user_id: int, course_id: int) -> Course | None:
        return self.db.scalar(select(Course).where(Course.id == course_id, Course.owner_id == user_id))

    def get_knowledge_point(self, course_id: int, knowledge_point_id: int) -> KnowledgePoint | None:
        return self.db.scalar(
            select(KnowledgePoint).where(
                KnowledgePoint.id == knowledge_point_id,
                KnowledgePoint.course_id == course_id,
            )
        )

    def list_knowledge_points(self, course_id: int) -> list[KnowledgePoint]:
        return list(
            self.db.scalars(
                select(KnowledgePoint)
                .where(KnowledgePoint.course_id == course_id)
                .order_by(KnowledgePoint.order_index, KnowledgePoint.id)
            )
        )

    def list_course_chunks(self, course_id: int, knowledge_point_id: int | None = None) -> list[KnowledgeChunk]:
        statement = select(KnowledgeChunk).where(KnowledgeChunk.course_id == course_id)
        if knowledge_point_id is not None:
            statement = statement.where(KnowledgeChunk.knowledge_point_id == knowledge_point_id)
        return list(self.db.scalars(statement.order_by(KnowledgeChunk.id).limit(5)))

    def get_profile(self, user_id: int) -> StudentProfile | None:
        return self.db.scalar(select(StudentProfile).where(StudentProfile.user_id == user_id))

    def get_learning_task_for_user(self, user_id: int, task_id: int) -> LearningTask | None:
        return self.db.scalar(select(LearningTask).where(LearningTask.id == task_id, LearningTask.user_id == user_id))

    def add_resource(self, resource: GeneratedResource) -> GeneratedResource:
        self.db.add(resource)
        self.db.flush()
        return resource

    def is_path_draft(self, path_id: int) -> bool:
        return self.db.scalar(select(LearningPath.id).where(
            LearningPath.id == path_id, LearningPath.status == "draft",
        )) is not None

    def add_quality_score(self, score: ResourceQualityScore) -> ResourceQualityScore:
        self.db.add(score)
        self.db.flush()
        return score

    def add_agent_log(self, log: AgentRunLog) -> AgentRunLog:
        self.db.add(log)
        self.db.flush()
        return log

    def list_resources(
        self,
        user_id: int,
        *,
        course_id: int | None = None,
        resource_type: str | None = None,
    ) -> list[GeneratedResource]:
        statement = select(GeneratedResource).where(GeneratedResource.user_id == user_id)
        if course_id is not None:
            statement = statement.where(GeneratedResource.course_id == course_id)
        if resource_type is not None:
            statement = statement.where(GeneratedResource.resource_type == resource_type)
        return list(
            self.db.scalars(statement.order_by(GeneratedResource.updated_at.desc(), GeneratedResource.id.desc()))
        )

    def get_resource_for_user(
        self,
        user_id: int,
        resource_id: int,
        *,
        for_update: bool = False,
    ) -> GeneratedResource | None:
        statement = select(GeneratedResource).where(
            GeneratedResource.id == resource_id,
            GeneratedResource.user_id == user_id,
        )
        if for_update:
            statement = statement.with_for_update()
        return self.db.scalar(statement)

    def list_learning_tasks_for_user(self, user_id: int) -> list[LearningTask]:
        return list(self.db.scalars(select(LearningTask).where(LearningTask.user_id == user_id)))

    def delete_resource(self, resource: GeneratedResource) -> None:
        self.db.delete(resource)

    def max_version_number(self, version_family_id: str) -> int:
        return int(
            self.db.scalar(
                select(func.max(GeneratedResource.version_number)).where(
                    GeneratedResource.version_family_id == version_family_id,
                )
            )
            or 0
        )

    def lock_version_family(self, version_family_id: str) -> None:
        list(
            self.db.scalars(
                select(GeneratedResource.id)
                .where(GeneratedResource.version_family_id == version_family_id)
                .order_by(GeneratedResource.id)
                .with_for_update()
            )
        )

    def list_quality_scores(self, resource_id: int) -> list[ResourceQualityScore]:
        return list(
            self.db.scalars(
                select(ResourceQualityScore)
                .where(ResourceQualityScore.resource_id == resource_id)
                .order_by(ResourceQualityScore.id)
            )
        )

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()

    def refresh(self, instance: object) -> None:
        self.db.refresh(instance)

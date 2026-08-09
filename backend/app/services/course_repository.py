from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import (
    AssessmentReport,
    Course,
    CourseEnrollment,
    CourseMaterial,
    CourseMaterialLink,
    GeneratedResource,
    KnowledgeChunk,
    KnowledgePoint,
    LearningPath,
    LearningTask,
    Material,
    MaterialChunk,
    PracticeAnswer,
    PracticeSession,
    ProfileEvent,
    StudentProfile,
    WeaknessReviewItem,
)


class SqlAlchemyCourseRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_materials_for_user(self, user_id: int, material_ids: list[int]) -> list[Material]:
        if not material_ids:
            return []
        return list(self.db.scalars(select(Material).where(Material.user_id == user_id, Material.id.in_(material_ids))))

    def list_material_chunks(self, material_ids: list[int]) -> list[MaterialChunk]:
        if not material_ids:
            return []
        return list(
            self.db.scalars(
                select(MaterialChunk)
                .where(MaterialChunk.material_id.in_(material_ids))
                .order_by(MaterialChunk.material_id, MaterialChunk.chunk_index)
            )
        )

    def add_material_chunks(self, chunks: list[MaterialChunk]) -> None:
        self.db.add_all(chunks)
        self.db.flush()

    def add_course_graph(
        self,
        course: Course,
        enrollment: CourseEnrollment,
        course_materials: list[CourseMaterial],
        material_links: list[CourseMaterialLink],
        knowledge_points: list[KnowledgePoint],
        knowledge_chunks: list[KnowledgeChunk],
    ) -> Course:
        self.db.add(course)
        self.db.flush()

        enrollment.course_id = course.id
        self.db.add(enrollment)

        source_to_course_material: dict[int, CourseMaterial] = {}
        for course_material in course_materials:
            source_material_id = int((course_material.metadata_json or {}).get("source_material_id"))
            course_material.course_id = course.id
            self.db.add(course_material)
            self.db.flush()
            source_to_course_material[source_material_id] = course_material

        for link in material_links:
            link.course_id = course.id
            self.db.add(link)

        point_by_key: dict[str, KnowledgePoint] = {}
        for index, knowledge_point in enumerate(knowledge_points):
            knowledge_point.course_id = course.id
            self.db.add(knowledge_point)
            self.db.flush()
            point_by_key[str(getattr(knowledge_point, "builder_key", f"kp-{index + 1}"))] = knowledge_point

        for knowledge_point in knowledge_points:
            local_prerequisites = list(knowledge_point.prerequisites_json or [])
            knowledge_point.prerequisites_json = [
                point_by_key[key].id
                for key in local_prerequisites
                if key in point_by_key and point_by_key[key].id != knowledge_point.id
            ]

        for chunk in knowledge_chunks:
            source_material_id = int((chunk.metadata_json or {}).get("source_material_id"))
            source_order = int((chunk.metadata_json or {}).get("knowledge_point_order", 0))
            source_key = str((chunk.metadata_json or {}).get("knowledge_point_key") or "")
            chunk.course_id = course.id
            chunk.material_id = source_to_course_material[source_material_id].id
            if source_key in point_by_key:
                chunk.knowledge_point_id = point_by_key[source_key].id
            elif 0 <= source_order < len(knowledge_points):
                chunk.knowledge_point_id = knowledge_points[source_order].id
            self.db.add(chunk)

        self.db.flush()
        return course

    def list_courses_for_user(self, user_id: int, source_type: str | None = None) -> list[Course]:
        statement = select(Course).where(Course.owner_id == user_id)
        if source_type:
            statement = statement.where(Course.source_type == source_type)
        return list(self.db.scalars(statement.order_by(Course.updated_at.desc(), Course.id.desc())))

    def get_course_for_user(self, user_id: int, course_id: int) -> Course | None:
        return self.db.scalar(select(Course).where(Course.id == course_id, Course.owner_id == user_id))

    def get_enrollment(self, user_id: int, course_id: int) -> CourseEnrollment | None:
        return self.db.scalar(select(CourseEnrollment).where(
            CourseEnrollment.user_id == user_id,
            CourseEnrollment.course_id == course_id,
        ))

    def list_enrollments(self, user_id: int) -> list[CourseEnrollment]:
        return list(self.db.scalars(
            select(CourseEnrollment)
            .where(CourseEnrollment.user_id == user_id)
            .order_by(CourseEnrollment.last_accessed_at.desc().nullslast(), CourseEnrollment.created_at.desc())
        ))

    def list_completed_practices(self, user_id: int, course_id: int) -> list[PracticeSession]:
        return list(self.db.scalars(
            select(PracticeSession).where(
                PracticeSession.user_id == user_id,
                PracticeSession.course_id == course_id,
                PracticeSession.status == "completed",
            ).order_by(PracticeSession.updated_at.desc(), PracticeSession.id.desc())
        ))

    def get_latest_report(self, user_id: int, course_id: int) -> AssessmentReport | None:
        return self.db.scalar(
            select(AssessmentReport).where(
                AssessmentReport.user_id == user_id,
                AssessmentReport.course_id == course_id,
            ).order_by(AssessmentReport.created_at.desc(), AssessmentReport.id.desc())
        )

    def list_course_materials(self, course_id: int) -> list[CourseMaterial]:
        return list(self.db.scalars(select(CourseMaterial).where(CourseMaterial.course_id == course_id).order_by(CourseMaterial.id)))

    def list_knowledge_points(self, course_id: int) -> list[KnowledgePoint]:
        return list(
            self.db.scalars(
                select(KnowledgePoint).where(KnowledgePoint.course_id == course_id).order_by(KnowledgePoint.order_index, KnowledgePoint.id)
            )
        )

    def list_knowledge_chunks(self, course_id: int) -> list[KnowledgeChunk]:
        return list(self.db.scalars(select(KnowledgeChunk).where(KnowledgeChunk.course_id == course_id).order_by(KnowledgeChunk.id)))

    def get_profile(self, user_id: int) -> StudentProfile | None:
        return self.db.scalar(select(StudentProfile).where(StudentProfile.user_id == user_id))

    def list_weakness_candidate_events(self, user_id: int, course_id: int) -> list[ProfileEvent]:
        events = list(
            self.db.scalars(
                select(ProfileEvent)
                .where(ProfileEvent.user_id == user_id, ProfileEvent.dimension == "weak_points")
                .order_by(ProfileEvent.created_at.desc(), ProfileEvent.id.desc())
            )
        )
        return [
            event
            for event in events
            if (event.evidence_json or {}).get("source_type") == "course_question"
            and (event.evidence_json or {}).get("course_id") == course_id
        ]

    def list_weakness_review_items(self, user_id: int, course_id: int) -> list[WeaknessReviewItem]:
        return list(
            self.db.scalars(
                select(WeaknessReviewItem)
                .where(WeaknessReviewItem.user_id == user_id, WeaknessReviewItem.course_id == course_id)
                .order_by(WeaknessReviewItem.created_at.desc(), WeaknessReviewItem.id.desc())
            )
        )

    def list_weakness_review_items_for_update(self, user_id: int, course_id: int) -> list[WeaknessReviewItem]:
        """Lock weakness rows for the user+course to prevent duplicate inserts under concurrency."""
        return list(
            self.db.scalars(
                select(WeaknessReviewItem)
                .where(WeaknessReviewItem.user_id == user_id, WeaknessReviewItem.course_id == course_id)
                .with_for_update()
                .order_by(WeaknessReviewItem.created_at.desc(), WeaknessReviewItem.id.desc())
            )
        )

    def get_weakness_review_item(self, user_id: int, course_id: int, item_id: int) -> WeaknessReviewItem | None:
        return self.db.scalar(
            select(WeaknessReviewItem).where(
                WeaknessReviewItem.id == item_id,
                WeaknessReviewItem.user_id == user_id,
                WeaknessReviewItem.course_id == course_id,
            )
        )

    def add_weakness_review_item(self, item: WeaknessReviewItem) -> None:
        self.db.add(item)
        self.db.flush()

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

    def list_learning_tasks(self, user_id: int, course_id: int) -> list[LearningTask]:
        return list(
            self.db.scalars(
                select(LearningTask)
                .where(LearningTask.user_id == user_id, LearningTask.course_id == course_id)
                .order_by(LearningTask.id.asc())
            )
        )

    def list_tasks_for_path(self, path_id: int) -> list[LearningTask]:
        return list(
            self.db.scalars(
                select(LearningTask)
                .where(LearningTask.path_id == path_id)
                .order_by(LearningTask.id.asc())
            )
        )

    def list_practice_answers(self, user_id: int, course_id: int) -> list[PracticeAnswer]:
        return list(
            self.db.scalars(
                select(PracticeAnswer)
                .join(PracticeSession, PracticeSession.id == PracticeAnswer.session_id)
                .where(PracticeAnswer.user_id == user_id, PracticeSession.course_id == course_id)
                .order_by(PracticeAnswer.created_at.desc(), PracticeAnswer.id.desc())
            )
        )

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()

    def refresh(self, instance: object) -> None:
        self.db.refresh(instance)

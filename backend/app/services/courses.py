from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from backend.app.models import (
    Course,
    CourseEnrollment,
    User,
)
from backend.app.schemas.courses import (
    CourseKnowledgePoint,
    CourseKnowledgePointContent,
    CourseKnowledgeSection,
    CourseLearnerProfile,
    CourseLearnerProfileUpdate,
    CourseListResponse,
    CourseMasteryMap,
    CourseOverview,
    CourseStageCompletion,
    CourseStructureSummary,
    CourseSummary,
    CreateCourseFromMaterialsResult,
    resource_brief,
)
from backend.app.services.course_contracts import (
    CourseEmbeddingService,
    CourseGenerationError as CourseGenerationError,
    CourseNotFoundError as CourseNotFoundError,
    CourseRepository,
    CourseWeaknessStateTransitionError as CourseWeaknessStateTransitionError,
)
from backend.app.services.course_content import CourseContentMixin
from backend.app.services.course_learning_state import CourseLearningStateMixin
from backend.app.services.course_repository import SqlAlchemyCourseRepository as SqlAlchemyCourseRepository
from backend.app.services.material_retrieval import MaterialChunkingService
from backend.app.services.model_settings import ModelSettingsService


class CourseService(CourseContentMixin, CourseLearningStateMixin):
    generation_error = CourseGenerationError
    text_extensions = {".txt", ".md", ".markdown", ".pdf", ".docx", ".pptx"}
    chunk_size = 900
    weakness_action_target_status = {
        "confirm": "confirmed",
        "start": "reviewing",
        "complete": "completed",
        "dismiss": "dismissed",
    }
    weakness_allowed_actions = {
        "pending": {"confirm", "start", "complete", "dismiss"},
        "confirmed": {"start", "complete", "dismiss"},
        "reviewing": {"complete", "dismiss"},
        "completed": {"dismiss"},
        "dismissed": {"dismiss"},
    }

    def __init__(
        self,
        repository: CourseRepository,
        embedding_service: CourseEmbeddingService | None = None,
        *,
        model_service: ModelSettingsService | None = None,
        trace_recorder: Any | None = None,
        chunking_service: MaterialChunkingService | None = None,
    ) -> None:
        self.repository = repository
        self.embedding_service = embedding_service
        self.model_service = model_service
        self.trace_recorder = trace_recorder
        self.chunking_service = chunking_service or MaterialChunkingService()

    def create_course_from_materials(
        self,
        user: User,
        material_ids: list[int],
        course_title: str = "",
    ) -> CreateCourseFromMaterialsResult:
        from backend.app.agents.course_builder import CourseBuilderGraphRunner

        return CourseBuilderGraphRunner(self).generate(user=user, material_ids=material_ids, course_title=course_title)

    def list_courses(self, user: User, source_type: str | None = None) -> CourseListResponse:
        courses = self.repository.list_courses_for_user(user.id, source_type)
        enrollments = {item.course_id: item for item in self._list_enrollments(user.id)}
        current_id = next((item.course_id for item in enrollments.values() if item.learning_status == "active"), None)
        courses.sort(key=lambda item: (
            0 if enrollments.get(item.id) and enrollments[item.id].learning_status == "active" else 1,
            -(enrollments.get(item.id).last_accessed_at or enrollments.get(item.id).created_at).timestamp() if enrollments.get(item.id) else 0,
        ))
        data = [self._build_summary(course, user_id=user.id, enrollment=enrollments.get(course.id), current_course_id=current_id) for course in courses]
        return CourseListResponse(data=data, page=1, page_size=len(data), total=len(data))

    def get_course(self, user: User, course_id: int) -> CourseSummary:
        course = self._require_course(user, course_id)
        enrollment = self._require_enrollment(user.id, course.id)
        current = next((item.course_id for item in self._list_enrollments(user.id) if (item.learning_status or "active") == "active"), None)
        return self._build_summary(course, user_id=user.id, enrollment=enrollment, current_course_id=current)

    def activate_course(self, user: User, course_id: int) -> CourseSummary:
        course = self._require_course(user, course_id)
        enrollment = self._require_enrollment(user.id, course.id)
        enrollment.last_accessed_at = datetime.now(UTC)
        self.repository.commit()
        current_id = course.id if (enrollment.learning_status or "active") == "active" else None
        return self._build_summary(course, user_id=user.id, enrollment=enrollment, current_course_id=current_id)

    def resume_course(self, user: User, course_id: int) -> CourseSummary:
        course = self._require_course(user, course_id)
        enrollment = self._require_enrollment(user.id, course.id)
        enrollment.learning_status = "active"
        enrollment.completed_at = None
        enrollment.last_accessed_at = datetime.now(UTC)
        self.repository.commit()
        return self._build_summary(course, user_id=user.id, enrollment=enrollment, current_course_id=course.id)

    def get_learner_profile(self, user: User, course_id: int) -> CourseLearnerProfile:
        course = self._require_course(user, course_id)
        enrollment = self._require_enrollment(user.id, course.id)
        return self._course_profile(user.id, course.id, enrollment)

    def update_learner_profile(self, user: User, course_id: int, payload: CourseLearnerProfileUpdate) -> CourseLearnerProfile:
        course = self._require_course(user, course_id)
        enrollment = self._require_enrollment(user.id, course.id)
        if enrollment.learning_status == "archived":
            raise CourseGenerationError("课程已完成归档；请先恢复学习再更新课程画像。")
        enrollment.learning_context_json = {
            "learning_goal": payload.learning_goal.strip(),
            "knowledge_foundation": payload.knowledge_foundation.strip(),
            "weak_points": [item.strip() for item in payload.weak_points if item.strip()][:20],
        }
        enrollment.learning_context_confidence_json = {
            "learning_goal": 100,
            "knowledge_foundation": 100,
            "weak_points": 100 if payload.weak_points else 0,
        }
        self.repository.commit()
        return self._course_profile(user.id, course.id, enrollment)

    def complete_course(self, user: User, course_id: int) -> CourseSummary:
        course = self._require_course(user, course_id)
        enrollment = self._require_enrollment(user.id, course.id)
        if enrollment.learning_status == "archived":
            raise CourseGenerationError("课程已经完成归档。")
        completion = self._stage_completion(user, course.id)
        if not completion.eligible:
            raise CourseGenerationError("课程尚未达到阶段完成标准：" + "；".join(completion.blocking_reasons))
        enrollment.learning_status = "archived"
        enrollment.completed_at = datetime.now(UTC)
        self.repository.commit()
        return self._build_summary(course, user_id=user.id, enrollment=enrollment, current_course_id=None)

    def get_stage_completion(self, user: User, course_id: int) -> CourseStageCompletion:
        course = self._require_course(user, course_id)
        return self._stage_completion(user, course.id)

    def get_overview(self, user: User, course_id: int) -> CourseOverview:
        course = self._require_course(user, course_id)
        materials = self.repository.list_course_materials(course.id)
        points = self.repository.list_knowledge_points(course.id)
        chunks = self.repository.list_knowledge_chunks(course.id)
        return CourseOverview(
            course=self._build_summary(course, len(materials), len(points), len(chunks)),
            materials=[material.filename for material in materials],
            knowledge_points=[self._build_knowledge_point(point) for point in points],
            chunk_count=len(chunks),
            structure=CourseStructureSummary(**course.structure_json) if getattr(course, "structure_json", None) else None,
        )

    def get_knowledge_points(self, user: User, course_id: int) -> list[CourseKnowledgePoint]:
        course = self._require_course(user, course_id)
        return [self._build_knowledge_point(point) for point in self.repository.list_knowledge_points(course.id)]

    def get_knowledge_point_content(
        self,
        user: User,
        course_id: int,
        knowledge_point_id: int,
    ) -> CourseKnowledgePointContent:
        course = self._require_course(user, course_id)
        points = self.repository.list_knowledge_points(course.id)
        point_index = next((index for index, item in enumerate(points) if item.id == knowledge_point_id), None)
        if point_index is None:
            raise CourseNotFoundError("课程知识点不存在或无权访问。")

        point = points[point_index]
        materials_by_id = {item.id: item for item in self.repository.list_course_materials(course.id)}
        chunks = [
            item
            for item in self.repository.list_knowledge_chunks(course.id)
            if item.knowledge_point_id == point.id
        ][:12]
        resources = [
            item
            for item in self.repository.list_generated_resources(user.id, course.id)
            if item.knowledge_point_id == point.id
        ]
        sections = []
        for chunk in chunks:
            material = materials_by_id.get(chunk.material_id)
            metadata = chunk.metadata_json or {}
            source_title = material.filename if material is not None else str(metadata.get("source_filename") or "课程资料")
            sections.append(
                CourseKnowledgeSection(
                    chunk_id=str(chunk.id),
                    title=(chunk.section_title or point.chapter or point.title)[:255],
                    content=chunk.content.strip()[:1200],
                    source_title=source_title[:255],
                    page_number=chunk.page_number,
                )
            )

        return CourseKnowledgePointContent(
            knowledge_point=self._build_knowledge_point(point),
            sections=sections,
            related_resources=[resource_brief(item) for item in resources],
            previous_knowledge_point_id=str(points[point_index - 1].id) if point_index > 0 else None,
            next_knowledge_point_id=str(points[point_index + 1].id) if point_index + 1 < len(points) else None,
        )

    def get_mastery_map(self, user: User, course_id: int) -> CourseMasteryMap:
        course = self._require_course(user, course_id)
        knowledge_points = self.repository.list_knowledge_points(course.id)
        review_items = self.repository.list_weakness_review_items(user.id, course.id)
        resources = self.repository.list_generated_resources(user.id, course.id)
        tasks = self.repository.list_learning_tasks(user.id, course.id)
        practice_answers = self.repository.list_practice_answers(user.id, course.id)
        points = self._build_mastery_points(knowledge_points, review_items, resources, tasks, practice_answers)
        return CourseMasteryMap(
            course_id=str(course.id),
            summary=self._build_mastery_summary(points),
            points=points,
        )

    def _require_course(self, user: User, course_id: int) -> Course:
        course = self.repository.get_course_for_user(user.id, course_id)
        if course is None:
            raise CourseNotFoundError("课程不存在或无权访问。")
        return course

    def _require_enrollment(self, user_id: int, course_id: int) -> CourseEnrollment:
        enrollment = self.repository.get_enrollment(user_id, course_id)
        if enrollment is None:
            enrollment = CourseEnrollment(
                user_id=user_id,
                course_id=course_id,
                role="learner",
                progress_percent=0,
                learning_status="active",
                learning_context_json={},
                learning_context_confidence_json={},
            )
        return enrollment

    def _list_enrollments(self, user_id: int) -> list[CourseEnrollment]:
        return self.repository.list_enrollments(user_id)

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from backend.app.core.errors import NotFoundDomainError, ValidationDomainError
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
    User,
    WeaknessReviewItem,
)


class CourseGenerationError(ValidationDomainError):
    pass


class CourseNotFoundError(NotFoundDomainError):
    pass


class CourseWeaknessStateTransitionError(ValidationDomainError):
    pass


@dataclass(frozen=True)
class ParsedSection:
    title: str
    chapter: str | None
    content: str
    material: Material


@dataclass(frozen=True)
class WeaknessCandidate:
    title: str
    knowledge_point_id: int | None
    trace_id: str | None
    source_title: str | None
    section_title: str | None


class CourseRepository(Protocol):
    def get_materials_for_user(self, user_id: int, material_ids: list[int]) -> list[Material]: ...

    def list_material_chunks(self, material_ids: list[int]) -> list[MaterialChunk]: ...

    def add_material_chunks(self, chunks: list[MaterialChunk]) -> None: ...

    def add_course_graph(
        self,
        course: Course,
        enrollment: CourseEnrollment,
        course_materials: list[CourseMaterial],
        material_links: list[CourseMaterialLink],
        knowledge_points: list[KnowledgePoint],
        knowledge_chunks: list[KnowledgeChunk],
    ) -> Course: ...

    def list_courses_for_user(self, user_id: int, source_type: str | None = None) -> list[Course]: ...

    def get_course_for_user(self, user_id: int, course_id: int) -> Course | None: ...

    def get_enrollment(self, user_id: int, course_id: int) -> CourseEnrollment | None: ...

    def list_enrollments(self, user_id: int) -> list[CourseEnrollment]: ...

    def list_completed_practices(self, user_id: int, course_id: int) -> list[PracticeSession]: ...

    def get_latest_report(self, user_id: int, course_id: int) -> AssessmentReport | None: ...

    def list_course_materials(self, course_id: int) -> list[CourseMaterial]: ...

    def list_knowledge_points(self, course_id: int) -> list[KnowledgePoint]: ...

    def list_knowledge_chunks(self, course_id: int) -> list[KnowledgeChunk]: ...

    def get_profile(self, user_id: int) -> StudentProfile | None: ...

    def list_weakness_candidate_events(self, user_id: int, course_id: int) -> list[ProfileEvent]: ...

    def list_weakness_review_items(self, user_id: int, course_id: int) -> list[WeaknessReviewItem]: ...

    def list_weakness_review_items_for_update(self, user_id: int, course_id: int) -> list[WeaknessReviewItem]: ...

    def get_weakness_review_item(self, user_id: int, course_id: int, item_id: int) -> WeaknessReviewItem | None: ...

    def add_weakness_review_item(self, item: WeaknessReviewItem) -> None: ...

    def list_generated_resources(self, user_id: int, course_id: int) -> list[GeneratedResource]: ...

    def get_active_path(self, user_id: int, course_id: int) -> LearningPath | None: ...

    def list_learning_tasks(self, user_id: int, course_id: int) -> list[LearningTask]: ...

    def list_tasks_for_path(self, path_id: int) -> list[LearningTask]: ...

    def list_practice_answers(self, user_id: int, course_id: int) -> list[PracticeAnswer]: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...

    def refresh(self, instance: object) -> None: ...


class CourseEmbeddingService(Protocol):
    def embed_texts(self, user: User, texts: list[str]) -> Any: ...

    def apply_embeddings(self, user: User, chunks: list[KnowledgeChunk]) -> Any: ...

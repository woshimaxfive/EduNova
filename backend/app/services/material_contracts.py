from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from backend.app.models import (
    Course,
    CourseMaterial,
    CourseMaterialLink,
    KnowledgeChunk,
    KnowledgePoint,
    Material,
    MaterialChunk,
    MaterialComparisonRun,
    User,
)


class MaterialValidationError(Exception):
    pass


class MaterialNotFoundError(Exception):
    pass


class CourseNotFoundError(Exception):
    pass


class MaterialModelService(Protocol):
    def chat_completion(self, user: User, messages: list[dict[str, str]]) -> str: ...


@dataclass(frozen=True)
class MaterialEvidence:
    material_id: int
    source_title: str
    title: str
    content: str
    section_title: str | None = None
    page_number: int | None = None
    knowledge_point_id: int | None = None
    confidence: str = "medium"


class MaterialRepository(Protocol):
    def get_course_for_user(self, user_id: int, course_id: int) -> Course | None: ...

    def add_material(self, material: Material) -> None: ...

    def add_material_chunks(self, chunks: list[MaterialChunk]) -> None: ...

    def get_material_for_user(self, user_id: int, material_id: int) -> Material | None: ...

    def delete_material(self, material: Material) -> None: ...

    def list_materials(
        self,
        user_id: int,
        course_id: int | None = None,
        unassigned: bool = False,
    ) -> list[Material]: ...

    def list_material_chunks(self, user_id: int, material_id: int) -> list[MaterialChunk]: ...

    def list_material_course_links(
        self,
        user_id: int,
        material_id: int,
    ) -> list[tuple[CourseMaterialLink, Course]]: ...

    def get_link(self, course_id: int, material_id: int) -> CourseMaterialLink | None: ...

    def add_link(self, link: CourseMaterialLink) -> CourseMaterialLink: ...

    def list_course_materials(self, course_id: int) -> list[CourseMaterial]: ...

    def list_knowledge_points(self, course_id: int) -> list[KnowledgePoint]: ...

    def list_knowledge_chunks(self, course_id: int) -> list[KnowledgeChunk]: ...

    def add_comparison_run(self, run: MaterialComparisonRun) -> MaterialComparisonRun: ...

    def get_comparison_run_for_user(
        self,
        user_id: int,
        comparison_id: int,
    ) -> MaterialComparisonRun | None: ...

    def get_latest_comparison_run(
        self,
        user_id: int,
        course_id: int,
    ) -> MaterialComparisonRun | None: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...

    def refresh(self, instance: object) -> None: ...

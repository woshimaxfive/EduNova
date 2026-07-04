from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import (
    Course,
    CourseEnrollment,
    CourseMaterial,
    CourseMaterialLink,
    KnowledgeChunk,
    KnowledgePoint,
    Material,
    User,
)
from backend.app.schemas.courses import (
    CourseKnowledgePoint,
    CourseListResponse,
    CourseOverview,
    CourseSummary,
    CreateCourseFromMaterialsResult,
)


class CourseGenerationError(Exception):
    pass


class CourseNotFoundError(Exception):
    pass


@dataclass(frozen=True)
class ParsedSection:
    title: str
    chapter: str | None
    content: str
    material: Material


class CourseRepository(Protocol):
    def get_materials_for_user(self, user_id: int, material_ids: list[int]) -> list[Material]: ...

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

    def list_course_materials(self, course_id: int) -> list[CourseMaterial]: ...

    def list_knowledge_points(self, course_id: int) -> list[KnowledgePoint]: ...

    def list_knowledge_chunks(self, course_id: int) -> list[KnowledgeChunk]: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...

    def refresh(self, instance: object) -> None: ...


class CourseEmbeddingService(Protocol):
    def embed_texts(self, user: User, texts: list[str]) -> Any: ...

    def apply_embeddings(self, user: User, chunks: list[KnowledgeChunk]) -> Any: ...


class SqlAlchemyCourseRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_materials_for_user(self, user_id: int, material_ids: list[int]) -> list[Material]:
        if not material_ids:
            return []
        return list(self.db.scalars(select(Material).where(Material.user_id == user_id, Material.id.in_(material_ids))))

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

        for knowledge_point in knowledge_points:
            knowledge_point.course_id = course.id
            self.db.add(knowledge_point)
            self.db.flush()

        for chunk in knowledge_chunks:
            source_material_id = int((chunk.metadata_json or {}).get("source_material_id"))
            source_order = int((chunk.metadata_json or {}).get("knowledge_point_order", 0))
            chunk.course_id = course.id
            chunk.material_id = source_to_course_material[source_material_id].id
            if 0 <= source_order < len(knowledge_points):
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

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()

    def refresh(self, instance: object) -> None:
        self.db.refresh(instance)


class CourseService:
    text_extensions = {".txt", ".md", ".markdown"}
    chunk_size = 900

    def __init__(self, repository: CourseRepository, embedding_service: CourseEmbeddingService | None = None) -> None:
        self.repository = repository
        self.embedding_service = embedding_service

    def create_course_from_materials(
        self,
        user: User,
        material_ids: list[int],
        course_title: str = "",
    ) -> CreateCourseFromMaterialsResult:
        unique_material_ids = list(dict.fromkeys(material_ids))
        if not unique_material_ids:
            raise CourseGenerationError("至少选择一份资料。")

        materials = self._ordered_materials(user.id, unique_material_ids)
        self._validate_materials(materials, unique_material_ids)
        sections = self._parse_sections(materials)
        if not sections:
            raise CourseGenerationError("当前仅支持已解析的 TXT/Markdown 生成课程。")

        title = course_title.strip() or Path(materials[0].filename).stem
        course = Course(
            owner_id=user.id,
            title=title,
            description=f"由 {len(materials)} 份资料生成",
            subject="自动生成课程",
            source_type="uploaded",
            visibility="private",
            status="ready",
        )
        enrollment = CourseEnrollment(user_id=user.id, course_id=0, role="learner", progress_percent=Decimal("0"))
        course_materials = [self._build_course_material(user, material) for material in materials]
        material_links = [
            CourseMaterialLink(course_id=0, material_id=material.id, added_by_user_id=user.id, usage_type="course_source")
            for material in materials
        ]
        knowledge_points = [
            KnowledgePoint(
                course_id=0,
                title=section.title,
                summary=self._summary(section.content),
                chapter=section.chapter,
                order_index=index,
                difficulty=None,
                prerequisites_json=[],
            )
            for index, section in enumerate(sections)
        ]
        knowledge_chunks = self._build_chunks(sections)

        try:
            created = self.repository.add_course_graph(
                course,
                enrollment,
                course_materials,
                material_links,
                knowledge_points,
                knowledge_chunks,
            )
            self._best_effort_embed_chunks(user, knowledge_chunks)
            self.repository.commit()
            self.repository.refresh(created)
        except Exception:
            self.repository.rollback()
            raise

        return CreateCourseFromMaterialsResult(
            course=self._build_summary(created, len(course_materials), len(knowledge_points), len(knowledge_chunks)),
            knowledge_points=[self._build_knowledge_point(point) for point in knowledge_points],
        )

    def list_courses(self, user: User, source_type: str | None = None) -> CourseListResponse:
        courses = self.repository.list_courses_for_user(user.id, source_type)
        data = [self._build_summary(course) for course in courses]
        return CourseListResponse(data=data, page=1, page_size=len(data), total=len(data))

    def get_course(self, user: User, course_id: int) -> CourseSummary:
        course = self._require_course(user, course_id)
        return self._build_summary(course)

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
        )

    def get_knowledge_points(self, user: User, course_id: int) -> list[CourseKnowledgePoint]:
        course = self._require_course(user, course_id)
        return [self._build_knowledge_point(point) for point in self.repository.list_knowledge_points(course.id)]

    def _ordered_materials(self, user_id: int, material_ids: list[int]) -> list[Material]:
        materials = self.repository.get_materials_for_user(user_id, material_ids)
        by_id = {material.id: material for material in materials}
        return [by_id[material_id] for material_id in material_ids if material_id in by_id]

    def _validate_materials(self, materials: list[Material], material_ids: list[int]) -> None:
        if len(materials) != len(material_ids):
            raise CourseGenerationError("资料不存在或无权访问。")

        for material in materials:
            if (
                material.parse_status != "completed"
                or not material.extracted_text
                or self._extension(material.filename) not in self.text_extensions
            ):
                raise CourseGenerationError("当前仅支持已解析的 TXT/Markdown 生成课程。")

    def _parse_sections(self, materials: list[Material]) -> list[ParsedSection]:
        sections: list[ParsedSection] = []
        for material in materials:
            extension = self._extension(material.filename)
            text = material.extracted_text or ""
            if extension in {".md", ".markdown"}:
                sections.extend(self._parse_markdown(material, text))
            else:
                sections.extend(self._parse_plain_text(material, text))
        return sections

    def _parse_markdown(self, material: Material, text: str) -> list[ParsedSection]:
        lines = text.splitlines()
        heading_indexes: list[tuple[int, int, str]] = []
        for index, line in enumerate(lines):
            stripped = line.strip()
            if not stripped.startswith("#"):
                continue
            marker, _, title = stripped.partition(" ")
            if 1 <= len(marker) <= 3 and set(marker) == {"#"} and title.strip():
                heading_indexes.append((index, len(marker), title.strip()))

        if not heading_indexes:
            return self._parse_plain_text(material, text)

        sections: list[ParsedSection] = []
        current_chapter: str | None = None
        for heading_position, (line_index, level, title) in enumerate(heading_indexes):
            if level == 1:
                current_chapter = title
            next_line_index = heading_indexes[heading_position + 1][0] if heading_position + 1 < len(heading_indexes) else len(lines)
            content = self._clean_text("\n".join(lines[line_index + 1 : next_line_index]))
            if not content:
                content = title
            sections.append(
                ParsedSection(
                    title=title,
                    chapter=title if level == 1 else current_chapter,
                    content=content,
                    material=material,
                )
            )
        return sections

    def _parse_plain_text(self, material: Material, text: str) -> list[ParsedSection]:
        paragraphs = [self._clean_text(part) for part in text.replace("\r\n", "\n").split("\n\n")]
        paragraphs = [paragraph for paragraph in paragraphs if paragraph]
        return [
            ParsedSection(
                title=f"第 {index} 部分",
                chapter=None,
                content=paragraph,
                material=material,
            )
            for index, paragraph in enumerate(paragraphs, start=1)
        ]

    def _build_course_material(self, user: User, material: Material) -> CourseMaterial:
        return CourseMaterial(
            user_id=user.id,
            course_id=0,
            filename=material.filename,
            content_type=material.content_type,
            storage_path=material.storage_path,
            parse_status=material.parse_status,
            extracted_text=material.extracted_text,
            metadata_json={
                **(material.metadata_json or {}),
                "source_material_id": material.id,
                "generated_from_library": True,
            },
        )

    def _build_chunks(self, sections: list[ParsedSection]) -> list[KnowledgeChunk]:
        chunks: list[KnowledgeChunk] = []
        for index, section in enumerate(sections):
            for chunk_text in self._split_text(section.content):
                chunks.append(
                    KnowledgeChunk(
                        course_id=0,
                        material_id=None,  # type: ignore[arg-type]
                        knowledge_point_id=None,
                        content=chunk_text,
                        page_number=None,
                        section_title=section.title,
                        embedding=None,
                        metadata_json={
                            "source_material_id": section.material.id,
                            "knowledge_point_order": index,
                            "source_filename": section.material.filename,
                        },
                    )
                )
        return chunks

    def _best_effort_embed_chunks(self, user: User, chunks: list[KnowledgeChunk]) -> None:
        if self.embedding_service is None or not chunks:
            return
        try:
            apply_embeddings = getattr(self.embedding_service, "apply_embeddings", None)
            if callable(apply_embeddings):
                apply_embeddings(user, chunks)
                return

            batch = self.embedding_service.embed_texts(user, [chunk.content for chunk in chunks])
            vectors = list(getattr(batch, "vectors", []))
            if len(vectors) != len(chunks):
                return
            source = str(getattr(batch, "source", "unknown"))
            model = str(getattr(batch, "model", "unknown"))
            dimension = int(getattr(batch, "dimension", 1536))
            for chunk, vector in zip(chunks, vectors, strict=True):
                if len(vector) != dimension:
                    continue
                chunk.embedding = vector
                chunk.metadata_json = {
                    **(chunk.metadata_json or {}),
                    "embedding_source": source,
                    "embedding_model": model,
                    "embedding_dimension": dimension,
                }
        except Exception:
            return

    def _require_course(self, user: User, course_id: int) -> Course:
        course = self.repository.get_course_for_user(user.id, course_id)
        if course is None:
            raise CourseNotFoundError("课程不存在或无权访问。")
        return course

    def _build_summary(
        self,
        course: Course,
        material_count: int | None = None,
        knowledge_point_count: int | None = None,
        chunk_count: int | None = None,
    ) -> CourseSummary:
        if material_count is None:
            material_count = len(self.repository.list_course_materials(course.id))
        if knowledge_point_count is None:
            knowledge_point_count = len(self.repository.list_knowledge_points(course.id))
        if chunk_count is None:
            chunk_count = len(self.repository.list_knowledge_chunks(course.id))

        return CourseSummary(
            id=str(course.id),
            title=course.title,
            description=course.description,
            subject=course.subject,
            source_type=course.source_type or "uploaded",
            status=course.status or "draft",
            progress_percent=0,
            material_count=material_count,
            knowledge_point_count=knowledge_point_count,
            chunk_count=chunk_count,
        )

    @staticmethod
    def _build_knowledge_point(point: KnowledgePoint) -> CourseKnowledgePoint:
        return CourseKnowledgePoint(
            id=str(point.id),
            title=point.title,
            summary=point.summary,
            chapter=point.chapter,
            order_index=point.order_index,
            difficulty=point.difficulty,
        )

    @classmethod
    def _split_text(cls, text: str) -> list[str]:
        if len(text) <= cls.chunk_size:
            return [text]
        return [text[index : index + cls.chunk_size] for index in range(0, len(text), cls.chunk_size)]

    @staticmethod
    def _summary(text: str) -> str:
        cleaned = CourseService._clean_text(text)
        return cleaned[:120]

    @staticmethod
    def _clean_text(text: str) -> str:
        return " ".join(text.split())

    @staticmethod
    def _extension(filename: str) -> str:
        return Path(filename).suffix.lower()

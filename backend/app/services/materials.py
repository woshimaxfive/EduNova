from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from backend.app.core.config import Settings, get_settings
from backend.app.models import Course, CourseMaterial, CourseMaterialLink, KnowledgeChunk, KnowledgePoint, Material, User
from backend.app.schemas.materials import (
    AttachCourseMaterialsResult,
    MaterialDetail,
    MaterialComparisonCitation,
    MaterialComparisonPoint,
    MaterialComparisonResult,
    MaterialComparisonSummary,
    MaterialListItem,
    MaterialProgress,
    MaterialUploadResult,
)


class MaterialValidationError(Exception):
    pass


class MaterialNotFoundError(Exception):
    pass


class CourseNotFoundError(Exception):
    pass


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

    def get_material_for_user(self, user_id: int, material_id: int) -> Material | None: ...

    def list_materials(self, user_id: int, course_id: int | None = None, unassigned: bool = False) -> list[Material]: ...

    def get_link(self, course_id: int, material_id: int) -> CourseMaterialLink | None: ...

    def add_link(self, link: CourseMaterialLink) -> CourseMaterialLink: ...

    def list_course_materials(self, course_id: int) -> list[CourseMaterial]: ...

    def list_knowledge_points(self, course_id: int) -> list[KnowledgePoint]: ...

    def list_knowledge_chunks(self, course_id: int) -> list[KnowledgeChunk]: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...

    def refresh(self, instance: object) -> None: ...


class SqlAlchemyMaterialRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_course_for_user(self, user_id: int, course_id: int) -> Course | None:
        return self.db.scalar(select(Course).where(Course.id == course_id, Course.owner_id == user_id))

    def add_material(self, material: Material) -> None:
        self.db.add(material)
        self.db.flush()

    def get_material_for_user(self, user_id: int, material_id: int) -> Material | None:
        return self.db.scalar(select(Material).where(Material.id == material_id, Material.user_id == user_id))

    def list_materials(self, user_id: int, course_id: int | None = None, unassigned: bool = False) -> list[Material]:
        statement = select(Material).where(Material.user_id == user_id)

        if course_id is not None:
            statement = statement.join(CourseMaterialLink, CourseMaterialLink.material_id == Material.id).where(
                CourseMaterialLink.course_id == course_id
            )

        if unassigned:
            linked_material = select(CourseMaterialLink.id).where(CourseMaterialLink.material_id == Material.id)
            statement = statement.where(~exists(linked_material))

        return list(self.db.scalars(statement.order_by(Material.created_at.desc(), Material.id.desc())))

    def get_link(self, course_id: int, material_id: int) -> CourseMaterialLink | None:
        return self.db.scalar(
            select(CourseMaterialLink).where(
                CourseMaterialLink.course_id == course_id,
                CourseMaterialLink.material_id == material_id,
            )
        )

    def add_link(self, link: CourseMaterialLink) -> CourseMaterialLink:
        existing = self.get_link(link.course_id, link.material_id)
        if existing is not None:
            return existing
        self.db.add(link)
        self.db.flush()
        return link

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


class MaterialService:
    allowed_extensions = {".txt", ".md", ".markdown", ".pdf", ".doc", ".docx", ".ppt", ".pptx", ".png", ".jpg", ".jpeg", ".webp"}
    light_parse_extensions = {".txt", ".md", ".markdown"}
    image_extensions = {".png", ".jpg", ".jpeg", ".webp"}
    exam_title_keywords = ("期末", "复习", "试题", "样题", "真题", "考试", "练习")

    def __init__(self, repository: MaterialRepository, settings: Settings | None = None) -> None:
        self.repository = repository
        self.settings = settings or get_settings()

    def upload_material(
        self,
        user: User,
        filename: str,
        content_type: str,
        content: bytes,
        course_id: int | None = None,
    ) -> MaterialUploadResult:
        clean_name = self._validate_filename(filename)
        extension = self._extension(clean_name)
        self._validate_size(content)
        course = self._require_course(user, course_id) if course_id is not None else None
        parse_status, extracted_text = self._extract_text(extension, content)
        relative_path = self._store_file(user.id, clean_name, content)
        metadata = {
            "size_bytes": len(content),
            "size_label": self._format_size(len(content)),
            "extension": extension.lstrip(".").upper() or "FILE",
            "detail": self._detail_for_status(parse_status, extension),
        }
        material = Material(
            user_id=user.id,
            filename=clean_name,
            content_type=content_type or "application/octet-stream",
            storage_path=relative_path,
            parse_status=parse_status,
            extracted_text=extracted_text,
            metadata_json=metadata,
        )

        try:
            self.repository.add_material(material)
            if course is not None:
                self.repository.add_link(
                    CourseMaterialLink(
                        course_id=course.id,
                        material_id=material.id,
                        added_by_user_id=user.id,
                        usage_type="reference",
                    )
                )
            self.repository.commit()
            self.repository.refresh(material)
        except Exception:
            self.repository.rollback()
            raise

        return self._build_upload_result(material, course.id if course is not None else None)

    def list_materials(self, user: User, course_id: int | None = None, unassigned: bool = False) -> list[MaterialListItem]:
        if course_id is not None:
            self._require_course(user, course_id)
        return [self._build_list_item(material) for material in self.repository.list_materials(user.id, course_id, unassigned)]

    def get_material(self, user: User, material_id: int) -> MaterialDetail:
        material = self._require_material(user, material_id)
        item = self._build_list_item(material)
        preview = material.extracted_text[:500] if material.extracted_text else None
        return MaterialDetail(
            **item.model_dump(),
            filename=material.filename,
            content_type=material.content_type,
            extracted_text_preview=preview,
        )

    def get_progress(self, user: User, material_id: int) -> MaterialProgress:
        material = self._require_material(user, material_id)
        if material.parse_status == "completed":
            return MaterialProgress(status="completed", progress_percent=100, message="轻解析已完成")
        if material.parse_status == "failed":
            return MaterialProgress(status="failed", progress_percent=0, message="解析失败")
        return MaterialProgress(status=material.parse_status, progress_percent=10, message=self._detail_for_status(material.parse_status, self._extension(material.filename)))

    def attach_materials_to_course(self, user: User, course_id: int, material_ids: list[int]) -> AttachCourseMaterialsResult:
        course = self._require_course(user, course_id)
        attached_ids: list[str] = []
        unique_material_ids = list(dict.fromkeys(material_ids))

        try:
            for material_id in unique_material_ids:
                material = self._require_material(user, material_id)
                link = self.repository.add_link(
                    CourseMaterialLink(
                        course_id=course.id,
                        material_id=material.id,
                        added_by_user_id=user.id,
                        usage_type="reference",
                    )
                )
                attached_ids.append(str(link.material_id))
            self.repository.commit()
        except Exception:
            self.repository.rollback()
            raise

        return AttachCourseMaterialsResult(course_id=str(course.id), material_ids=attached_ids, attached_count=len(attached_ids))

    def compare_materials(self, user: User, course_id: int, material_ids: list[int]) -> MaterialComparisonResult:
        course = self._require_course(user, course_id)
        unique_material_ids = list(dict.fromkeys(material_ids))
        if len(unique_material_ids) < 2:
            raise MaterialValidationError("至少选择两份同课程资料。")

        materials = [self._require_material(user, material_id) for material_id in unique_material_ids]
        for material in materials:
            if self.repository.get_link(course.id, material.id) is None:
                raise MaterialNotFoundError("资料不存在、无权访问或未绑定当前课程。")

        knowledge_points = self.repository.list_knowledge_points(course.id)
        evidence = self._build_comparison_evidence(course.id, materials, knowledge_points)
        material_ids_with_evidence = {item.material_id for item in evidence}
        if len(material_ids_with_evidence) < 2:
            raise MaterialValidationError("至少需要两份已解析且可比较的课程资料。")

        concept_groups = self._group_evidence(evidence)
        citations = self._build_comparison_citations(evidence)
        points = [self._comparison_point(title, items) for title, items in concept_groups.items()]
        points.sort(key=self._comparison_rank, reverse=True)

        repeated = [point for point in points if len(point.material_ids) >= 2]
        exam_likely = [
            point
            for point in points
            if len(point.material_ids) >= 2 or any(self._is_exam_material(title) for title in point.source_titles)
        ]
        materials_only = [
            point
            for point in points
            if len(point.material_ids) == 1 and not any(self._is_exam_material(title) for title in point.source_titles)
        ]
        questions_only = [
            point
            for point in points
            if len(point.material_ids) == 1 and all(self._is_exam_material(title) for title in point.source_titles)
        ]
        covered_titles = {self._normalize_title(point.title) for point in points}
        missing_review = [
            MaterialComparisonPoint(
                title=point.title,
                material_ids=[],
                source_titles=[],
                reason="所选资料暂未覆盖这个课程知识点，建议补看课程资料或教师提纲。",
                confidence="low",
                support_count=0,
                knowledge_point_id=str(point.id),
            )
            for point in knowledge_points
            if self._normalize_title(point.title) not in covered_titles
        ]

        return MaterialComparisonResult(
            course_id=str(course.id),
            material_ids=[str(material_id) for material_id in unique_material_ids],
            summary=MaterialComparisonSummary(
                compared_material_count=len(unique_material_ids),
                comparable_material_count=len(material_ids_with_evidence),
                matched_concept_count=len(points),
                citation_count=len(citations),
                message="已基于课程知识切片和安全短摘录完成资料对比。",
            ),
            repeated_concepts=repeated[:8],
            exam_likely_points=exam_likely[:8],
            materials_only_points=materials_only[:8],
            questions_only_points=questions_only[:8],
            missing_review_points=missing_review[:8],
            priority_order=points[:10],
            citations=citations[:12],
        )

    def _require_course(self, user: User, course_id: int) -> Course:
        course = self.repository.get_course_for_user(user.id, course_id)
        if course is None:
            raise CourseNotFoundError("课程不存在或无权访问。")
        return course

    def _require_material(self, user: User, material_id: int) -> Material:
        material = self.repository.get_material_for_user(user.id, material_id)
        if material is None:
            raise MaterialNotFoundError("资料不存在或无权访问。")
        return material

    def _build_comparison_evidence(
        self,
        course_id: int,
        materials: list[Material],
        knowledge_points: list[KnowledgePoint],
    ) -> list[MaterialEvidence]:
        materials_by_id = {material.id: material for material in materials}
        source_ids = set(materials_by_id)
        points_by_id = {point.id: point for point in knowledge_points}
        course_materials = self.repository.list_course_materials(course_id)
        source_id_by_course_material_id = {
            course_material.id: self._safe_int((course_material.metadata_json or {}).get("source_material_id"))
            for course_material in course_materials
        }
        evidence: list[MaterialEvidence] = []

        for chunk in self.repository.list_knowledge_chunks(course_id):
            source_material_id = self._source_material_id_for_chunk(chunk, source_id_by_course_material_id)
            if source_material_id not in source_ids:
                continue
            material = materials_by_id[source_material_id]
            point = points_by_id.get(chunk.knowledge_point_id) if chunk.knowledge_point_id is not None else None
            title = point.title if point is not None else (chunk.section_title or self._title_from_text(chunk.content))
            evidence.append(
                MaterialEvidence(
                    material_id=material.id,
                    source_title=material.filename,
                    title=title,
                    content=chunk.content,
                    section_title=chunk.section_title,
                    page_number=chunk.page_number,
                    knowledge_point_id=point.id if point is not None else None,
                    confidence="high" if point is not None else "medium",
                )
            )

        material_ids_with_chunks = {item.material_id for item in evidence}
        for material in materials:
            if material.id in material_ids_with_chunks:
                continue
            if material.parse_status != "completed" or not material.extracted_text or self._extension(material.filename) not in self.light_parse_extensions:
                continue
            evidence.extend(self._fallback_text_evidence(material, knowledge_points))

        return evidence

    def _fallback_text_evidence(self, material: Material, knowledge_points: list[KnowledgePoint]) -> list[MaterialEvidence]:
        lines = [self._clean_text(part) for part in material.extracted_text.replace("\r\n", "\n").splitlines()] if material.extracted_text else []
        lines = [line for line in lines if line]
        if not lines and material.extracted_text:
            lines = [self._clean_text(material.extracted_text)]

        evidence: list[MaterialEvidence] = []
        for line in lines[:12]:
            point = next((item for item in knowledge_points if item.title and item.title in line), None)
            title = point.title if point is not None else self._title_from_text(line)
            evidence.append(
                MaterialEvidence(
                    material_id=material.id,
                    source_title=material.filename,
                    title=title,
                    content=line,
                    section_title=title,
                    page_number=None,
                    knowledge_point_id=point.id if point is not None else None,
                    confidence="medium" if point is not None else "low",
                )
            )
        return evidence

    def _source_material_id_for_chunk(
        self,
        chunk: KnowledgeChunk,
        source_id_by_course_material_id: dict[int, int | None],
    ) -> int | None:
        source_material_id = self._safe_int((chunk.metadata_json or {}).get("source_material_id"))
        if source_material_id is not None:
            return source_material_id
        return source_id_by_course_material_id.get(chunk.material_id)

    def _group_evidence(self, evidence: list[MaterialEvidence]) -> dict[str, list[MaterialEvidence]]:
        groups: dict[str, list[MaterialEvidence]] = {}
        display_titles: dict[str, str] = {}
        for item in evidence:
            title = item.title.strip() or "资料重点"
            group_key = self._normalize_title(title)
            groups.setdefault(group_key, []).append(item)
            display_title = self._display_comparison_title(title)
            current_title = display_titles.get(group_key)
            if current_title is None or self._is_exam_material(current_title):
                display_titles[group_key] = display_title
        return {display_titles.get(group_key, group_key): items for group_key, items in groups.items()}

    def _comparison_point(self, title: str, evidence: list[MaterialEvidence]) -> MaterialComparisonPoint:
        material_ids = sorted({item.material_id for item in evidence})
        source_titles = sorted({item.source_title for item in evidence})
        knowledge_point_id = next((item.knowledge_point_id for item in evidence if item.knowledge_point_id is not None), None)
        if len(material_ids) >= 2:
            reason = "多份资料重复出现，适合作为优先复习重点。"
            confidence = "high"
        elif all(self._is_exam_material(title) for title in source_titles):
            reason = "只在试题或样题类资料出现，建议作为查漏补缺题型。"
            confidence = "medium"
        else:
            reason = "只在单份资料出现，建议结合课程目标判断是否补看。"
            confidence = "medium"

        return MaterialComparisonPoint(
            title=title,
            material_ids=[str(material_id) for material_id in material_ids],
            source_titles=source_titles,
            reason=reason,
            confidence=confidence,
            support_count=len(evidence),
            knowledge_point_id=str(knowledge_point_id) if knowledge_point_id is not None else None,
        )

    def _comparison_rank(self, point: MaterialComparisonPoint) -> tuple[int, int, int, str]:
        exam_score = 1 if any(self._is_exam_material(title) for title in point.source_titles) else 0
        return (len(point.material_ids), exam_score, point.support_count, point.title)

    def _build_comparison_citations(self, evidence: list[MaterialEvidence]) -> list[MaterialComparisonCitation]:
        citations: list[MaterialComparisonCitation] = []
        seen: set[tuple[int, str]] = set()
        for item in evidence:
            key = (item.material_id, item.title)
            if key in seen:
                continue
            seen.add(key)
            citations.append(
                MaterialComparisonCitation(
                    id=f"m{item.material_id}-{len(citations) + 1}",
                    material_id=str(item.material_id),
                    source_title=item.source_title,
                    section_title=item.section_title,
                    page_number=item.page_number,
                    excerpt=self._safe_excerpt(item.content),
                    confidence=item.confidence,
                )
            )
        return citations

    def _is_exam_material(self, title: str) -> bool:
        return any(keyword in title for keyword in self.exam_title_keywords)

    def _title_from_text(self, text: str) -> str:
        cleaned = self._clean_text(text)
        for separator in ("：", ":", "。", "，", ",", " "):
            if separator in cleaned:
                candidate = cleaned.split(separator, 1)[0].strip()
                if candidate:
                    return candidate[:40]
        return cleaned[:40] or "资料重点"

    def _safe_excerpt(self, text: str, limit: int = 80) -> str:
        cleaned = self._clean_text(text)
        for marker in ("SECRET", "API Key", "系统提示词", "模型输入", "完整资料原文"):
            if marker in cleaned:
                cleaned = cleaned.split(marker, 1)[0].strip()
        if len(cleaned) <= limit:
            return cleaned
        return f"{cleaned[:limit].rstrip()}..."

    @classmethod
    def _display_comparison_title(cls, title: str) -> str:
        return cls._strip_exam_title_prefix(title).strip() or title.strip() or "资料重点"

    @classmethod
    def _normalize_title(cls, title: str) -> str:
        cleaned = cls._strip_exam_title_prefix(title)
        return "".join(cleaned.lower().split())

    @staticmethod
    def _strip_exam_title_prefix(title: str) -> str:
        cleaned = title.strip()
        for prefix in ("期末样题", "期末试题", "样题", "试题", "真题", "考试", "复习", "试题独有"):
            for separator in ("：", ":", "-", "—"):
                marker = f"{prefix}{separator}"
                if cleaned.startswith(marker):
                    return cleaned[len(marker) :].strip()
        return cleaned

    @staticmethod
    def _clean_text(text: str) -> str:
        return " ".join(text.split())

    @staticmethod
    def _safe_int(value: object) -> int | None:
        try:
            if value is None:
                return None
            return int(value)
        except (TypeError, ValueError):
            return None

    def _validate_filename(self, filename: str) -> str:
        clean_name = Path(filename).name.strip()
        if not clean_name:
            raise MaterialValidationError("文件名不能为空。")
        extension = self._extension(clean_name)
        if extension not in self.allowed_extensions:
            raise MaterialValidationError("暂不支持这种文件类型。")
        return clean_name

    def _validate_size(self, content: bytes) -> None:
        max_bytes = self.settings.material_max_upload_mb * 1024 * 1024
        if len(content) == 0:
            raise MaterialValidationError("上传文件不能为空。")
        if len(content) > max_bytes:
            raise MaterialValidationError(f"文件不能超过 {self.settings.material_max_upload_mb} MB。")

    def _extract_text(self, extension: str, content: bytes) -> tuple[str, str | None]:
        if extension in self.light_parse_extensions:
            return "completed", content.decode("utf-8", errors="replace")
        return "uploaded", None

    def _store_file(self, user_id: int, filename: str, content: bytes) -> str:
        extension = self._extension(filename)
        relative_path = Path(f"user_{user_id}") / f"{uuid4().hex}{extension}"
        storage_root = Path(self.settings.material_storage_dir)
        target_path = storage_root / relative_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(content)
        return relative_path.as_posix()

    def _build_upload_result(self, material: Material, course_id: int | None) -> MaterialUploadResult:
        item = self._build_list_item(material)
        return MaterialUploadResult(
            id=item.id,
            material_id=material.id,
            course_id=course_id,
            filename=material.filename,
            title=item.title,
            type=item.type,
            detail=item.detail,
            modified=item.modified,
            size=item.size,
            parse_status=material.parse_status,
        )

    def _build_list_item(self, material: Material) -> MaterialListItem:
        extension = self._extension(material.filename)
        course_ids = sorted({str(link.course_id) for link in material.course_links})
        return MaterialListItem(
            id=str(material.id),
            title=material.filename,
            type=self._material_type(material),
            detail=self._detail_for_status(material.parse_status, extension),
            modified=self._date_label(material.created_at),
            size=str((material.metadata_json or {}).get("size_label") or ""),
            category="image" if extension in self.image_extensions else "document",
            extension=extension.lstrip(".").upper() or "FILE",
            parse_status=material.parse_status,
            course_ids=course_ids,
        )

    @classmethod
    def _detail_for_status(cls, parse_status: str, extension: str) -> str:
        if extension in cls.image_extensions:
            return "仅入库，暂不做 OCR"
        labels = {
            "completed": "已解析",
            "uploaded": "等待解析",
            "pending": "等待解析",
            "parsing": "解析中",
            "failed": "解析失败",
        }
        return labels.get(parse_status, parse_status)

    @classmethod
    def _material_type(cls, material: Material) -> str:
        extension = cls._extension(material.filename).lstrip(".").upper()
        if extension:
            return extension
        if "/" in material.content_type:
            return material.content_type.rsplit("/", 1)[-1].upper()[:5] or "FILE"
        return "FILE"

    @staticmethod
    def _extension(filename: str) -> str:
        return Path(filename).suffix.lower()

    @staticmethod
    def _format_size(size: int) -> str:
        if size >= 1024 * 1024:
            return f"{size / 1024 / 1024:.1f} MB"
        if size >= 1024:
            return f"{(size + 1023) // 1024} KB"
        return f"{size} B"

    @staticmethod
    def _date_label(value: datetime | None) -> str:
        if value is None:
            return "今天"
        current = datetime.now(UTC)
        comparable = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
        if comparable.date() == current.date():
            return "今天"
        if (current.date() - comparable.date()).days == 1:
            return "昨天"
        return comparable.strftime("%m-%d")

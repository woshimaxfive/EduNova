from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from backend.app.core.config import Settings, get_settings
from backend.app.models import Course, CourseMaterialLink, Material, User
from backend.app.schemas.materials import (
    AttachCourseMaterialsResult,
    MaterialDetail,
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


class MaterialRepository(Protocol):
    def get_course_for_user(self, user_id: int, course_id: int) -> Course | None: ...

    def add_material(self, material: Material) -> None: ...

    def get_material_for_user(self, user_id: int, material_id: int) -> Material | None: ...

    def list_materials(self, user_id: int, course_id: int | None = None, unassigned: bool = False) -> list[Material]: ...

    def get_link(self, course_id: int, material_id: int) -> CourseMaterialLink | None: ...

    def add_link(self, link: CourseMaterialLink) -> CourseMaterialLink: ...

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

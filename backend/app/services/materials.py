from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
import re
from uuid import uuid4

from backend.app.agents.runtime import AgentTraceRecorder
from backend.app.api.errors import make_trace_id
from backend.app.core.config import Settings, get_settings
from backend.app.models import Course, CourseMaterialLink, KnowledgePoint, Material, MaterialChunk, MaterialComparisonRun, User
from backend.app.schemas.materials import (
    AttachCourseMaterialsResult,
    MaterialDetail,
    MaterialComparisonResult,
    MaterialListItem,
    MaterialLinkedCourse,
    MaterialProgress,
    MaterialSectionSummary,
    MaterialUploadResult,
    MaterialOutlineResponse,
    MaterialOutlineSection,
    MaterialOutlineChunk,
    UpdateMaterialOutlineRequest,
)
from backend.app.services.material_parsers import DocumentParseError, DocumentParser
from backend.app.services.material_contracts import (
    CourseNotFoundError,
    MaterialEvidence,
    MaterialModelService,
    MaterialNotFoundError,
    MaterialRepository,
    MaterialValidationError,
)
from backend.app.services.material_comparison_builder import MaterialComparisonBuilder
from backend.app.services.material_repository import SqlAlchemyMaterialRepository as SqlAlchemyMaterialRepository
from backend.app.services.material_retrieval import MaterialChunkingService
from backend.app.services.storage import StorageAdapter, build_storage
from backend.app.services.upload_security import MalwareScanner, UploadSecurityError, build_malware_scanner, validate_upload_type


class MaterialService:
    validation_error = MaterialValidationError
    not_found_error = MaterialNotFoundError
    allowed_extensions = {".txt", ".md", ".markdown", ".pdf", ".doc", ".docx", ".ppt", ".pptx", ".png", ".jpg", ".jpeg", ".webp"}
    light_parse_extensions = {".txt", ".md", ".markdown"}
    deep_parse_extensions = {".pdf", ".docx", ".pptx"}
    parsed_text_extensions = light_parse_extensions | deep_parse_extensions
    image_extensions = {".png", ".jpg", ".jpeg", ".webp"}
    exam_title_keywords = ("期末", "复习", "试题", "样题", "真题", "考试", "练习")

    def __init__(
        self,
        repository: MaterialRepository,
        settings: Settings | None = None,
        parser: DocumentParser | None = None,
        chunking_service: MaterialChunkingService | None = None,
        model_service: MaterialModelService | None = None,
        trace_recorder: AgentTraceRecorder | None = None,
        storage: StorageAdapter | None = None,
        malware_scanner: MalwareScanner | None = None,
    ) -> None:
        self.repository = repository
        self.settings = settings or get_settings()
        self.parser = parser or DocumentParser()
        self.chunking_service = chunking_service or MaterialChunkingService()
        self.model_service = model_service
        self.trace_recorder = trace_recorder
        self.storage = storage or build_storage(self.settings, kind="materials")
        self.malware_scanner = malware_scanner or build_malware_scanner(self.settings)
        self.comparison_builder = MaterialComparisonBuilder(
            repository,
            parsed_text_extensions=self.parsed_text_extensions,
            exam_title_keywords=self.exam_title_keywords,
        )

    def upload_material(
        self,
        user: User,
        filename: str,
        content_type: str,
        content: bytes,
        course_id: int | None = None,
        defer_ingestion: bool = False,
    ) -> MaterialUploadResult:
        clean_name = self._validate_filename(filename)
        extension = self._extension(clean_name)
        self._validate_size(content)
        try:
            validate_upload_type(clean_name, content_type, content)
            self.malware_scanner.scan(content)
        except UploadSecurityError as exc:
            raise MaterialValidationError(str(exc)) from exc
        course = self._require_course(user, course_id) if course_id is not None else None
        if defer_ingestion and extension in self.parsed_text_extensions:
            parse_status, extracted_text = "pending", None
        else:
            parse_status, extracted_text = self._extract_text(extension, content)
        relative_path = self._store_file(user.id, clean_name, content, content_type)
        agent_trace_id = make_trace_id()
        metadata = {
            "size_bytes": len(content),
            "size_label": self._format_size(len(content)),
            "extension": extension.lstrip(".").upper() or "FILE",
            "detail": self._detail_for_status(parse_status, extension),
            "agent_trace_id": agent_trace_id,
        }
        material = Material(
            user_id=user.id,
            filename=clean_name,
            content_type=content_type or "application/octet-stream",
            storage_path=relative_path,
            parse_status=parse_status,
            agent_trace_id=agent_trace_id,
            extracted_text=extracted_text,
            metadata_json=metadata,
            ingestion_status=(
                "stored"
                if extension in self.image_extensions
                else "pending" if defer_ingestion and extension in self.parsed_text_extensions else "legacy"
            ),
            outline_version=0,
            outline_json={},
            quality_json={},
        )

        try:
            self.repository.add_material(material)
            chunks = [] if defer_ingestion else self.chunking_service.build_chunks(material)
            if chunks:
                self.repository.add_material_chunks(chunks)
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
        preview_text = re.sub(r"<!--.*?-->", "", material.extracted_text, flags=re.DOTALL).strip() if material.extracted_text else ""
        preview = preview_text[:500] or None
        chunks = self.repository.list_material_chunks(user.id, material.id)
        linked_courses = self.repository.list_material_course_links(user.id, material.id)
        sections = self._build_section_summaries(chunks)
        page_numbers = [chunk.page_number for chunk in chunks if chunk.page_number is not None]
        return MaterialDetail(
            **item.model_dump(),
            filename=material.filename,
            content_type=material.content_type,
            extracted_text_preview=preview,
            chunk_count=len(chunks),
            section_count=len(sections),
            page_count=max(page_numbers) if page_numbers else None,
            sections=sections[:20],
            linked_courses=[
                MaterialLinkedCourse(id=str(course.id), title=course.title, usage_type=link.usage_type)
                for link, course in linked_courses
            ],
            agent_trace_id=material.agent_trace_id,
            parser_version=material.parser_version,
        )

    def delete_material(self, user: User, material_id: int) -> None:
        material = self._require_material(user, material_id)
        storage_path = material.storage_path
        # Keep deletion retryable: a storage outage must not remove the database
        # record while leaving a private object that can no longer be addressed.
        self.storage.delete(storage_path)
        try:
            self.repository.delete_material(material)
            self.repository.commit()
        except Exception:
            self.repository.rollback()
            raise

    def get_outline(self, user: User, material_id: int) -> MaterialOutlineResponse:
        material = self._require_material(user, material_id)
        outline = dict(material.outline_json or {})
        sections = [item for item in outline.get("sections", []) if isinstance(item, dict)]
        chunks = self.repository.list_material_chunks(user.id, material.id)
        section_by_id = {str(item.get("id")): item for item in sections}
        return MaterialOutlineResponse(
            material_id=str(material.id),
            filename=material.filename,
            ingestion_status=material.ingestion_status,
            parser_version=material.parser_version,
            version=int(material.outline_version or 0),
            confirmed=bool(outline.get("confirmed")),
            quality=dict(material.quality_json or {}),
            warnings=[str(item) for item in (material.quality_json or {}).get("warnings", [])],
            sections=[MaterialOutlineSection(**item) for item in sections],
            chunks=[
                MaterialOutlineChunk(
                    id=f"chunk-{chunk.chunk_index + 1}",
                    chunk_index=chunk.chunk_index,
                    section_id=str((chunk.metadata_json or {}).get("section_id") or ""),
                    section_path=list(chunk.section_path_json or []),
                    start_page=chunk.page_number,
                    end_page=chunk.end_page_number,
                    chunk_type=chunk.chunk_type,
                    content=chunk.content,
                    quality=dict(chunk.quality_json or {}),
                )
                for chunk in chunks
                if str((chunk.metadata_json or {}).get("section_id") or "") in section_by_id
            ],
        )

    def update_outline(self, user: User, material_id: int, request: UpdateMaterialOutlineRequest) -> MaterialOutlineResponse:
        material = self._require_material(user, material_id)
        if material.ingestion_status not in {"awaiting_confirmation", "confirmed"}:
            raise MaterialValidationError("资料尚未完成精细解析。")
        if int(material.outline_version or 0) != request.version:
            raise MaterialValidationError("目录已被其他操作更新，请刷新后重试。")
        outline = dict(material.outline_json or {})
        sections = [dict(item) for item in outline.get("sections", []) if isinstance(item, dict)]
        chunks = self.repository.list_material_chunks(user.id, material.id)
        by_id = {str(item.get("id")): item for item in sections}
        for operation in request.operations:
            if operation.type == "rename":
                section = by_id.get(str(operation.section_id or ""))
                title = " ".join(str(operation.title or "").split())[:255]
                if section is None or not title:
                    raise MaterialValidationError("需要指定有效章节和新标题。")
                section["title"] = title
            elif operation.type == "include":
                section = by_id.get(str(operation.section_id or ""))
                if section is None or operation.included is None:
                    raise MaterialValidationError("需要指定有效章节和包含状态。")
                section["included"] = bool(operation.included)
            elif operation.type == "merge":
                selected = [by_id.get(item) for item in operation.section_ids]
                selected = [item for item in selected if item is not None]
                indexes = sorted(sections.index(item) for item in selected)
                if len(indexes) < 2 or indexes != list(range(indexes[0], indexes[-1] + 1)):
                    raise MaterialValidationError("只能合并相邻章节。")
                target = sections[indexes[0]]
                merged_ids = {str(item["id"]) for item in selected}
                target["title"] = " ".join(str(operation.title or target["title"]).split())[:255]
                target["end_page"] = max((item.get("end_page") or 0 for item in selected), default=target.get("end_page")) or None
                target["chunk_indexes"] = sorted({index for item in selected for index in item.get("chunk_indexes", [])})
                sections = [item for item in sections if str(item["id"]) not in merged_ids or item is target]
                for chunk in chunks:
                    if str((chunk.metadata_json or {}).get("section_id")) in merged_ids:
                        chunk.metadata_json = {**(chunk.metadata_json or {}), "section_id": target["id"]}
                        chunk.section_title = target["title"]
            elif operation.type == "split":
                section = by_id.get(str(operation.section_id or ""))
                title = " ".join(str(operation.title or "").split())[:255]
                split_index = operation.chunk_index
                indexes = list(section.get("chunk_indexes", [])) if section else []
                if section is None or not title or split_index not in indexes or indexes.index(split_index) == 0:
                    raise MaterialValidationError("请在章节内部的有效切片边界拆分。")
                position = indexes.index(split_index)
                new_id = f"section-{max([self._safe_int(str(item.get('id', '')).split('-')[-1]) or 0 for item in sections] + [0]) + 1}"
                new_indexes = indexes[position:]
                section["chunk_indexes"] = indexes[:position]
                new_section = {
                    **section,
                    "id": new_id,
                    "title": title,
                    "path": [*list(section.get("path", []))[:-1], title],
                    "start_page": next((chunk.page_number for chunk in chunks if chunk.chunk_index == split_index), section.get("start_page")),
                    "chunk_indexes": new_indexes,
                    "confidence": 1.0,
                }
                sections.insert(sections.index(section) + 1, new_section)
                for chunk in chunks:
                    if chunk.chunk_index in new_indexes:
                        chunk.metadata_json = {**(chunk.metadata_json or {}), "section_id": new_id}
                        chunk.section_title = title
            else:
                raise MaterialValidationError("不支持的目录编辑操作。")
            by_id = {str(item.get("id")): item for item in sections}
        self._rebuild_outline_paths(sections, chunks)
        material.outline_version = int(material.outline_version or 0) + 1
        material.outline_json = {
            "sections": sections,
            "confirmed": False,
            "classification": dict((material.outline_json or {}).get("classification") or {}),
        }
        material.ingestion_status = "awaiting_confirmation"
        self.repository.commit()
        self.repository.refresh(material)
        return self.get_outline(user, material_id)

    def confirm_outline(self, user: User, material_id: int, version: int) -> MaterialOutlineResponse:
        material = self._require_material(user, material_id)
        if material.parse_status != "completed" or material.ingestion_status != "awaiting_confirmation":
            raise MaterialValidationError("资料正在解析或目录尚未就绪，请等待完成后再确认。")
        if int(material.outline_version or 0) != version:
            raise MaterialValidationError("目录版本已变化，请刷新后重新确认。")
        if not bool((material.quality_json or {}).get("passed")):
            raise MaterialValidationError("资料解析质量未通过，不能用于建课。")
        sections = [item for item in (material.outline_json or {}).get("sections", []) if isinstance(item, dict)]
        if not any(bool(item.get("included", True)) and item.get("chunk_indexes") for item in sections):
            raise MaterialValidationError("至少保留一个包含正文的章节。")
        included_ids = {str(item.get("id")) for item in sections if bool(item.get("included", True))}
        for chunk in self.repository.list_material_chunks(user.id, material.id):
            section_id = str((chunk.metadata_json or {}).get("section_id") or "")
            chunk.quality_json = {**(chunk.quality_json or {}), "included": section_id in included_ids}
        material.outline_json = {
            "sections": sections,
            "confirmed": True,
            "confirmed_at": datetime.now(UTC).isoformat(),
            "classification": dict((material.outline_json or {}).get("classification") or {}),
        }
        material.ingestion_status = "confirmed"
        material.metadata_json = {**(material.metadata_json or {}), "detail": "目录已确认，可生成课程"}
        self.repository.commit()
        self.repository.refresh(material)
        return self.get_outline(user, material_id)

    @staticmethod
    def _rebuild_outline_paths(sections: list[dict], chunks: list[MaterialChunk]) -> None:
        stack: list[str] = []
        for section in sections:
            level = max(1, min(6, int(section.get("level") or 1)))
            stack = stack[: level - 1]
            stack.append(str(section.get("title") or "未命名章节"))
            section["path"] = list(stack)
            for chunk in chunks:
                if str((chunk.metadata_json or {}).get("section_id")) == str(section.get("id")):
                    chunk.section_path_json = list(stack)
                    chunk.section_title = section["title"]

    @staticmethod
    def _build_section_summaries(chunks: list[MaterialChunk]) -> list[MaterialSectionSummary]:
        grouped: dict[tuple[str, int | None], list[MaterialChunk]] = {}
        for chunk in chunks:
            title = (chunk.section_title or "正文").strip() or "正文"
            grouped.setdefault((title, chunk.page_number), []).append(chunk)

        summaries: list[MaterialSectionSummary] = []
        for (title, page_number), section_chunks in grouped.items():
            normalized_preview = " ".join(section_chunks[0].content.split())[:180]
            summaries.append(
                MaterialSectionSummary(
                    section_title=title,
                    page_number=page_number,
                    chunk_count=len(section_chunks),
                    preview=normalized_preview,
                )
            )
        return summaries

    def get_progress(self, user: User, material_id: int) -> MaterialProgress:
        material = self._require_material(user, material_id)
        ingestion_labels = {
            "stored": (100, "图片已入库，可用于图片提问"),
            "pending": (5, "等待精细解析"),
            "running": (45, "正在精细解析资料结构"),
            "awaiting_confirmation": (90, "解析完成，等待确认目录"),
            "confirmed": (100, "目录已确认，可生成课程"),
            "failed": (0, "精细解析未通过"),
            "legacy": (100 if material.parse_status == "completed" else 10, "旧版解析，可按需重新解析"),
        }
        if material.ingestion_status in ingestion_labels:
            progress, message = ingestion_labels[material.ingestion_status]
            return MaterialProgress(status=material.ingestion_status, progress_percent=progress, message=message)
        if material.parse_status == "completed":
            return MaterialProgress(status="completed", progress_percent=100, message="资料解析已完成")
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
        from backend.app.agents.material_comparison import MaterialComparisonGraphRunner

        return MaterialComparisonGraphRunner(self).run(user=user, course_id=course_id, material_ids=material_ids)

    def get_comparison(self, user: User, comparison_id: int) -> MaterialComparisonResult:
        run = self.repository.get_comparison_run_for_user(user.id, comparison_id)
        if run is None:
            raise MaterialNotFoundError("资料对比记录不存在或无权访问。")
        return self._comparison_run_to_api(run)

    def get_latest_comparison(self, user: User, course_id: int) -> MaterialComparisonResult | None:
        self._require_course(user, course_id)
        run = self.repository.get_latest_comparison_run(user.id, course_id)
        return self._comparison_run_to_api(run) if run is not None else None

    def _prepare_comparison(
        self,
        user: User,
        course_id: int,
        material_ids: list[int],
    ) -> tuple[Course, list[Material], list[KnowledgePoint], list[MaterialEvidence]]:
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

        return course, materials, knowledge_points, evidence

    def _build_deterministic_comparison(
        self,
        course: Course,
        material_ids: list[int],
        knowledge_points: list[KnowledgePoint],
        evidence: list[MaterialEvidence],
    ) -> MaterialComparisonResult:
        return self.comparison_builder.build_result(course, material_ids, knowledge_points, evidence)

    @staticmethod
    def _comparison_run_to_api(run: MaterialComparisonRun) -> MaterialComparisonResult:
        return MaterialComparisonBuilder.run_to_api(run)
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
        return self.comparison_builder.build_evidence(course_id, materials, knowledge_points)

    def _group_evidence(self, evidence: list[MaterialEvidence]) -> dict[str, list[MaterialEvidence]]:
        return self.comparison_builder.group_evidence(evidence)

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
        if extension in self.parsed_text_extensions:
            try:
                extracted_text = self.parser.extract_text(extension, content)
            except DocumentParseError:
                return "failed", None
            if extracted_text.strip():
                return "completed", extracted_text
            return "uploaded", None
        return "uploaded", None

    def _store_file(self, user_id: int, filename: str, content: bytes, content_type: str) -> str:
        extension = self._extension(filename)
        relative_path = Path(f"user_{user_id}") / f"{uuid4().hex}{extension}"
        return self.storage.put_bytes(relative_path.as_posix(), content, content_type=content_type)

    def _build_upload_result(self, material: Material, course_id: int | None) -> MaterialUploadResult:
        item = self._build_list_item(material)
        return MaterialUploadResult(
            id=item.id,
            material_id=material.id,
            course_id=course_id,
            agent_trace_id=getattr(material, "agent_trace_id", None),
            filename=material.filename,
            title=item.title,
            type=item.type,
            detail=item.detail,
            modified=item.modified,
            size=item.size,
            parse_status=material.parse_status,
            ingestion_status=material.ingestion_status,
            category=item.category,
            quality_summary=dict(material.quality_json or {}),
        )

    def _build_list_item(self, material: Material) -> MaterialListItem:
        extension = self._extension(material.filename)
        metadata = material.metadata_json or {}
        course_ids = sorted({str(link.course_id) for link in material.course_links})
        return MaterialListItem(
            id=str(material.id),
            title=material.filename,
            type=self._material_type(material),
            detail=str(metadata.get("detail") or self._detail_for_status(material.parse_status, extension)),
            modified=self._date_label(material.created_at),
            size=str(metadata.get("size_label") or ""),
            category="image" if extension in self.image_extensions else "document",
            extension=extension.lstrip(".").upper() or "FILE",
            parse_status=material.parse_status,
            ingestion_status=material.ingestion_status,
            outline_version=int(material.outline_version or 0),
            outline_confirmed=bool((material.outline_json or {}).get("confirmed")),
            quality_summary=dict(material.quality_json or {}),
            course_ids=course_ids,
        )

    @classmethod
    def _detail_for_status(cls, parse_status: str, extension: str) -> str:
        if extension in cls.image_extensions:
            return "已入库，可用于图片提问"
        if parse_status == "uploaded" and extension in {".doc", ".ppt"}:
            return "旧版 Office 格式暂不支持深度解析"
        if parse_status == "uploaded" and extension in cls.deep_parse_extensions:
            return "未检测到可抽取文本，暂不支持扫描件 OCR"
        labels = {
            "completed": "已解析",
            "uploaded": "等待解析",
            "pending": "等待解析",
            "parsing": "解析中",
            "failed": "解析失败",
            "awaiting_confirmation": "解析完成，等待确认目录",
            "confirmed": "目录已确认，可生成课程",
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

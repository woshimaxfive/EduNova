from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
import re
from time import perf_counter
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from sqlalchemy import delete
from sqlalchemy.orm import Session

from backend.app.agents.learning_review import parse_json_object, safe_text
from backend.app.agents.runtime import AgentTraceRecorder
from backend.app.core.config import Settings, get_settings
from backend.app.models import Material, MaterialChunk, User
from backend.app.services.material_parsers import (
    DocumentParseError,
    DocumentStructureExtractor,
    ParsedDocument,
    create_document_structure_extractor,
)
from backend.app.services.storage import build_storage


class MaterialIngestionError(RuntimeError):
    def __init__(self, message: str, *, quality: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.quality = dict(quality or {})


class MaterialIngestionState(TypedDict, total=False):
    trace_id: str
    user: User
    user_id: int
    material: Material
    extension: str
    content: bytes
    document: ParsedDocument
    normalized_blocks: list[dict[str, Any]]
    sections: list[dict[str, Any]]
    chunks: list[dict[str, Any]]
    quality: dict[str, Any]
    warnings: list[str]
    result: dict[str, Any]
    job_context: Any


class MaterialIngestionGraphRunner:
    workflow = "material_ingestion"
    parser_version = "material-ingestion-v2"
    node_progress = {
        "validate": (6, "资料已校验"),
        "extract_pages": (20, "已提取正文与页码"),
        "normalize_layout": (34, "已清理版面噪声"),
        "detect_outline": (50, "已识别目录结构"),
        "model_refine": (60, "已校正目录层级"),
        "chunk": (75, "已生成章节切片"),
        "quality_gate": (88, "已完成解析质检"),
        "persist": (100, "资料待确认"),
    }

    def __init__(
        self,
        db: Session,
        *,
        settings: Settings | None = None,
        parser: DocumentStructureExtractor | None = None,
        model_service: Any | None = None,
        trace_recorder: AgentTraceRecorder | None = None,
    ) -> None:
        self.db = db
        self.settings = settings or get_settings()
        self.parser = parser or create_document_structure_extractor(
            parser_name=self.settings.edunova_document_parser,
            artifacts_path=self.settings.docling_artifacts_path,
            timeout_seconds=self.settings.docling_document_timeout_seconds,
        )
        self.model_service = model_service
        self.trace_recorder = trace_recorder or AgentTraceRecorder()
        self.graph = self._build_graph()

    def run(self, *, user: User, material: Material, trace_id: str, job_context: Any | None = None) -> dict[str, Any]:
        state: MaterialIngestionState = {
            "trace_id": trace_id,
            "user": user,
            "user_id": user.id,
            "material": material,
            "extension": Path(material.filename).suffix.lower(),
            "warnings": [],
            "job_context": job_context,
        }
        return self.graph.invoke(state)["result"]

    def _build_graph(self):
        graph = StateGraph(MaterialIngestionState)
        graph.add_node("validate", self._validate)
        graph.add_node("extract_pages", self._extract_pages)
        graph.add_node("normalize_layout", self._normalize_layout)
        graph.add_node("detect_outline", self._detect_outline)
        graph.add_node("model_refine", self._model_refine)
        graph.add_node("chunk", self._chunk)
        graph.add_node("quality_gate", self._quality_gate)
        graph.add_node("persist", self._persist)
        graph.add_edge(START, "validate")
        for current, following in zip(
            ("validate", "extract_pages", "normalize_layout", "detect_outline", "model_refine", "chunk", "quality_gate"),
            ("extract_pages", "normalize_layout", "detect_outline", "model_refine", "chunk", "quality_gate", "persist"),
            strict=True,
        ):
            graph.add_edge(current, following)
        graph.add_edge("persist", END)
        return graph.compile()

    def _validate(self, state: MaterialIngestionState) -> dict[str, Any]:
        def work() -> dict[str, Any]:
            material = state["material"]
            if material.user_id != state["user_id"]:
                raise MaterialIngestionError("资料不存在或无权访问。")
            if state["extension"] not in {".pdf", ".docx", ".pptx", ".txt", ".md", ".markdown"}:
                raise MaterialIngestionError("当前文件格式不支持精细解析。")
            storage = build_storage(self.settings, kind="materials")
            if not storage.exists(material.storage_path):
                raise MaterialIngestionError("资料原文件不存在，无法重新解析。")
            content = storage.read_bytes(material.storage_path)
            if not content:
                raise MaterialIngestionError("资料原文件为空。")
            return {"content": content}

        return self._node(state, "validate", 1, work)

    def _extract_pages(self, state: MaterialIngestionState) -> dict[str, Any]:
        def work() -> dict[str, Any]:
            try:
                document = self.parser.parse_document(state["extension"], state["content"])
            except DocumentParseError as exc:
                raise MaterialIngestionError("资料无法提取可读文本；扫描件暂不支持 OCR。") from exc
            return {"document": document}

        return self._node(state, "extract_pages", 2, work)

    def _normalize_layout(self, state: MaterialIngestionState) -> dict[str, Any]:
        def work() -> dict[str, Any]:
            document = state["document"]
            edge_lines: Counter[str] = Counter()
            for page in document.pages:
                lines = [self._line(line) for line in page.text.splitlines() if self._line(line)]
                for line in [*lines[:2], *lines[-2:]]:
                    if 2 <= len(line) <= 80:
                        edge_lines[line] += 1
            repeated = {line for line, count in edge_lines.items() if count >= max(3, round(len(document.pages) * 0.2))}
            normalized: list[dict[str, Any]] = []
            for block in document.blocks:
                lines = [self._line(line) for line in block.text.splitlines()]
                lines = [line for line in lines if line and line not in repeated and not self._is_page_number(line)]
                if not lines:
                    continue
                text = "\n".join(lines)
                normalized.append({
                    "text": text,
                    "page_number": block.page_number,
                    "kind": block.kind,
                    "heading_level": block.heading_level,
                })
            if not normalized:
                raise MaterialIngestionError("版面清理后没有可用于学习的正文。")
            return {"normalized_blocks": normalized}

        return self._node(state, "normalize_layout", 3, work)

    def _detect_outline(self, state: MaterialIngestionState) -> dict[str, Any]:
        def work() -> dict[str, Any]:
            sections: list[dict[str, Any]] = []
            current: dict[str, Any] | None = None
            stack: list[str] = []
            seen_chapters: set[str] = set()
            for block in state["normalized_blocks"]:
                parts = block["text"].splitlines()
                for part in parts:
                    level = block.get("heading_level") if block.get("kind") == "heading" else self._heading_level(part)
                    if level is not None and current and not self._chapter_number(part):
                        current_chapter = self._chapter_number(current["path"][0] if current["path"] else current["title"])
                        section_chapter = self._section_chapter_number(part)
                        if current_chapter and section_chapter and current_chapter != section_chapter:
                            level = None
                    if level is None and current and (chapter_number := self._chapter_number(current["path"][0] if current["path"] else current["title"])):
                        repaired_heading = self._repair_missing_chapter_heading(part, chapter_number)
                        if repaired_heading:
                            part = repaired_heading
                            level = self._heading_level(part)
                    if level is not None:
                        title = self._normalize_heading(part)
                        if not title:
                            continue
                        chapter_number = self._chapter_number(title)
                        if chapter_number and chapter_number in seen_chapters:
                            continue
                        if chapter_number:
                            if not seen_chapters:
                                for existing in sections:
                                    existing["included"] = False
                                    if existing["title"] == "正文":
                                        existing["title"] = "前置内容"
                                        existing["path"] = ["前置内容"]
                            seen_chapters.add(chapter_number)
                        stack = stack[: max(0, level - 1)]
                        stack.append(title)
                        current = {
                            "id": f"section-{len(sections) + 1}",
                            "title": title[:255],
                            "level": level,
                            "path": list(stack),
                            "start_page": block.get("page_number"),
                            "end_page": block.get("page_number"),
                            "confidence": 0.96 if block.get("heading_level") else 0.82,
                            "included": not self._excluded_by_default(title),
                            "_title_merged": bool(chapter_number and title != f"第{chapter_number}章"),
                            "blocks": [],
                        }
                        sections.append(current)
                        continue
                    if (
                        current
                        and self._chapter_number(current["title"])
                        and not current["blocks"]
                        and not current.get("_title_merged")
                        and self._is_chapter_title_line(part)
                    ):
                        chapter_title = self._line(part)
                        if chapter_title.endswith("二叉"):
                            chapter_title += "树"
                        current["title"] = f"{current['title']} {chapter_title}"[:255]
                        current["path"][-1] = current["title"]
                        stack[-1] = current["title"]
                        current["_title_merged"] = True
                        continue
                    if current is None:
                        current = {
                            "id": "section-1",
                            "title": "正文",
                            "level": 1,
                            "path": ["正文"],
                            "start_page": block.get("page_number"),
                            "end_page": block.get("page_number"),
                            "confidence": 0.55,
                            "included": False,
                            "blocks": [],
                        }
                        sections.append(current)
                    current["blocks"].append({"text": part, "page_number": block.get("page_number")})
                    if block.get("page_number") is not None:
                        current["end_page"] = block["page_number"]
            sections = [section for section in sections if section["blocks"] or section["title"] != "正文"]
            if not sections:
                raise MaterialIngestionError("没有识别到有效章节。")
            return {"sections": sections}

        return self._node(state, "detect_outline", 4, work)

    def _model_refine(self, state: MaterialIngestionState) -> dict[str, Any]:
        def work() -> dict[str, Any]:
            sections = state["sections"]
            ambiguous = [section for section in sections if section["confidence"] < 0.7][:40]
            if not ambiguous or self.model_service is None:
                return {"sections": sections, "warnings": [*state["warnings"], "目录层级由确定性规则识别，可在确认前人工调整。"]}
            payload = [{"id": item["id"], "title": item["title"], "level": item["level"]} for item in ambiguous]
            try:
                raw = self.model_service.chat_completion(
                    state["user"],
                    [
                        {"role": "system", "content": "你是资料目录校正器。只输出 JSON，不得增加不存在的标题。"},
                        {"role": "user", "content": f"校正这些候选标题的层级，返回 sections 数组，每项仅含 id、title、level：{payload}"},
                    ],
                )
                parsed = parse_json_object(raw)
                updates = parsed.get("sections") if isinstance(parsed, dict) else None
            except Exception:
                updates = None
            if not isinstance(updates, list):
                return {"sections": sections, "warnings": [*state["warnings"], "模型目录校正不可用，已保留规则结果。"]}
            by_id = {str(item.get("id")): item for item in updates if isinstance(item, dict)}
            for section in sections:
                update = by_id.get(section["id"])
                if not update:
                    continue
                title = safe_text(update.get("title"), limit=255)
                level = update.get("level")
                if title and self._similar_heading(title, section["title"]):
                    section["title"] = title
                if isinstance(level, int) and 1 <= level <= 6:
                    section["level"] = level
                section["confidence"] = max(section["confidence"], 0.78)
            self._rebuild_paths(sections)
            return {"sections": sections}

        return self._node(state, "model_refine", 5, work)

    def _chunk(self, state: MaterialIngestionState) -> dict[str, Any]:
        def work() -> dict[str, Any]:
            chunks: list[dict[str, Any]] = []
            for section in state["sections"]:
                section_chunks = self._chunk_section(section)
                for item in section_chunks:
                    item["chunk_index"] = len(chunks)
                    item["id"] = f"chunk-{len(chunks) + 1}"
                    chunks.append(item)
                section["chunk_indexes"] = [item["chunk_index"] for item in section_chunks]
            if not chunks:
                raise MaterialIngestionError("没有生成可用于检索和建课的正文切片。")
            return {"chunks": chunks, "sections": state["sections"]}

        return self._node(state, "chunk", 6, work)

    def _quality_gate(self, state: MaterialIngestionState) -> dict[str, Any]:
        def work() -> dict[str, Any]:
            document = state["document"]
            chunks = state["chunks"]
            page_count = len(document.pages) or max((item.get("end_page") or 1 for item in chunks), default=1)
            readable_pages = sum(1 for page in document.pages if len(re.sub(r"\s+", "", page.text)) >= 20) if document.pages else page_count
            readable_ratio = readable_pages / page_count if page_count else 0.0
            combined = "".join(item["content"] for item in chunks)
            abnormal_count = combined.count("�") + len(re.findall(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", combined))
            abnormal_ratio = abnormal_count / max(1, len(combined))
            hashes = [item["content_hash"] for item in chunks]
            duplicate_ratio = 1 - len(set(hashes)) / max(1, len(hashes))
            meaningful = [section for section in state["sections"] if section.get("included") and section.get("title") not in {"正文", "未命名章节"}]
            top_level = [section for section in meaningful if section.get("level") == 1]
            empty_section_ratio = sum(1 for section in meaningful if not section.get("chunk_indexes")) / max(1, len(meaningful))
            section_density = len(meaningful) / max(1, page_count)
            page_aware_required = state["extension"] in {".pdf", ".pptx"}
            missing_pages = page_aware_required and any(item.get("start_page") is None for item in chunks)
            risks: list[str] = []
            if readable_ratio < 0.70:
                risks.append("low_readable_page_ratio")
            if abnormal_ratio > 0.005:
                risks.append("abnormal_character_ratio")
            if duplicate_ratio > 0.10:
                risks.append("duplicate_chunks")
            if page_count >= 20 and len(meaningful) <= 1:
                risks.append("missing_meaningful_outline")
            if page_count >= 20 and (section_density > 0.75 or empty_section_ratio > 0.20):
                risks.append("noisy_outline")
            if page_count >= 20 and len(top_level) > max(20, round(page_count * 0.12)):
                risks.append("too_many_top_level_sections")
            if missing_pages:
                risks.append("missing_page_numbers")
            warnings = list(state["warnings"])
            if 0.70 <= readable_ratio < 0.85:
                warnings.append("部分页面文本较少，请在目录确认前检查切片内容。")
            quality = {
                "passed": not risks,
                "page_count": page_count,
                "readable_page_count": readable_pages,
                "readable_page_ratio": round(readable_ratio, 4),
                "section_count": len(state["sections"]),
                "included_section_count": sum(1 for item in state["sections"] if item.get("included")),
                "top_level_section_count": len(top_level),
                "chunk_count": len(chunks),
                "section_density": round(section_density, 4),
                "empty_section_ratio": round(empty_section_ratio, 4),
                "abnormal_character_ratio": round(abnormal_ratio, 6),
                "duplicate_chunk_ratio": round(duplicate_ratio, 4),
                "risk_flags": risks,
                "warnings": list(dict.fromkeys(warnings)),
            }
            if risks:
                raise MaterialIngestionError(
                    "资料解析质量未通过，原文件已保留，可调整文件后重试。",
                    quality=quality,
                )
            return {"quality": quality, "warnings": quality["warnings"]}

        return self._node(state, "quality_gate", 7, work)

    def _persist(self, state: MaterialIngestionState) -> dict[str, Any]:
        def work() -> dict[str, Any]:
            material = state["material"]
            self.db.execute(delete(MaterialChunk).where(MaterialChunk.material_id == material.id))
            for item in state["chunks"]:
                section = next(section for section in state["sections"] if section["id"] == item["section_id"])
                self.db.add(MaterialChunk(
                    material_id=material.id,
                    chunk_index=item["chunk_index"],
                    section_title=section["title"],
                    page_number=item.get("start_page"),
                    end_page_number=item.get("end_page"),
                    section_path_json=list(section["path"]),
                    chunk_type=item["chunk_type"],
                    content_hash=item["content_hash"],
                    quality_json=dict(item["quality"]),
                    content=item["content"],
                    embedding=None,
                    metadata_json={
                        "source_filename": material.filename,
                        "section_id": item["section_id"],
                        "chapter_title": section["path"][0] if section["path"] else section["title"],
                        "parser_version": self._effective_parser_version(state),
                    },
                ))
            public_sections = [
                {key: value for key, value in section.items() if key != "blocks" and not key.startswith("_")}
                for section in state["sections"]
            ]
            material.extracted_text = "\n\n".join(item["content"] for item in state["chunks"])
            material.parse_status = "completed"
            material.ingestion_status = "awaiting_confirmation"
            material.parser_version = self._effective_parser_version(state)
            material.content_hash = sha256(state["content"]).hexdigest()
            material.outline_version = max(1, int(material.outline_version or 0) + 1)
            material.outline_json = {"sections": public_sections, "confirmed": False}
            material.quality_json = state["quality"]
            material.parsed_at = datetime.now(UTC)
            material.agent_trace_id = state["trace_id"]
            material.metadata_json = {
                **(material.metadata_json or {}),
                "detail": "解析完成，等待确认目录",
                "agent_trace_id": state["trace_id"],
            }
            self.db.add(material)
            self.db.commit()
            return {"result": {
                "material_id": str(material.id),
                "ingestion_status": material.ingestion_status,
                "outline_version": material.outline_version,
                "section_count": state["quality"]["section_count"],
                "chunk_count": state["quality"]["chunk_count"],
                "quality": state["quality"],
                "warnings": state["warnings"],
            }}

        return self._node(state, "persist", 8, work)

    def _effective_parser_version(self, state: MaterialIngestionState) -> str:
        return f"{self.parser_version}:{state['document'].parser}"[:50]

    def _node(self, state: MaterialIngestionState, name: str, index: int, work):
        started = perf_counter()
        context = state.get("job_context")
        if context is not None:
            context.before_node(name)
        try:
            result = work()
        except Exception as exc:
            self._record(state, name, index, "failed", {"error_code": exc.__class__.__name__}, started)
            if context is not None:
                context.after_node(name=name, label="节点执行失败", progress_percent=max(0, self.node_progress[name][0] - 1), status="failed")
            raise
        metadata = {
            "material_count": 1,
            "candidate_count": len(result.get("chunks", state.get("chunks", []))),
            "section_count": len(result.get("sections", state.get("sections", []))),
        }
        self._record(state, name, index, "completed", metadata, started)
        if context is not None:
            progress, label = self.node_progress[name]
            context.after_node(name=name, label=label, progress_percent=progress, status="completed")
        return result

    def _record(self, state: MaterialIngestionState, name: str, index: int, status: str, metadata: dict[str, Any], started: float) -> None:
        self.trace_recorder.record(
            trace_id=state["trace_id"],
            user_id=state["user_id"],
            course_id=None,
            agent_name=name,
            step_index=index,
            status=status,
            input_summary="处理用户资料的结构与质量。",
            output_summary="节点已完成。" if status == "completed" else "节点失败，已保留安全诊断。",
            duration_ms=max(0, int((perf_counter() - started) * 1000)),
            workflow=self.workflow,
            artifact_type="material",
            artifact_id=str(state["material"].id),
            metadata=metadata,
        )

    def _chunk_section(self, section: dict[str, Any]) -> list[dict[str, Any]]:
        blocks = section.get("blocks") or []
        pieces: list[dict[str, Any]] = []
        buffer: list[str] = []
        start_page: int | None = None
        end_page: int | None = None

        def flush() -> None:
            nonlocal buffer, start_page, end_page
            content = "\n".join(buffer).strip()
            if not content:
                return
            pieces.append({
                "section_id": section["id"],
                "content": content,
                "start_page": start_page,
                "end_page": end_page,
                "chunk_type": "body",
                "content_hash": sha256(re.sub(r"\s+", "", content).encode("utf-8")).hexdigest(),
                "quality": {"character_count": len(content), "within_target": 300 <= len(content) <= 900},
            })
            buffer = []
            start_page = None
            end_page = None

        for block in blocks:
            text = block["text"].strip()
            if not text:
                continue
            sentences = [item.strip() for item in re.split(r"(?<=[。！？；])", text) if item.strip()] or [text]
            for sentence in sentences:
                while len(sentence) > 1200:
                    head, sentence = sentence[:1200], sentence[1200:]
                    if buffer:
                        flush()
                    buffer = [head]
                    start_page = end_page = block.get("page_number")
                    flush()
                prospective = len("\n".join([*buffer, sentence]))
                if buffer and prospective > 900 and len("\n".join(buffer)) >= 300:
                    flush()
                if start_page is None:
                    start_page = block.get("page_number")
                end_page = block.get("page_number") or end_page
                buffer.append(sentence)
                if len("\n".join(buffer)) >= 900:
                    flush()
        flush()
        if len(pieces) >= 2 and len(pieces[-1]["content"]) < 300 and len(pieces[-2]["content"]) + len(pieces[-1]["content"]) <= 1200:
            tail = pieces.pop()
            previous = pieces[-1]
            previous["content"] += "\n" + tail["content"]
            previous["end_page"] = tail["end_page"] or previous["end_page"]
            previous["content_hash"] = sha256(re.sub(r"\s+", "", previous["content"]).encode("utf-8")).hexdigest()
            previous["quality"] = {"character_count": len(previous["content"]), "within_target": 300 <= len(previous["content"]) <= 900}
        return pieces

    @classmethod
    def _heading_level(cls, text: str) -> int | None:
        compact = cls._line(text)
        if not compact or len(compact) > 80:
            return None
        if cls._chapter_number(compact):
            return 1
        match = re.match(r"^[|Il1i!！,，._·•\-—–\s]{0,4}(\d{1,2})\s*\.\s*(\d{1,2})(?:\s*\.\s*(\d{1,2}))?\s+(.+)$", compact)
        if match:
            title = match.group(4).strip()
            noisy = re.search(
                r"(?:所示|参见|见图|见表|小节中|都属于|这种情况|至此|如下所述|试设计|可以看成|指的是)",
                title,
            )
            if 2 <= len(title) <= 48 and not noisy and not re.match(r"^(?:的|所示|中|为|给出|可见|时|后|前)", title):
                return 3 if match.group(3) else 2
        if re.fullmatch(r"(?:目录|参考文献|附录(?:\s*[A-Z一二三四五六七八九十])?)", compact, re.IGNORECASE):
            return 1
        return None

    @classmethod
    def _normalize_heading(cls, text: str) -> str:
        compact = re.sub(r"\s+", " ", text).strip(" |·•")
        match = cls._chapter_match(compact)
        if not match:
            normalized = re.sub(r"^[|Il1i!！,，_·•\-—–\s]{1,4}(?=\d{1,2}\s*\.)", "", compact)
            return cls._repair_heading_ocr(normalized)
        number = cls._canonical_chapter_number(match.group(1))
        remainder = re.sub(r"^[|Il1!！J户b,卢仁＝习二勹\s]+", "", compact[match.end():]).strip(" |·•")
        if re.fullmatch(r"[Il1亡d]+", remainder, re.IGNORECASE) and remainder != "图":
            remainder = ""
        if remainder.endswith("二叉"):
            remainder += "树"
        return cls._repair_heading_ocr(f"第{number}章{f' {remainder}' if remainder else ''}")

    @staticmethod
    def _repair_heading_ocr(value: str) -> str:
        title = value
        for source, target in {
            "时问": "时间",
            "空问": "空间",
            "橾式": "模式",
            "插人": "插入",
            "归井": "归并",
            "定义和特权": "定义和特点",
            "链队�人列": "链队列",
        }.items():
            title = title.replace(source, target)
        title = re.sub(r"\s*([、，,:：])\s*", r"\1", title)
        title = re.sub(r"(?:\s*[.·_-]+|[一—-]{2,})$", "", title).strip()
        return title

    @staticmethod
    def _section_chapter_number(text: str) -> str | None:
        match = re.match(r"^[|Il1i!！,，._·•\-—–\s]{0,4}(\d{1,2})\s*\.", text.strip())
        return str(int(match.group(1))) if match else None

    @classmethod
    def _chapter_match(cls, text: str):
        compact = cls._line(text)
        match = re.match(
            r"^[|Il1!！,，＝=._·•\-—–\s]{0,8}第\s*([一二三四五六七八九十百0-9lIiI]+)\s*[章农幸]",
            compact,
            re.IGNORECASE,
        )
        return match or re.match(
            r"^[|Il1!！,，＝=._·•\-—–\s]{0,8}章\s*([一二三四五六七八九十百0-9lIiI]+)\s*第",
            compact,
            re.IGNORECASE,
        )

    @classmethod
    def _chapter_number(cls, text: str) -> str | None:
        match = cls._chapter_match(text)
        return cls._canonical_chapter_number(match.group(1)) if match else None

    @staticmethod
    def _canonical_chapter_number(value: str) -> str:
        compact = value.strip().lower()
        return "1" if compact in {"l", "i"} else compact

    @classmethod
    def _is_chapter_title_line(cls, text: str) -> bool:
        compact = cls._line(text).strip(" |·•")
        if not compact or len(compact) > 30 or cls._heading_level(compact) is not None:
            return False
        if re.search(r"[。！？；：:，,（）()=<>]", compact):
            return False
        return bool(re.search(r"[一-鿿]", compact))

    @classmethod
    def _repair_missing_chapter_heading(cls, text: str, chapter_number: str) -> str | None:
        if not chapter_number.isdigit():
            return None
        compact = cls._line(text)
        match = re.match(r"^[|Ili!！,，_·•\-—–\s]{0,4}\.\s*(\d{1,2})(?:\s*\.\s*(\d{1,2}))?\s+(.+)$", compact)
        if not match:
            return None
        suffix = f".{match.group(2)}" if match.group(2) else ""
        return f"{chapter_number}.{match.group(1)}{suffix} {match.group(3)}"

    @staticmethod
    def _line(text: str) -> str:
        return re.sub(r"\s+", " ", str(text or "")).strip()

    @staticmethod
    def _is_page_number(text: str) -> bool:
        return bool(re.fullmatch(r"[-—–| ]*[0-9一二三四五六七八九十百]+[-—–| ]*", text))

    @staticmethod
    def _excluded_by_default(title: str) -> bool:
        return any(token in title for token in ("目录", "参考文献", "版权", "出版说明"))

    @staticmethod
    def _similar_heading(left: str, right: str) -> bool:
        a = re.sub(r"\W+", "", left).casefold()
        b = re.sub(r"\W+", "", right).casefold()
        return bool(a and b and (a in b or b in a or len(set(a) & set(b)) / max(len(set(a)), len(set(b))) >= 0.7))

    @staticmethod
    def _rebuild_paths(sections: list[dict[str, Any]]) -> None:
        stack: list[str] = []
        for section in sections:
            level = max(1, min(6, int(section["level"])))
            stack = stack[: level - 1]
            stack.append(section["title"])
            section["path"] = list(stack)

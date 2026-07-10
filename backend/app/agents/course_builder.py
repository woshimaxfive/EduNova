from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from math import ceil
from pathlib import Path
from time import perf_counter
from typing import Any, Callable, TypedDict

from langgraph.graph import END, START, StateGraph

from backend.app.agents.learning_review import contains_sensitive_text, parse_json_object, review_contract, safe_text
from backend.app.api.errors import make_trace_id
from backend.app.models import Course, CourseEnrollment, CourseMaterialLink, KnowledgeChunk, KnowledgePoint, Material, MaterialChunk, User
from backend.app.schemas.courses import CreateCourseFromMaterialsResult


class CourseBuilderState(TypedDict, total=False):
    trace_id: str
    user: User
    user_id: int
    material_ids: list[int]
    requested_title: str
    materials: list[Material]
    source_chunks: list[MaterialChunk]
    source_units: list[dict[str, Any]]
    deterministic_structure: dict[str, Any]
    structure: dict[str, Any]
    generation_mode: str
    review_mode: str
    review_result: dict[str, Any]
    needs_repair: bool
    repair_count: int
    knowledge_points: list[KnowledgePoint]
    knowledge_chunks: list[KnowledgeChunk]
    warnings: list[str]
    result: CreateCourseFromMaterialsResult


class CourseBuilderGraphRunner:
    workflow = "course_builder"

    def __init__(self, service: Any) -> None:
        self.service = service
        self.graph = self._build_graph()

    def generate(self, *, user: User, material_ids: list[int], course_title: str) -> CreateCourseFromMaterialsResult:
        unique_ids = list(dict.fromkeys(material_ids))
        if not unique_ids:
            raise self.service.generation_error("至少选择一份资料。")
        state: CourseBuilderState = {
            "trace_id": make_trace_id(),
            "user": user,
            "user_id": user.id,
            "material_ids": unique_ids,
            "requested_title": course_title.strip(),
            "warnings": [],
            "repair_count": 0,
        }
        return self.graph.invoke(state)["result"]

    def _build_graph(self):
        graph = StateGraph(CourseBuilderState)
        graph.add_node("read_materials", self._read_materials_node)
        graph.add_node("source_outline", self._source_outline_node)
        graph.add_node("structure_course", self._structure_course_node)
        graph.add_node("knowledge_points", self._knowledge_points_node)
        graph.add_node("chunk", self._chunk_node)
        graph.add_node("embed", self._embed_node)
        graph.add_node("review", self._review_node)
        graph.add_node("repair", self._repair_node)
        graph.add_node("persist", self._persist_node)
        graph.add_edge(START, "read_materials")
        graph.add_edge("read_materials", "source_outline")
        graph.add_edge("source_outline", "structure_course")
        graph.add_edge("structure_course", "knowledge_points")
        graph.add_edge("knowledge_points", "chunk")
        graph.add_edge("chunk", "embed")
        graph.add_edge("embed", "review")
        graph.add_conditional_edges("review", lambda state: "repair" if state.get("needs_repair") else "persist", {"repair": "repair", "persist": "persist"})
        graph.add_edge("repair", "persist")
        graph.add_edge("persist", END)
        return graph.compile()

    def _read_materials_node(self, state: CourseBuilderState) -> dict[str, Any]:
        def work():
            materials = self.service._ordered_materials(int(state["user_id"]), list(state["material_ids"]))
            self.service._validate_materials(materials, list(state["material_ids"]))
            list_chunks = getattr(self.service.repository, "list_material_chunks", None)
            chunks = list_chunks(list(state["material_ids"])) if callable(list_chunks) else []
            existing_ids = {chunk.material_id for chunk in chunks}
            generated: list[MaterialChunk] = []
            for material in materials:
                if material.id not in existing_ids:
                    generated.extend(self.service.chunking_service.build_chunks(material))
            if generated:
                add_chunks = getattr(self.service.repository, "add_material_chunks", None)
                if callable(add_chunks):
                    add_chunks(generated)
                    self.service.repository.commit()
                    chunks = list_chunks(list(state["material_ids"])) if callable(list_chunks) else generated
                else:
                    chunks = generated
            if not chunks:
                raise self.service.generation_error("当前资料没有可用于建课的有效内容。")
            return {"materials": materials, "source_chunks": chunks}, f"已读取 {len(materials)} 份资料和 {len(chunks)} 个来源分块。", "completed", {"material_count": len(materials), "candidate_count": len(chunks)}

        return self._run_node(state, "read_materials", 1, "读取当前用户选中的已解析资料", work)

    def _source_outline_node(self, state: CourseBuilderState) -> dict[str, Any]:
        def work():
            materials = {material.id: material for material in state["materials"]}
            chunks = list(state["source_chunks"])
            section_groups: list[list[MaterialChunk]] = []
            current: list[MaterialChunk] = []
            current_group: tuple[int, str] | None = None
            for chunk in chunks:
                group = (chunk.material_id, str(chunk.section_title or ""))
                if current and group != current_group:
                    section_groups.append(current)
                    current = []
                current.append(chunk)
                current_group = group
            if current:
                section_groups.append(current)
            group_bucket_size = max(1, ceil(len(section_groups) / 30))
            grouped = [
                [chunk for section in section_groups[index:index + group_bucket_size] for chunk in section]
                for index in range(0, len(section_groups), group_bucket_size)
            ]
            units: list[dict[str, Any]] = []
            for index, group_chunks in enumerate(grouped[:30], start=1):
                first = group_chunks[0]
                material = materials[first.material_id]
                section_titles = list(dict.fromkeys(safe_text(chunk.section_title, limit=100) for chunk in group_chunks if safe_text(chunk.section_title, limit=100)))
                title = section_titles[0] if len(section_titles) == 1 else (
                    f"{section_titles[0]}等 {len(section_titles)} 节" if section_titles else f"{Path(material.filename).stem} 第 {index} 部分"
                )
                units.append(
                    {
                        "key": f"source-{index}",
                        "title": title,
                        "material_id": first.material_id,
                        "source_filename": material.filename,
                        "chapter": safe_text((first.metadata_json or {}).get("chapter_title"), limit=100) or material.filename,
                        "chunk_indexes": [chunk.chunk_index for chunk in group_chunks],
                        "excerpt": safe_text(" ".join(chunk.content for chunk in group_chunks), limit=500),
                    }
                )
            return {"source_units": units}, f"已形成 {len(units)} 个可审计来源单元。", "completed", {"candidate_count": len(units)}

        return self._run_node(state, "source_outline", 2, "把资料分块整理成安全来源提纲", work)

    def _structure_course_node(self, state: CourseBuilderState) -> dict[str, Any]:
        def work():
            deterministic = self._deterministic_structure(state)
            enhanced = self._model_structure(state, deterministic, repair=False)
            structure = enhanced or deterministic
            mode = "model_enhanced" if enhanced else "deterministic_source"
            return {"deterministic_structure": deterministic, "structure": structure, "generation_mode": mode}, (
                "模型已在真实来源范围内完成教学结构重组。" if enhanced else "模型不可用或结构无效，保留确定性课程结构。"
            ), "completed" if enhanced else "warning", {"model_used": bool(enhanced), "generation_mode": mode}

        return self._run_node(state, "structure_course", 3, "生成课程目标、章节和知识点结构", work)

    def _knowledge_points_node(self, state: CourseBuilderState) -> dict[str, Any]:
        def work():
            points: list[KnowledgePoint] = []
            for index, spec in enumerate(state["structure"].get("knowledge_points", [])):
                point = KnowledgePoint(
                    course_id=0,
                    title=safe_text(spec.get("title"), limit=255),
                    summary=safe_text(spec.get("summary"), limit=1000),
                    chapter=safe_text(spec.get("chapter"), limit=255) or None,
                    order_index=index,
                    difficulty=str(spec.get("difficulty") or "medium"),
                    prerequisites_json=list(spec.get("prerequisite_keys") or []),
                )
                setattr(point, "builder_key", str(spec.get("key") or f"kp-{index + 1}"))
                points.append(point)
            return {"knowledge_points": points}, f"已生成 {len(points)} 个知识点实体。", "completed", {"candidate_count": len(points)}

        return self._run_node(state, "knowledge_points", 4, "把审核前课程结构转换为知识点实体", work)

    def _chunk_node(self, state: CourseBuilderState) -> dict[str, Any]:
        def work():
            chunk_by_ref = {(chunk.material_id, chunk.chunk_index): chunk for chunk in state["source_chunks"]}
            chunks: list[KnowledgeChunk] = []
            for point_index, spec in enumerate(state["structure"].get("knowledge_points", [])):
                for source_key in spec.get("source_keys", []):
                    unit = next((item for item in state["source_units"] if item["key"] == source_key), None)
                    if unit is None:
                        continue
                    for chunk_index in unit["chunk_indexes"]:
                        source = chunk_by_ref.get((unit["material_id"], chunk_index))
                        if source is None:
                            continue
                        chunks.append(
                            KnowledgeChunk(
                                course_id=0,
                                material_id=None,  # type: ignore[arg-type]
                                knowledge_point_id=None,
                                content=source.content,
                                page_number=source.page_number,
                                section_title=source.section_title or spec.get("title"),
                                embedding=None,
                                metadata_json={
                                    "source_material_id": source.material_id,
                                    "source_chunk_index": source.chunk_index,
                                    "source_filename": unit["source_filename"],
                                    "knowledge_point_order": point_index,
                                    "knowledge_point_key": spec.get("key"),
                                },
                            )
                        )
            return {"knowledge_chunks": chunks}, f"已为知识点绑定 {len(chunks)} 个真实来源分块。", "completed", {"candidate_count": len(chunks)}

        return self._run_node(state, "chunk", 5, "建立课程分块与知识点来源映射", work)

    def _embed_node(self, state: CourseBuilderState) -> dict[str, Any]:
        def work():
            chunks = list(state.get("knowledge_chunks", []))
            warning = None
            if self.service.embedding_service is not None and chunks:
                try:
                    self.service._best_effort_embed_chunks(state["user"], chunks)
                except Exception:
                    warning = "外部 embedding 不可用，课程将使用关键词检索。"
            warnings = [*state.get("warnings", [])]
            if warning:
                warnings.append(warning)
            embedded_count = sum(1 for chunk in chunks if chunk.embedding is not None)
            return {"knowledge_chunks": chunks, "warnings": warnings}, (
                f"已生成 {embedded_count} 个真实向量。" if embedded_count else (warning or "当前未配置外部 embedding，保留关键词检索。")
            ), "completed" if embedded_count else "warning", {"embedding_status": "external" if embedded_count else "local_fallback", "candidate_count": embedded_count}

        return self._run_node(state, "embed", 6, "为课程分块生成外部语义向量", work)

    def _review_node(self, state: CourseBuilderState) -> dict[str, Any]:
        def work():
            risks = self._structure_risks(state["structure"], state["source_units"])
            model_review = None
            if state.get("generation_mode") == "model_enhanced" and self.service.model_service is not None:
                try:
                    raw = self.service.model_service.chat_completion(
                        state["user"],
                        [
                            {"role": "system", "content": "你是 CourseBuilderGraph ReviewAgent。只输出 JSON，不得添加来源。"},
                            {
                                "role": "user",
                                "content": (
                                    f"审核知识点数={len(state['structure'].get('knowledge_points', []))}，"
                                    f"来源数={len(state['source_units'])}。"
                                    "返回 {\"review_status\":\"passed|revise\",\"confidence\":0.0,"
                                    "\"risk_flags\":[],\"safety_summary\":\"\"}。"
                                ),
                            },
                        ],
                    )
                    model_review = review_contract(parse_json_object(raw), default_summary="课程结构、来源和安全审核完成。")
                except Exception:
                    model_review = None
            if model_review and model_review["review_status"] == "revise":
                risks.extend(str(item) for item in model_review["risk_flags"])
            risks = list(dict.fromkeys(risks))
            if risks:
                review = {"review_status": "revise", "confidence": model_review["confidence"] if model_review else 0.42, "risk_flags": risks, "safety_summary": model_review["safety_summary"] if model_review else "课程结构需要修订。"}
                return {"review_result": review, "review_mode": "model_and_rules" if model_review else "rules_only", "needs_repair": True}, review["safety_summary"], "warning", review
            review = model_review or {"review_status": "warning", "confidence": 0.66, "risk_flags": [], "safety_summary": "模型审核不可用，已完成来源覆盖、先修图和隐私规则审核。"}
            return {"review_result": review, "review_mode": "model_and_rules" if model_review else "rules_only", "needs_repair": False}, review["safety_summary"], "completed" if model_review else "warning", review

        return self._run_node(state, "review", 7, "审核来源覆盖、先修关系和安全边界", work)

    def _repair_node(self, state: CourseBuilderState) -> dict[str, Any]:
        def work():
            repaired = self._model_structure(state, state["structure"], repair=True)
            if repaired is None or self._structure_risks(repaired, state["source_units"]):
                repaired = state["deterministic_structure"]
                mode = "deterministic_source"
            else:
                mode = "model_enhanced"
            points, chunks = self._entities_from_structure(repaired, state)
            if self.service.embedding_service is not None and chunks:
                self.service._best_effort_embed_chunks(state["user"], chunks)
            review = {"review_status": "passed", "confidence": 0.72 if mode == "model_enhanced" else 0.66, "risk_flags": [], "safety_summary": "已完成一次修订并通过确定性来源与先修图校验。"}
            return {"structure": repaired, "knowledge_points": points, "knowledge_chunks": chunks, "generation_mode": mode, "review_result": review, "repair_count": 1}, review["safety_summary"], "completed", {**review, "repair_count": 1}

        return self._run_node(state, "repair", 8, "按审核结果修订一次课程结构", work)

    def _persist_node(self, state: CourseBuilderState) -> dict[str, Any]:
        started = perf_counter()
        materials = state["materials"]
        structure = dict(state["structure"])
        title = str(state.get("requested_title") or structure.get("title") or Path(materials[0].filename).stem).strip()[:255]
        course = Course(
            owner_id=int(state["user_id"]),
            title=title,
            description=safe_text(structure.get("description"), limit=1000) or f"由 {len(materials)} 份资料生成",
            subject=safe_text(structure.get("subject"), limit=120) or "自动生成课程",
            source_type="uploaded",
            visibility="private",
            status="ready",
            agent_trace_id=state["trace_id"],
            structure_json={},
        )
        enrollment = CourseEnrollment(user_id=int(state["user_id"]), course_id=0, role="learner", progress_percent=Decimal("0"))
        course_materials = [self.service._build_course_material(state["user"], material) for material in materials]
        for material in course_materials:
            material.agent_trace_id = state["trace_id"]
        links = [CourseMaterialLink(course_id=0, material_id=material.id, added_by_user_id=int(state["user_id"]), usage_type="course_source") for material in materials]
        try:
            created = self.service.repository.add_course_graph(course, enrollment, course_materials, links, state["knowledge_points"], state["knowledge_chunks"])
            key_to_id = {str(getattr(point, "builder_key", f"kp-{index + 1}")): str(point.id) for index, point in enumerate(state["knowledge_points"])}
            chapters: dict[str, list[str]] = defaultdict(list)
            for point in state["knowledge_points"]:
                chapters[str(point.chapter or "课程内容")].append(str(point.id))
            used_sources = {key for point in structure.get("knowledge_points", []) for key in point.get("source_keys", [])}
            course.structure_json = {
                "schema_version": 2,
                "learning_objectives": list(structure.get("learning_objectives", []))[:12],
                "chapters": [{"title": chapter, "knowledge_point_ids": ids} for chapter, ids in chapters.items()],
                "supplemental_refs": [
                    {"source_key": unit["key"], "title": unit["title"], "material_id": str(unit["material_id"])}
                    for unit in state["source_units"]
                    if unit["key"] not in used_sources
                ],
                "generation_mode": state.get("generation_mode", "deterministic_source"),
                "review_mode": state.get("review_mode", "rules_only"),
                "review_result": state.get("review_result", {}),
                "source_coverage": {"source_unit_count": len(state["source_units"]), "mapped_source_count": len(used_sources)},
                "knowledge_key_map": key_to_id,
                "warnings": list(state.get("warnings", [])),
            }
            self.service.repository.commit()
            self.service.repository.refresh(created)
        except Exception as exc:
            self.service.repository.rollback()
            self._record(state, "persist", 9, "failed", "事务性持久化课程结构", "课程持久化失败，未保留半成品课程。", {"error_code": exc.__class__.__name__}, started)
            raise
        result = CreateCourseFromMaterialsResult(
            course=self.service._build_summary(created, len(course_materials), len(state["knowledge_points"]), len(state["knowledge_chunks"])),
            knowledge_points=[self.service._build_knowledge_point(point) for point in state["knowledge_points"]],
        )
        self._record(state, "persist", 9, "completed", "事务性持久化课程结构", "课程、知识点、来源分块和先修关系已持久化。", {"artifact_id": str(created.id), "candidate_count": len(state["knowledge_points"])}, started)
        return {"result": result}

    def _deterministic_structure(self, state: CourseBuilderState) -> dict[str, Any]:
        points: list[dict[str, Any]] = []
        for index, unit in enumerate(state["source_units"], start=1):
            key = f"kp-{index}"
            points.append(
                {
                    "key": key,
                    "title": unit["title"],
                    "chapter": unit.get("chapter") or unit["source_filename"],
                    "summary": unit["excerpt"],
                    "difficulty": "easy" if index == 1 else "medium" if index < len(state["source_units"]) else "hard",
                    "prerequisite_keys": [f"kp-{index - 1}"] if index > 1 else [],
                    "source_keys": [unit["key"]],
                }
            )
        return {
            "title": state.get("requested_title") or Path(state["materials"][0].filename).stem,
            "subject": "自动生成课程",
            "description": f"由 {len(state['materials'])} 份资料生成的结构化课程",
            "learning_objectives": [f"理解并应用 {point['title']}" for point in points[:8]],
            "knowledge_points": points,
        }

    def _model_structure(self, state: CourseBuilderState, fallback: dict[str, Any], *, repair: bool) -> dict[str, Any] | None:
        if self.service.model_service is None:
            return None
        source_lines = [f"{unit['key']} | {unit['title']} | {unit['excerpt'][:260]}" for unit in state["source_units"]]
        try:
            raw = self.service.model_service.chat_completion(
                state["user"],
                [
                    {
                        "role": "system",
                        "content": (
                            "你是 CourseBuilderGraph 的课程结构 Agent。只输出 JSON。"
                            "可以合并、拆分和重排来源，但 source_keys 只能使用提供的 key，先修关系必须无环。"
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            ("根据审核风险修订一次。\n" if repair else "生成适合学生学习的课程结构。\n")
                            + "来源单元：\n"
                            + "\n".join(source_lines)
                            + "\n返回 title、subject、description、learning_objectives、knowledge_points；"
                            + "每个知识点包含 key、title、chapter、summary、difficulty、prerequisite_keys、source_keys。"
                        ),
                    },
                ],
            )
        except Exception:
            return None
        return self._sanitize_structure(parse_json_object(raw), state["source_units"], fallback)

    def _sanitize_structure(self, value: Any, source_units: list[dict[str, Any]], fallback: dict[str, Any]) -> dict[str, Any] | None:
        if not isinstance(value, dict) or not isinstance(value.get("knowledge_points"), list):
            return None
        valid_sources = {unit["key"] for unit in source_units}
        points: list[dict[str, Any]] = []
        keys: set[str] = set()
        for index, raw in enumerate(value["knowledge_points"][:30], start=1):
            if not isinstance(raw, dict):
                continue
            key = safe_text(raw.get("key"), limit=40) or f"kp-{index}"
            if key in keys:
                key = f"kp-{index}"
            title = safe_text(raw.get("title"), limit=120)
            source_keys = [str(item) for item in raw.get("source_keys", []) if str(item) in valid_sources]
            if not title or not source_keys:
                continue
            difficulty = str(raw.get("difficulty") or "medium")
            points.append({
                "key": key,
                "title": title,
                "chapter": safe_text(raw.get("chapter"), limit=120) or "课程内容",
                "summary": safe_text(raw.get("summary"), limit=800),
                "difficulty": difficulty if difficulty in {"easy", "medium", "hard"} else "medium",
                "prerequisite_keys": [safe_text(item, limit=40) for item in raw.get("prerequisite_keys", []) if safe_text(item, limit=40)],
                "source_keys": list(dict.fromkeys(source_keys)),
            })
            keys.add(key)
        if not points:
            return None
        return {
            "title": safe_text(value.get("title"), limit=255) or fallback["title"],
            "subject": safe_text(value.get("subject"), limit=120) or fallback["subject"],
            "description": safe_text(value.get("description"), limit=1000) or fallback["description"],
            "learning_objectives": [safe_text(item, limit=200) for item in value.get("learning_objectives", []) if safe_text(item, limit=200)][:12],
            "knowledge_points": points,
        }

    def _structure_risks(self, structure: dict[str, Any], source_units: list[dict[str, Any]]) -> list[str]:
        points = structure.get("knowledge_points") if isinstance(structure, dict) else None
        if not isinstance(points, list) or not points or len(points) > 30:
            return ["invalid_point_count"]
        valid_sources = {unit["key"] for unit in source_units}
        keys = {str(point.get("key")) for point in points if isinstance(point, dict)}
        titles: set[str] = set()
        graph: dict[str, list[str]] = {}
        risks: list[str] = []
        for point in points:
            title = self._normalized(point.get("title"))
            if not title or title in titles:
                risks.append("duplicate_or_empty_title")
            titles.add(title)
            if contains_sensitive_text(point):
                risks.append("sensitive_output")
            source_keys = set(point.get("source_keys") or [])
            if not source_keys or not source_keys.issubset(valid_sources):
                risks.append("invalid_source_ref")
            prerequisites = [str(item) for item in point.get("prerequisite_keys") or []]
            if any(item not in keys for item in prerequisites):
                risks.append("invalid_prerequisite_ref")
            graph[str(point.get("key"))] = prerequisites
        if self._has_cycle(graph):
            risks.append("prerequisite_cycle")
        return list(dict.fromkeys(risks))

    @staticmethod
    def _has_cycle(graph: dict[str, list[str]]) -> bool:
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node: str) -> bool:
            if node in visiting:
                return True
            if node in visited:
                return False
            visiting.add(node)
            if any(visit(parent) for parent in graph.get(node, [])):
                return True
            visiting.remove(node)
            visited.add(node)
            return False

        return any(visit(node) for node in graph)

    def _entities_from_structure(self, structure: dict[str, Any], state: CourseBuilderState) -> tuple[list[KnowledgePoint], list[KnowledgeChunk]]:
        points: list[KnowledgePoint] = []
        for index, spec in enumerate(structure.get("knowledge_points", [])):
            point = KnowledgePoint(course_id=0, title=spec["title"], summary=spec.get("summary"), chapter=spec.get("chapter"), order_index=index, difficulty=spec.get("difficulty"), prerequisites_json=list(spec.get("prerequisite_keys") or []))
            setattr(point, "builder_key", spec["key"])
            points.append(point)
        chunk_by_ref = {(chunk.material_id, chunk.chunk_index): chunk for chunk in state["source_chunks"]}
        chunks: list[KnowledgeChunk] = []
        for point_index, spec in enumerate(structure.get("knowledge_points", [])):
            for source_key in spec.get("source_keys", []):
                unit = next((item for item in state["source_units"] if item["key"] == source_key), None)
                if unit is None:
                    continue
                for chunk_index in unit["chunk_indexes"]:
                    source = chunk_by_ref.get((unit["material_id"], chunk_index))
                    if source is not None:
                        chunks.append(KnowledgeChunk(course_id=0, material_id=None, knowledge_point_id=None, content=source.content, page_number=source.page_number, section_title=source.section_title or spec["title"], embedding=None, metadata_json={"source_material_id": source.material_id, "source_chunk_index": source.chunk_index, "source_filename": unit["source_filename"], "knowledge_point_order": point_index, "knowledge_point_key": spec["key"]}))  # type: ignore[arg-type]
        return points, chunks

    @staticmethod
    def _normalized(value: Any) -> str:
        return " ".join(str(value or "").split()).lower()

    def _run_node(self, state: CourseBuilderState, name: str, index: int, input_summary: str, work: Callable):
        started = perf_counter()
        try:
            result, output_summary, status, metadata = work()
        except Exception as exc:
            self._record(state, name, index, "failed", input_summary, "节点执行失败，已记录安全错误摘要。", {"error_code": exc.__class__.__name__}, started)
            raise
        self._record(state, name, index, status, input_summary, output_summary, metadata, started)
        return result

    def _record(self, state: CourseBuilderState, name: str, index: int, status: str, input_summary: str, output_summary: str, metadata: dict[str, Any], started: float) -> None:
        recorder = self.service.trace_recorder
        if recorder is None:
            return
        recorder.record(
            trace_id=state["trace_id"],
            user_id=int(state["user_id"]),
            course_id=None,
            agent_name=name,
            step_index=index,
            status=status,
            input_summary=input_summary,
            output_summary=output_summary,
            duration_ms=max(0, int((perf_counter() - started) * 1000)),
            workflow=self.workflow,
            artifact_type="course",
            artifact_id=metadata.get("artifact_id"),
            metadata=metadata,
        )

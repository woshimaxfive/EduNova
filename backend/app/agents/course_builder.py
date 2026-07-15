from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from math import ceil
import operator
from pathlib import Path
import re
from time import perf_counter
from typing import Annotated, Any, Callable, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from backend.app.agents.learning_review import contains_sensitive_text, parse_json_object, review_contract, safe_text
from backend.app.api.errors import make_trace_id
from backend.app.core.config import get_settings
from backend.app.models import Course, CourseEnrollment, CourseMaterialLink, KnowledgeChunk, KnowledgePoint, Material, MaterialChunk, User
from backend.app.schemas.courses import CreateCourseFromMaterialsResult
from backend.app.services.learner_context import context_service_from_repository
from backend.app.services.model_execution import execution_context_for_state, model_execution_scope
from backend.app.services.content_locale import china_first_content_policy


class CourseBuilderState(TypedDict, total=False):
    trace_id: str
    user: User
    user_id: int
    material_ids: list[int]
    requested_title: str
    materials: list[Material]
    source_chunks: list[MaterialChunk]
    learner_context: Any
    chapters: list[dict[str, Any]]
    worker_chapter: dict[str, Any]
    worker_results: Annotated[list[dict[str, Any]], operator.add]
    structure: dict[str, Any]
    review_mode: str
    review_result: dict[str, Any]
    needs_repair: bool
    repair_count: int
    knowledge_points: list[KnowledgePoint]
    knowledge_chunks: list[KnowledgeChunk]
    quality: dict[str, Any]
    warnings: list[str]
    result: CreateCourseFromMaterialsResult
    job_context: Any


class CourseBuilderGraphRunner:
    workflow = "course_builder"
    prompt_version = "course-builder-v3"
    job_progress = {
        "validate_confirmed_materials": (7, "已校验确认资料"),
        "coherence_gate": (14, "已检查资料主题一致性"),
        "load_outlines": (24, "已读取确认目录"),
        "chapter_plan": (34, "已规划章节分析"),
        "concept_workers": (54, "已分析章节知识点"),
        "aggregate": (62, "已聚合课程结构"),
        "prerequisite_graph": (70, "已建立先修关系"),
        "evidence_bind": (78, "已绑定真实证据"),
        "review": (88, "已审核课程质量"),
        "repair": (94, "已修订课程结构"),
        "persist": (100, "课程已创建"),
    }

    def __init__(self, service: Any) -> None:
        self.service = service
        self.graph = self._build_graph()

    def generate(
        self,
        *,
        user: User,
        material_ids: list[int],
        course_title: str,
        trace_id: str | None = None,
        job_context: Any | None = None,
    ) -> CreateCourseFromMaterialsResult:
        unique_ids = list(dict.fromkeys(material_ids))
        if not unique_ids:
            raise self.service.generation_error("至少选择一份资料。")
        state: CourseBuilderState = {
            "trace_id": trace_id or make_trace_id(),
            "user": user,
            "user_id": user.id,
            "material_ids": unique_ids,
            "requested_title": course_title.strip(),
            "warnings": [],
            "worker_results": [],
            "repair_count": 0,
            "job_context": job_context,
        }
        with model_execution_scope(execution_context_for_state(state, workflow=self.workflow)):
            max_concurrency = max(1, min(2, get_settings().model_max_concurrent_per_user))
            return self.graph.invoke(state, config={"max_concurrency": max_concurrency})["result"]

    def _build_graph(self):
        graph = StateGraph(CourseBuilderState)
        graph.add_node("validate_confirmed_materials", self._validate_confirmed_materials)
        graph.add_node("coherence_gate", self._coherence_gate)
        graph.add_node("load_outlines", self._load_outlines)
        graph.add_node("chapter_plan", self._chapter_plan)
        graph.add_node("concept_workers", self._concept_worker)
        graph.add_node("aggregate", self._aggregate)
        graph.add_node("prerequisite_graph", self._prerequisite_graph)
        graph.add_node("evidence_bind", self._evidence_bind)
        graph.add_node("review", self._review)
        graph.add_node("repair", self._repair)
        graph.add_node("persist", self._persist)
        graph.add_edge(START, "validate_confirmed_materials")
        graph.add_edge("validate_confirmed_materials", "coherence_gate")
        graph.add_edge("coherence_gate", "load_outlines")
        graph.add_edge("load_outlines", "chapter_plan")
        graph.add_conditional_edges("chapter_plan", self._dispatch_chapters, ["concept_workers"])
        graph.add_edge("concept_workers", "aggregate")
        graph.add_edge("aggregate", "prerequisite_graph")
        graph.add_edge("prerequisite_graph", "evidence_bind")
        graph.add_edge("evidence_bind", "review")
        graph.add_conditional_edges("review", lambda state: "repair" if state.get("needs_repair") else "persist", {"repair": "repair", "persist": "persist"})
        graph.add_edge("repair", "persist")
        graph.add_edge("persist", END)
        return graph.compile()

    def _validate_confirmed_materials(self, state: CourseBuilderState) -> dict[str, Any]:
        def work():
            materials = self.service._ordered_materials(state["user_id"], state["material_ids"])
            self.service._validate_materials(materials, state["material_ids"])
            invalid = [material.filename for material in materials if material.ingestion_status != "confirmed" or not (material.quality_json or {}).get("passed")]
            if invalid:
                raise self.service.generation_error("以下资料尚未确认目录或解析质量未通过：" + "、".join(invalid[:5]))
            chunks = list(self.service.repository.list_material_chunks(state["material_ids"]))
            included = [chunk for chunk in chunks if (chunk.quality_json or {}).get("included", True)]
            if not included:
                raise self.service.generation_error("确认目录中没有可用于建课的正文切片。")
            context_service = context_service_from_repository(self.service.repository)
            learner_context = context_service.global_context(state["user_id"]) if context_service is not None else None
            return {"materials": materials, "source_chunks": included, "learner_context": learner_context}, {
                "material_count": len(materials), "candidate_count": len(included)
            }
        return self._run_node(state, "validate_confirmed_materials", 1, work)

    def _coherence_gate(self, state: CourseBuilderState) -> dict[str, Any]:
        def work():
            materials = state["materials"]
            if len(materials) <= 1:
                return {}, {"material_count": len(materials), "coherence_status": "single_material"}
            token_sets: list[set[str]] = []
            chunks_by_material: dict[int, list[MaterialChunk]] = defaultdict(list)
            for chunk in state["source_chunks"]:
                chunks_by_material[chunk.material_id].append(chunk)
            for material in materials:
                sample = material.filename + " " + " ".join(chunk.section_title or "" for chunk in chunks_by_material[material.id][:80])
                token_sets.append(self._terms(sample))
            similarities = []
            for left in range(len(token_sets)):
                for right in range(left + 1, len(token_sets)):
                    union = token_sets[left] | token_sets[right]
                    similarities.append(len(token_sets[left] & token_sets[right]) / max(1, len(union)))
            minimum = min(similarities, default=1.0)
            if minimum < 0.025:
                raise self.service.generation_error("所选资料主题差异较大，建议拆成不同课程后分别生成。")
            return {}, {"material_count": len(materials), "coherence_score": round(minimum, 4)}
        return self._run_node(state, "coherence_gate", 2, work)

    def _load_outlines(self, state: CourseBuilderState) -> dict[str, Any]:
        def work():
            material_by_id = {material.id: material for material in state["materials"]}
            groups: dict[tuple[int, str], list[MaterialChunk]] = defaultdict(list)
            for chunk in state["source_chunks"]:
                path = list(chunk.section_path_json or [])
                chapter = path[0] if path else (chunk.section_title or Path(material_by_id[chunk.material_id].filename).stem)
                groups[(chunk.material_id, chapter)].append(chunk)
            chapters = []
            for index, ((material_id, title), chunks) in enumerate(groups.items(), start=1):
                chapters.append({
                    "key": f"chapter-{index}",
                    "title": title[:255],
                    "material_id": material_id,
                    "source_filename": material_by_id[material_id].filename,
                    "chunk_indexes": [chunk.chunk_index for chunk in chunks],
                    "character_count": sum(len(chunk.content) for chunk in chunks),
                })
            if not chapters:
                raise self.service.generation_error("确认目录中没有有效章节。")
            return {"chapters": chapters}, {"chapter_count": len(chapters), "candidate_count": len(state["source_chunks"])}
        return self._run_node(state, "load_outlines", 3, work)

    def _chapter_plan(self, state: CourseBuilderState) -> dict[str, Any]:
        def work():
            chapters = list(state["chapters"])
            total_chars = sum(item["character_count"] for item in chapters)
            for chapter in chapters:
                proportional = round(56 * chapter["character_count"] / max(1, total_chars))
                chapter["target_count"] = max(2, min(18, proportional))
            target_total = min(120, max(len(chapters) * 2, sum(item["target_count"] for item in chapters)))
            return {"chapters": chapters}, {"chapter_count": len(chapters), "target_knowledge_point_count": target_total}
        return self._run_node(state, "chapter_plan", 4, work)

    @staticmethod
    def _dispatch_chapters(state: CourseBuilderState):
        return [
            Send("concept_workers", {
                "trace_id": state["trace_id"],
                "user": state["user"],
                "user_id": state["user_id"],
                "worker_chapter": chapter,
                "source_chunks": state["source_chunks"],
                "learner_context": state.get("learner_context"),
                "job_context": state.get("job_context"),
                "worker_results": [],
            })
            for chapter in state["chapters"]
        ]

    def _concept_worker(self, state: CourseBuilderState) -> dict[str, Any]:
        started = perf_counter()
        chapter = state["worker_chapter"]
        chunks = [chunk for chunk in state["source_chunks"] if chunk.material_id == chapter["material_id"] and chunk.chunk_index in chapter["chunk_indexes"]]
        deterministic = self._deterministic_chapter_points(chapter, chunks)
        enhanced = self._model_chapter_points(state, chapter, chunks, deterministic)
        points = enhanced or deterministic
        self._record(state, "concept_workers", 5, "completed", {
            "chapter_title": chapter["title"], "candidate_count": len(points), "model_used": bool(enhanced)
        }, started)
        return {"worker_results": [{"chapter": chapter, "points": points, "generation_mode": "model_enhanced" if enhanced else "deterministic_source"}]}

    def _aggregate(self, state: CourseBuilderState) -> dict[str, Any]:
        def work():
            points: list[dict[str, Any]] = []
            modes: list[str] = []
            for result in state.get("worker_results", []):
                modes.append(result["generation_mode"])
                for point in result["points"]:
                    point = dict(point)
                    point["key"] = f"kp-{len(points) + 1}"
                    points.append(point)
            self._ensure_unique_point_titles(points)
            if not points or len(points) > 120:
                raise self.service.generation_error("课程知识点数量不合理，未创建课程。")
            structure = {
                "title": state.get("requested_title") or Path(state["materials"][0].filename).stem,
                "subject": "智能资料课程",
                "description": f"基于 {len(state['materials'])} 份已确认资料生成的结构化课程",
                "learning_objectives": [f"理解并应用 {point['title']}" for point in points[:12]],
                "knowledge_points": points,
                "generation_mode": "model_enhanced" if "model_enhanced" in modes else "deterministic_source",
            }
            return {"structure": structure}, {"candidate_count": len(points), "generation_mode": structure["generation_mode"]}
        return self._run_node(state, "aggregate", 6, work)

    def _prerequisite_graph(self, state: CourseBuilderState) -> dict[str, Any]:
        def work():
            points = state["structure"]["knowledge_points"]
            previous_by_chapter: dict[str, str] = {}
            previous_chapter_tail: str | None = None
            current_chapter = None
            for point in points:
                chapter = point["chapter"]
                prerequisites: list[str] = []
                if chapter in previous_by_chapter:
                    prerequisites.append(previous_by_chapter[chapter])
                elif previous_chapter_tail and chapter != current_chapter:
                    prerequisites.append(previous_chapter_tail)
                point["prerequisite_keys"] = prerequisites
                previous_by_chapter[chapter] = point["key"]
                if current_chapter != chapter:
                    current_chapter = chapter
                previous_chapter_tail = point["key"]
            return {"structure": state["structure"]}, {"candidate_count": len(points), "prerequisite_edge_count": sum(len(p["prerequisite_keys"]) for p in points)}
        return self._run_node(state, "prerequisite_graph", 7, work)

    def _evidence_bind(self, state: CourseBuilderState) -> dict[str, Any]:
        def work():
            points, knowledge_chunks = self._build_bound_entities(state)
            return {"knowledge_points": points, "knowledge_chunks": knowledge_chunks}, {"candidate_count": len(points), "evidence_count": len(knowledge_chunks)}
        return self._run_node(state, "evidence_bind", 8, work)

    def _review(self, state: CourseBuilderState) -> dict[str, Any]:
        def work():
            quality, risks = self._quality(state)
            model_review = self._model_review(state, quality)
            if model_review and model_review["review_status"] == "revise":
                risks.extend(str(item) for item in model_review["risk_flags"])
            risks = list(dict.fromkeys(risks))
            review = model_review or {
                "review_status": "passed" if not risks else "revise",
                "confidence": 0.78 if not risks else 0.35,
                "risk_flags": risks,
                "safety_summary": "已完成来源覆盖、重复率、先修图和内容安全审核。",
            }
            if risks:
                review = {**review, "review_status": "revise", "risk_flags": risks}
            return {"quality": quality, "review_result": review, "review_mode": "model_and_rules" if model_review else "rules_only", "needs_repair": bool(risks)}, {**quality, **review}
        return self._run_node(state, "review", 9, work)

    def _repair(self, state: CourseBuilderState) -> dict[str, Any]:
        def work():
            structure = self._deterministic_structure(state)
            state["structure"] = structure
            quality, risks = self._quality(state)
            if risks:
                raise self.service.generation_error("课程质量审核未通过，未保存低质量课程：" + "、".join(risks))
            points, knowledge_chunks = self._build_bound_entities(state)
            review = {"review_status": "passed", "confidence": 0.76, "risk_flags": [], "safety_summary": "已完成一次结构修订并通过全部确定性质量门。"}
            return {
                "structure": structure,
                "knowledge_points": points,
                "knowledge_chunks": knowledge_chunks,
                "quality": quality,
                "review_result": review,
                "repair_count": 1,
                "needs_repair": False,
            }, {**quality, **review, "repair_count": 1}
        return self._run_node(state, "repair", 10, work)

    def _deterministic_structure(self, state: CourseBuilderState) -> dict[str, Any]:
        points: list[dict[str, Any]] = []
        previous_by_chapter: dict[str, str] = {}
        previous_chapter_tail: str | None = None
        current_chapter: str | None = None
        for chapter in state["chapters"]:
            chunks = [
                chunk
                for chunk in state["source_chunks"]
                if chunk.material_id == chapter["material_id"] and chunk.chunk_index in chapter["chunk_indexes"]
            ]
            for point in self._deterministic_chapter_points(chapter, chunks):
                point = dict(point)
                point["key"] = f"kp-{len(points) + 1}"
                prerequisites: list[str] = []
                if point["chapter"] in previous_by_chapter:
                    prerequisites.append(previous_by_chapter[point["chapter"]])
                elif previous_chapter_tail and point["chapter"] != current_chapter:
                    prerequisites.append(previous_chapter_tail)
                point["prerequisite_keys"] = prerequisites
                previous_by_chapter[point["chapter"]] = point["key"]
                current_chapter = point["chapter"]
                previous_chapter_tail = point["key"]
                points.append(point)
        self._ensure_unique_point_titles(points)
        return {
            "title": state.get("requested_title") or Path(state["materials"][0].filename).stem,
            "subject": "智能资料课程",
            "description": f"基于 {len(state['materials'])} 份已确认资料生成的结构化课程",
            "learning_objectives": [f"理解并应用 {point['title']}" for point in points[:12]],
            "knowledge_points": points[:120],
            "generation_mode": "deterministic_source",
        }

    @classmethod
    def _ensure_unique_point_titles(cls, points: list[dict[str, Any]]) -> None:
        """Disambiguate valid chapter-local titles without another model call."""
        used: set[str] = set()
        for point in points:
            title = cls._clean_title(point.get("title"))
            normalized = cls._normalize(title)
            if normalized not in used:
                point["title"] = title
                used.add(normalized)
                continue

            chapter = cls._clean_title(point.get("chapter"))[:16]
            prefix = f"{chapter}：" if chapter else ""
            base = title[: max(2, 40 - len(prefix))]
            candidate = f"{prefix}{base}"
            sequence = 2
            while cls._normalize(candidate) in used:
                suffix = f"（{sequence}）"
                candidate = f"{prefix}{base[: max(2, 42 - len(prefix) - len(suffix))]}{suffix}"
                sequence += 1
            point["title"] = candidate
            used.add(cls._normalize(candidate))

    def _build_bound_entities(self, state: CourseBuilderState) -> tuple[list[KnowledgePoint], list[KnowledgeChunk]]:
        points: list[KnowledgePoint] = []
        knowledge_chunks: list[KnowledgeChunk] = []
        chunk_by_ref = {(chunk.material_id, chunk.chunk_index): chunk for chunk in state["source_chunks"]}
        filename_by_material = {material.id: material.filename for material in state["materials"]}
        for index, spec in enumerate(state["structure"]["knowledge_points"]):
            point = KnowledgePoint(
                course_id=0,
                title=spec["title"],
                summary=spec["summary"],
                chapter=spec["chapter"],
                order_index=index,
                difficulty=spec["difficulty"],
                prerequisites_json=spec["prerequisite_keys"],
            )
            setattr(point, "builder_key", spec["key"])
            points.append(point)
            for ref in spec["source_refs"]:
                source = chunk_by_ref.get((ref["material_id"], ref["chunk_index"]))
                if source is None:
                    continue
                knowledge_chunks.append(KnowledgeChunk(
                    course_id=0,
                    material_id=None,  # type: ignore[arg-type]
                    knowledge_point_id=None,
                    content=source.content,
                    page_number=source.page_number,
                    section_title=source.section_title or spec["title"],
                    embedding=None,
                    metadata_json={
                        "source_material_id": source.material_id,
                        "source_chunk_index": source.chunk_index,
                        "source_filename": filename_by_material.get(source.material_id, "课程资料"),
                        "knowledge_point_order": index,
                        "knowledge_point_key": spec["key"],
                        "end_page_number": source.end_page_number,
                        "section_path": list(source.section_path_json or []),
                    },
                ))
        if self.service.embedding_service is not None and knowledge_chunks:
            try:
                self.service._best_effort_embed_chunks(state["user"], knowledge_chunks)
            except Exception:
                state["warnings"].append("外部向量服务不可用，课程仍可使用关键词检索。")
        return points, knowledge_chunks

    def _persist(self, state: CourseBuilderState) -> dict[str, Any]:
        started = perf_counter()
        self._job_before(state, "persist")
        quality = state["quality"]
        if not quality.get("passed"):
            raise self.service.generation_error("课程质量未通过，禁止持久化。")
        materials = state["materials"]
        structure = state["structure"]
        title = str(state.get("requested_title") or structure.get("title") or Path(materials[0].filename).stem).strip()[:255]
        course = Course(owner_id=state["user_id"], title=title, description=structure["description"], subject=structure["subject"], source_type="uploaded", visibility="private", status="ready", agent_trace_id=state["trace_id"], structure_json={})
        enrollment = CourseEnrollment(user_id=state["user_id"], course_id=0, role="learner", progress_percent=Decimal("0"))
        course_materials = [self.service._build_course_material(state["user"], material) for material in materials]
        for item in course_materials:
            item.agent_trace_id = state["trace_id"]
        links = [CourseMaterialLink(course_id=0, material_id=material.id, added_by_user_id=state["user_id"], usage_type="course_source") for material in materials]
        try:
            created = self.service.repository.add_course_graph(course, enrollment, course_materials, links, state["knowledge_points"], state["knowledge_chunks"])
            chapters: dict[str, list[str]] = defaultdict(list)
            for point in state["knowledge_points"]:
                chapters[str(point.chapter or "课程内容")].append(str(point.id))
            context = state.get("learner_context")
            course.structure_json = {
                "schema_version": 3,
                "learning_objectives": structure["learning_objectives"],
                "chapters": [{"title": chapter, "knowledge_point_ids": ids} for chapter, ids in chapters.items()],
                "generation_mode": structure["generation_mode"],
                "review_mode": state.get("review_mode", "rules_only"),
                "review_result": state["review_result"],
                "quality": quality,
                "source_coverage": {"source_chunk_count": len(state["source_chunks"]), "mapped_source_count": quality["mapped_source_count"]},
                "prompt_version": self.prompt_version,
                **china_first_content_policy.metadata(),
                "warnings": list(dict.fromkeys(state.get("warnings", []))),
                "profile_applied_version": context.profile_applied_version if context is not None else 0,
            }
            self.service.repository.commit()
            self.service.repository.refresh(created)
        except Exception:
            self.service.repository.rollback()
            self._job_after(state, "persist", status="failed", progress_percent=96, label="课程创建失败")
            raise
        result = CreateCourseFromMaterialsResult(course=self.service._build_summary(created, len(course_materials), len(state["knowledge_points"]), len(state["knowledge_chunks"])), knowledge_points=[self.service._build_knowledge_point(point) for point in state["knowledge_points"]])
        self._record(state, "persist", 11, "completed", {"artifact_id": str(created.id), **quality}, started)
        self._job_after(state, "persist")
        return {"result": result}

    def _deterministic_chapter_points(self, chapter: dict[str, Any], chunks: list[MaterialChunk]) -> list[dict[str, Any]]:
        target = max(1, min(len(chunks), int(chapter.get("target_count") or 1)))
        section_groups: list[dict[str, Any]] = []
        group_by_section: dict[str, dict[str, Any]] = {}
        for position, chunk in enumerate(chunks):
            section_id = str((chunk.metadata_json or {}).get("section_id") or f"section-{chunk.chunk_index}")
            group = group_by_section.get(section_id)
            if group is None:
                group = {
                    "id": section_id,
                    "title": self._clean_title(chunk.section_title or ""),
                    "path": list(chunk.section_path_json or []),
                    "position": position,
                    "chunks": [],
                }
                group_by_section[section_id] = group
                section_groups.append(group)
            group["chunks"].append(chunk)

        while len(section_groups) < target:
            splittable = max(section_groups, key=lambda item: len(item["chunks"]), default=None)
            if splittable is None or len(splittable["chunks"]) <= 1:
                break
            split_at = ceil(len(splittable["chunks"]) / 2)
            tail = {
                **splittable,
                "id": f"{splittable['id']}-split-{len(section_groups) + 1}",
                "position": splittable["position"] + split_at,
                "chunks": splittable["chunks"][split_at:],
            }
            splittable["chunks"] = splittable["chunks"][:split_at]
            section_groups.append(tail)
            section_groups.sort(key=lambda item: item["position"])

        if len(section_groups) <= target:
            selected = list(section_groups)
        else:
            selected = sorted(
                sorted(section_groups, key=self._section_priority, reverse=True)[:target],
                key=lambda item: item["position"],
            )

        assigned: dict[str, list[MaterialChunk]] = {item["id"]: list(item["chunks"]) for item in selected}
        selected_ids = set(assigned)
        for group in section_groups:
            if group["id"] in selected_ids:
                continue
            nearest = min(selected, key=lambda item: abs(int(item["position"]) - int(group["position"])))
            assigned[nearest["id"]].extend(group["chunks"])

        points: list[dict[str, Any]] = []
        used_titles: set[str] = set()
        for selected_group in selected:
            group = sorted(assigned[selected_group["id"]], key=lambda item: item.chunk_index)
            candidates: list[str] = []
            for chunk in group:
                candidates.extend(reversed([str(item).strip() for item in list(chunk.section_path_json or []) if str(item).strip()]))
                if str(chunk.section_title or "").strip():
                    candidates.append(str(chunk.section_title).strip())
            if selected_group["title"]:
                candidates.insert(0, selected_group["title"])
            chapter_title = self._clean_title(chapter["title"])
            titles = [self._clean_title(item) for item in candidates]
            titles = [item for item in titles if self._is_knowledge_title(item)]
            title = None
            if len(group) == 1:
                title = next((item for item in titles if self._normalize(item) not in used_titles), None)
            if not title:
                title = next(
                    (
                        item
                        for item in titles
                        if self._normalize(item) != self._normalize(chapter_title)
                        and self._normalize(item) not in used_titles
                    ),
                    None,
                )
            if not title and not points and self._is_knowledge_title(chapter_title):
                title = chapter_title
            if not title:
                title = self._title_from_content(group[0].content, len(points) + 1)
                if title.startswith("核心概念"):
                    repeated_base = next(
                        (item for item in titles if self._normalize(item) != self._normalize(chapter_title)),
                        chapter_title,
                    )
                    title = f"{repeated_base[:28]}：专题 {len(points) + 1}"
            title = self._clean_title(title)
            normalized_title = self._normalize(title)
            if not self._is_knowledge_title(title) or not normalized_title or normalized_title in used_titles:
                repeated_base = next(
                    (item for item in titles if self._normalize(item) != self._normalize(chapter_title)),
                    chapter_title,
                )
                title = f"{repeated_base[:28]}：专题 {len(points) + 1}"
                normalized_title = self._normalize(title)
            used_titles.add(normalized_title)
            points.append({
                "title": title[:120],
                "chapter": chapter["title"],
                "summary": safe_text(" ".join(chunk.content for chunk in group), limit=600),
                "difficulty": "easy" if len(points) < max(1, target // 3) else "medium" if len(points) < max(2, target * 2 // 3) else "hard",
                "source_refs": [{"material_id": chunk.material_id, "chunk_index": chunk.chunk_index} for chunk in group],
            })
        return points

    @classmethod
    def _section_priority(cls, section: dict[str, Any]) -> tuple[float, int]:
        title = cls._clean_title(section.get("title"))
        content_size = sum(len(chunk.content) for chunk in section.get("chunks", []))
        score = min(3.0, content_size / 1200)
        if cls._is_knowledge_title(title):
            score += 2.0
        if len(section.get("path") or []) >= 3:
            score += 2.0
        if re.search(
            r"(?:算法|排序|查找|搜索|遍历|存储|实现|操作|性质|复杂度|匹配|矩阵|广义表|链表|栈|队列|树|图|散列|路径|拓扑|关键|递归|编码|归并|基数|堆|AVL|B\+?)",
            title,
            flags=re.IGNORECASE,
        ):
            score += 4.0
        if re.search(r"(?:案例引入|案例分析|类型定义|基本概念)$", title):
            score -= 2.5
        return score, -int(section.get("position") or 0)

    def _model_chapter_points(self, state: CourseBuilderState, chapter: dict[str, Any], chunks: list[MaterialChunk], fallback: list[dict[str, Any]]) -> list[dict[str, Any]] | None:
        if self.service.model_service is None:
            return None
        source_map = {f"m{chunk.material_id}-c{chunk.chunk_index}": chunk for chunk in chunks}
        evidence = "\n".join(f"{key} | {chunk.section_title or chapter['title']} | {safe_text(chunk.content, limit=320)}" for key, chunk in list(source_map.items())[:80])
        context = state.get("learner_context")
        profile_hint = {
            "learning_goal": context.advisory_value("learning_goal") if context is not None else "",
            "knowledge_foundation": context.trusted_value("knowledge_foundation") if context is not None else "",
        }
        try:
            raw = self.service.model_service.chat_completion(state["user"], [
                {"role": "system", "content": "你是 CourseBuilderGraph 的章节概念 Agent。只输出 JSON；不得创建证据中不存在的概念、公式或算法。" + china_first_content_policy.prompt_instruction()},
                {"role": "user", "content": f"章节={chapter['title']}，目标知识点数约 {chapter['target_count']}。可信画像提示={profile_hint}。\n证据：\n{evidence}\n返回 points 数组，每项含 title、summary、difficulty、source_keys。"},
            ])
        except Exception:
            return None
        parsed = parse_json_object(raw)
        raw_points = parsed.get("points") if isinstance(parsed, dict) else None
        if not isinstance(raw_points, list):
            return None
        points = []
        used_refs: set[tuple[int, int]] = set()
        for item in raw_points[: min(24, max(2, chapter["target_count"] * 2))]:
            if not isinstance(item, dict):
                continue
            refs = []
            for key in item.get("source_keys", []):
                chunk = source_map.get(str(key))
                if chunk is not None:
                    refs.append({"material_id": chunk.material_id, "chunk_index": chunk.chunk_index})
                    used_refs.add((chunk.material_id, chunk.chunk_index))
            title = safe_text(item.get("title"), limit=120)
            if not title or not refs:
                continue
            difficulty = str(item.get("difficulty") or "medium")
            points.append({"title": title, "chapter": chapter["title"], "summary": safe_text(item.get("summary"), limit=600), "difficulty": difficulty if difficulty in {"easy", "medium", "hard"} else "medium", "source_refs": refs})
        if not points:
            return None
        remaining = [chunk for chunk in chunks if (chunk.material_id, chunk.chunk_index) not in used_refs]
        for index, chunk in enumerate(remaining):
            points[index % len(points)]["source_refs"].append({"material_id": chunk.material_id, "chunk_index": chunk.chunk_index})
        return points

    def _model_review(self, state: CourseBuilderState, quality: dict[str, Any]) -> dict[str, Any] | None:
        if self.service.model_service is None:
            return None
        candidate = [{"title": point["title"], "chapter": point["chapter"], "summary": point["summary"], "evidence_count": len(point["source_refs"])} for point in state["structure"]["knowledge_points"]]
        evidence = [safe_text(chunk.content, limit=100) for chunk in state["source_chunks"][:60]]
        try:
            raw = self.service.model_service.chat_completion(state["user"], [
                {"role": "system", "content": "你是 CourseBuilderGraph ReviewAgent。审核完整候选与证据，只输出 JSON，不得新增事实。" + china_first_content_policy.prompt_instruction()},
                {"role": "user", "content": f"质量指标={quality}\n完整候选={candidate}\n证据短摘录={evidence}\n返回 review_status、confidence、risk_flags、safety_summary。"},
            ])
        except Exception:
            return None
        return review_contract(parse_json_object(raw), default_summary="课程内容、证据和结构审核完成。")

    def _quality(self, state: CourseBuilderState) -> tuple[dict[str, Any], list[str]]:
        specs = state["structure"]["knowledge_points"]
        source_refs = {(chunk.material_id, chunk.chunk_index) for chunk in state["source_chunks"]}
        mapped = {(ref["material_id"], ref["chunk_index"]) for point in specs for ref in point.get("source_refs", [])}
        coverage = len(mapped & source_refs) / max(1, len(source_refs))
        titles = [self._normalize(point.get("title")) for point in specs]
        duplicate_rate = 1 - len(set(titles)) / max(1, len(titles))
        source_chapters = {str(chapter["title"]) for chapter in state["chapters"]}
        covered_chapters = {str(point.get("chapter")) for point in specs}
        risks = []
        if not specs or len(specs) > 120:
            risks.append("invalid_point_count")
        if coverage < 0.85:
            risks.append("low_source_coverage")
        if duplicate_rate > 0:
            risks.append("duplicate_titles")
        if not source_chapters.issubset(covered_chapters):
            risks.append("uncovered_chapter")
        if any(not point.get("source_refs") for point in specs):
            risks.append("missing_evidence")
        if any(contains_sensitive_text(point) for point in specs):
            risks.append("sensitive_output")
        if any(not self._is_knowledge_title(str(point.get("title") or "")) for point in specs):
            risks.append("invalid_knowledge_point_title")
        graph = {point["key"]: list(point.get("prerequisite_keys", [])) for point in specs}
        if self._has_cycle(graph):
            risks.append("prerequisite_cycle")
        quality = {
            "passed": not risks,
            "knowledge_point_count": len(specs),
            "chapter_count": len(source_chapters),
            "source_chunk_count": len(source_refs),
            "mapped_source_count": len(mapped & source_refs),
            "source_coverage_rate": round(coverage, 4),
            "evidence_completeness": round(sum(1 for point in specs if point.get("source_refs")) / max(1, len(specs)), 4),
            "duplicate_title_rate": round(duplicate_rate, 4),
            "knowledge_point_density": round(len(specs) / max(1, len(source_chapters)), 2),
            "risk_flags": risks,
            "prompt_version": self.prompt_version,
        }
        return quality, risks

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
            if any(parent in graph and visit(parent) for parent in graph.get(node, [])):
                return True
            visiting.remove(node)
            visited.add(node)
            return False
        return any(visit(node) for node in graph)

    @staticmethod
    def _terms(value: str) -> set[str]:
        lowered = value.casefold()
        return {token for token in [*re.findall(r"[a-z][a-z0-9+*#-]{1,}", lowered), *re.findall(r"[一-鿿]{2,6}", lowered)] if len(token) >= 2}

    @staticmethod
    def _normalize(value: Any) -> str:
        return "".join(str(value or "").casefold().split())

    @classmethod
    def _title_from_content(cls, content: str, index: int) -> str:
        first = safe_text(content.split("。", 1)[0], limit=42).strip("：:，,；;。")
        first = cls._clean_title(first)
        return first if cls._is_knowledge_title(first) else f"核心概念 {index}"

    @staticmethod
    def _clean_title(value: Any) -> str:
        title = " ".join(str(value or "").replace("　", " ").split()).strip("：:，,；;。")
        replacements = {
            "时问": "时间",
            "空问": "空间",
            "橾式": "模式",
            "插人": "插入",
            "归井": "归并",
            "二又树": "二叉树",
            "算祛": "算法",
            "定义和特权": "定义和特点",
        }
        for source, target in replacements.items():
            title = title.replace(source, target)
        title = re.sub(r"(?:\s*[.·_-]+|[一—-]{2,})$", "", title).strip()
        return title[:120]

    @staticmethod
    def _is_knowledge_title(value: str) -> bool:
        title = value.strip()
        if not 2 <= len(title) <= 42:
            return False
        if len(re.findall(r"[，,；;。！？!?]", title)) > 0:
            return False
        if re.match(r"^(?:图|表|例|式)\s*[\d.]+", title, flags=re.IGNORECASE):
            return False
        if re.search(r"(?:所示|参见|见图|见表|小节中|都属于|这种情况|至此|如下所述|上式|下式|前面已经|由此可见)", title):
            return False
        if re.search(r"(?:^|\s)[(（]?[a-z][)）](?:\s|和|、|$)", title, flags=re.IGNORECASE):
            return False
        if re.search(r"[={}\\/<>]", title) or re.search(r"\b(?:cout|printf|gethead|return|while|for)\b", title, flags=re.IGNORECASE):
            return False
        return bool(re.search(r"[A-Za-z0-9一-鿿]", title))

    def _run_node(self, state: CourseBuilderState, name: str, index: int, work: Callable):
        started = perf_counter()
        self._job_before(state, name)
        try:
            with model_execution_scope(execution_context_for_state(state, workflow=self.workflow, node_name=name)):
                result, metadata = work()
        except Exception as exc:
            self._record(state, name, index, "failed", {"error_code": exc.__class__.__name__}, started)
            self._job_after(state, name, status="failed", progress_percent=max(0, self.job_progress[name][0] - 1), label="节点执行失败")
            raise
        self._record(state, name, index, "completed", metadata, started)
        self._job_after(state, name)
        return result

    @staticmethod
    def _job_before(state: CourseBuilderState, name: str) -> None:
        context = state.get("job_context")
        if context is not None:
            context.before_node(name)

    def _job_after(self, state: CourseBuilderState, name: str, *, status: str = "completed", progress_percent: int | None = None, label: str | None = None) -> None:
        context = state.get("job_context")
        if context is None:
            return
        progress, default_label = self.job_progress[name]
        context.after_node(name=name, label=label or default_label, progress_percent=progress if progress_percent is None else progress_percent, status=status)

    def _record(self, state: CourseBuilderState, name: str, index: int, status: str, metadata: dict[str, Any], started: float) -> None:
        if self.service.trace_recorder is None:
            return
        self.service.trace_recorder.record(
            trace_id=state["trace_id"], user_id=state["user_id"], course_id=None, agent_name=name, step_index=index,
            status=status, input_summary="处理已确认资料与课程候选。", output_summary="节点已完成。" if status == "completed" else "节点失败，未保留半成品课程。",
            duration_ms=max(0, int((perf_counter() - started) * 1000)), workflow=self.workflow, artifact_type="course",
            artifact_id=metadata.get("artifact_id"), metadata=metadata,
        )

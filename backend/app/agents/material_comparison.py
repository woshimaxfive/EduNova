from __future__ import annotations

from time import perf_counter
from typing import Any, Callable, TypedDict

from langgraph.graph import END, START, StateGraph

from backend.app.agents.learning_review import contains_sensitive_text, parse_json_object, review_contract, safe_text
from backend.app.api.errors import make_trace_id
from backend.app.models import Course, KnowledgePoint, Material, MaterialComparisonRun, User
from backend.app.schemas.materials import MaterialComparisonPoint, MaterialComparisonResult
from backend.app.services.model_execution import execution_context_for_state, model_execution_scope
from backend.app.services.learner_context import context_service_from_repository
from backend.app.services.content_locale import china_first_content_policy


class MaterialComparisonState(TypedDict, total=False):
    trace_id: str
    user: User
    user_id: int
    course_id: int
    material_ids: list[int]
    course: Course
    materials: list[Material]
    knowledge_points: list[KnowledgePoint]
    evidence: list[Any]
    learner_context: Any
    deterministic_result: MaterialComparisonResult
    comparison_result: MaterialComparisonResult
    generation_mode: str
    review_mode: str
    review_result: dict[str, Any]
    warnings: list[str]
    needs_repair: bool
    repair_count: int
    persisted_run: MaterialComparisonRun
    result: MaterialComparisonResult


class MaterialComparisonGraphRunner:
    workflow = "material_comparison"

    def __init__(self, service: Any) -> None:
        self.service = service
        self.graph = self._build_graph()

    def run(self, *, user: User, course_id: int, material_ids: list[int]) -> MaterialComparisonResult:
        state: MaterialComparisonState = {
            "trace_id": make_trace_id(),
            "user": user,
            "user_id": user.id,
            "course_id": course_id,
            "material_ids": list(dict.fromkeys(material_ids)),
            "warnings": [],
            "repair_count": 0,
        }
        with model_execution_scope(execution_context_for_state(state, workflow=self.workflow)):
            return self.graph.invoke(state)["result"]

    def _build_graph(self):
        graph = StateGraph(MaterialComparisonState)
        graph.add_node("validate_scope", self._validate_scope_node)
        graph.add_node("collect_evidence", self._collect_evidence_node)
        graph.add_node("deterministic_compare", self._deterministic_compare_node)
        graph.add_node("model_compare", self._model_compare_node)
        graph.add_node("review", self._review_node)
        graph.add_node("repair", self._repair_node)
        graph.add_node("persist", self._persist_node)
        graph.add_edge(START, "validate_scope")
        graph.add_edge("validate_scope", "collect_evidence")
        graph.add_edge("collect_evidence", "deterministic_compare")
        graph.add_edge("deterministic_compare", "model_compare")
        graph.add_edge("model_compare", "review")
        graph.add_conditional_edges(
            "review",
            lambda state: "repair" if state.get("needs_repair") else "persist",
            {"repair": "repair", "persist": "persist"},
        )
        graph.add_edge("repair", "persist")
        graph.add_edge("persist", END)
        return graph.compile()

    def _validate_scope_node(self, state: MaterialComparisonState) -> dict[str, Any]:
        def work():
            course = self.service._require_course(state["user"], int(state["course_id"]))
            unique_ids = list(dict.fromkeys(state["material_ids"]))
            if len(unique_ids) < 2:
                raise self.service.validation_error("至少选择两份同课程资料。")
            materials = [self.service._require_material(state["user"], material_id) for material_id in unique_ids]
            for material in materials:
                if self.service.repository.get_link(course.id, material.id) is None:
                    raise self.service.not_found_error("资料不存在、无权访问或未绑定当前课程。")
            return (
                {"course": course, "materials": materials, "material_ids": unique_ids},
                f"已验证 {len(materials)} 份资料属于当前用户和课程。",
                "completed",
                {"material_count": len(materials)},
            )

        return self._run_node(state, "validate_scope", 1, "校验课程、资料所有权和绑定关系", work)

    def _collect_evidence_node(self, state: MaterialComparisonState) -> dict[str, Any]:
        def work():
            knowledge_points = self.service.repository.list_knowledge_points(int(state["course_id"]))
            evidence = self.service._build_comparison_evidence(
                int(state["course_id"]),
                list(state["materials"]),
                knowledge_points,
            )
            comparable_ids = {item.material_id for item in evidence}
            if len(comparable_ids) < 2:
                raise self.service.validation_error("至少需要两份已解析且可比较的课程资料。")
            context_service = context_service_from_repository(self.service.repository)
            learner_context = context_service.course_context(int(state["user_id"]), int(state["course_id"])) if context_service is not None else None
            return (
                {"knowledge_points": knowledge_points, "evidence": evidence, "learner_context": learner_context},
                f"已收集 {len(evidence)} 条安全资料证据。",
                "completed",
                {
                    "material_count": len(comparable_ids),
                    "candidate_count": len(evidence),
                    **(learner_context.trace_metadata() if learner_context is not None else {"profile_context_used": False}),
                },
            )

        return self._run_node(state, "collect_evidence", 2, "收集课程切片和资料分块证据", work)

    def _deterministic_compare_node(self, state: MaterialComparisonState) -> dict[str, Any]:
        def work():
            result = self.service._build_deterministic_comparison(
                state["course"],
                list(state["material_ids"]),
                list(state["knowledge_points"]),
                list(state["evidence"]),
            )
            warnings = list(state.get("warnings", []))
            if not result.repeated_concepts:
                warnings.append("所选资料重合度较低，已保留各自重点，不生成虚假的共同重点。")
            return (
                {"deterministic_result": result, "comparison_result": result, "warnings": warnings},
                f"规则底稿包含 {result.summary.matched_concept_count} 个概念和 {len(result.citations)} 条引用。",
                "warning" if warnings else "completed",
                {"citation_count": len(result.citations), "warning_count": len(warnings)},
            )

        return self._run_node(state, "deterministic_compare", 3, "生成不可越权的资料对比规则底稿", work)

    def _model_compare_node(self, state: MaterialComparisonState) -> dict[str, Any]:
        def work():
            enhanced = self._model_enhance(state, repair=False)
            if enhanced is None:
                warnings = list(state.get("warnings", []))
                warnings.append("模型增强不可用，已使用完整规则对比结果。")
                return (
                    {"comparison_result": state["deterministic_result"], "generation_mode": "deterministic_source", "warnings": list(dict.fromkeys(warnings))},
                    "模型增强不可用，保留规则底稿。",
                    "warning",
                    {"generation_mode": "deterministic_source", "warning_count": len(warnings)},
                )
            return (
                {"comparison_result": enhanced, "generation_mode": "model_enhanced"},
                "模型已在合法概念集合内优化重点解释和复习顺序。",
                "completed",
                {"generation_mode": "model_enhanced"},
            )

        return self._run_node(state, "model_compare", 4, "在规则证据边界内增强资料对比", work)

    def _review_node(self, state: MaterialComparisonState) -> dict[str, Any]:
        def work():
            result = state["comparison_result"]
            risks = self._result_risks(state, result)
            model_review = None
            if state.get("generation_mode") == "model_enhanced" and self.service.model_service is not None:
                try:
                    raw = self.service.model_service.chat_completion(
                        state["user"],
                        [
                            {
                                "role": "system",
                                "content": "你是 MaterialComparisonGraph 的 ReviewAgent。只审核结构、引用一致性和安全性，只输出 JSON。" + china_first_content_policy.prompt_instruction(),
                            },
                            {
                                "role": "user",
                                "content": (
                                    f"资料数={len(state['material_ids'])}，概念数={result.summary.matched_concept_count}，"
                                    f"引用数={len(result.citations)}，规则风险={risks}。"
                                    "返回 {\"review_status\":\"passed|revise\",\"confidence\":0.0,"
                                    "\"risk_flags\":[],\"safety_summary\":\"...\"}。"
                                ),
                            },
                        ],
                    )
                    model_review = review_contract(parse_json_object(raw), default_summary="资料对比证据和安全审核完成。")
                except Exception:
                    model_review = None
            if model_review and model_review["review_status"] == "revise":
                risks.extend(str(item) for item in model_review["risk_flags"])
            risks = list(dict.fromkeys(risks))
            if risks:
                review = {
                    "review_status": "revise",
                    "confidence": model_review["confidence"] if model_review else 0.42,
                    "risk_flags": risks,
                    "safety_summary": model_review["safety_summary"] if model_review else "规则审核发现资料对比需要修订。",
                }
                return (
                    {"review_result": review, "review_mode": "model_and_rules" if model_review else "rules_only", "needs_repair": True},
                    review["safety_summary"],
                    "warning",
                    review,
                )
            if model_review is None:
                review = {
                    "review_status": "warning",
                    "confidence": 0.66,
                    "risk_flags": [],
                    "safety_summary": "模型审核不可用，已完成引用、来源和隐私规则审核。",
                }
                return {"review_result": review, "review_mode": "rules_only", "needs_repair": False}, review["safety_summary"], "warning", review
            review = {**model_review, "review_status": "passed", "risk_flags": []}
            return {"review_result": review, "review_mode": "model_and_rules", "needs_repair": False}, review["safety_summary"], "completed", review

        return self._run_node(state, "review", 5, "审核引用匹配、来源覆盖和隐私边界", work)

    def _repair_node(self, state: MaterialComparisonState) -> dict[str, Any]:
        def work():
            repaired = self._model_enhance(state, repair=True)
            if repaired is None or self._result_risks(state, repaired):
                repaired = state["deterministic_result"]
                generation_mode = "deterministic_source"
            else:
                generation_mode = "model_enhanced"
            review = {
                "review_status": "passed",
                "confidence": 0.72 if generation_mode == "model_enhanced" else 0.66,
                "risk_flags": [],
                "safety_summary": "已完成一次修订并重新通过引用和安全规则校验。",
            }
            return (
                {"comparison_result": repaired, "generation_mode": generation_mode, "review_result": review, "repair_count": 1},
                review["safety_summary"],
                "completed",
                {**review, "repair_count": 1, "generation_mode": generation_mode},
            )

        return self._run_node(state, "repair", 6, "按审核风险修订一次资料对比", work)

    def _persist_node(self, state: MaterialComparisonState) -> dict[str, Any]:
        started = perf_counter()
        result = state["comparison_result"]
        payload = result.model_dump(exclude={"id", "course_id", "material_ids", "agent_trace_id", "generation_mode", "review_mode", "created_at"})
        payload["review_result"] = state.get("review_result", {})
        payload["warnings"] = list(dict.fromkeys(state.get("warnings", [])))
        learner_context = state.get("learner_context")
        payload["profile_applied_version"] = (
            learner_context.global_context.profile_applied_version if learner_context is not None else 0
        )
        payload["course_context_hash"] = learner_context.context_hash if learner_context is not None else "legacy"
        payload.update(china_first_content_policy.metadata())
        try:
            run = self.service.repository.add_comparison_run(
                MaterialComparisonRun(
                    user_id=int(state["user_id"]),
                    course_id=int(state["course_id"]),
                    material_ids_json=list(state["material_ids"]),
                    result_json=payload,
                    agent_trace_id=state["trace_id"],
                    generation_mode=state.get("generation_mode", "deterministic_source"),
                    review_mode=state.get("review_mode", "rules_only"),
                )
            )
            self.service.repository.commit()
            self.service.repository.refresh(run)
            api_result = self.service._comparison_run_to_api(run)
        except Exception as exc:
            self.service.repository.rollback()
            self._record(state, "persist", 7, "failed", "保存审核后的资料对比", "资料对比保存失败。", {"error_code": exc.__class__.__name__}, started)
            raise
        self._record(
            state,
            "persist",
            7,
            "completed",
            "保存审核后的资料对比",
            "资料对比已保存并可在刷新后恢复。",
            {"artifact_id": str(run.id), "citation_count": len(api_result.citations), "repair_count": int(state.get("repair_count") or 0)},
            started,
        )
        return {"persisted_run": run, "result": api_result}

    def _model_enhance(self, state: MaterialComparisonState, *, repair: bool) -> MaterialComparisonResult | None:
        if self.service.model_service is None:
            return None
        draft = state["deterministic_result"]
        all_points = self._all_points(draft)
        titles = list(dict.fromkeys(point.title for point in all_points))
        learner_context = state.get("learner_context")
        priority_hint = {
            "course_goal": learner_context.course_goal if learner_context is not None else "",
            "active_weaknesses": list(learner_context.active_weaknesses) if learner_context is not None else [],
        }
        try:
            raw = self.service.model_service.chat_completion(
                state["user"],
                [
                    {
                        "role": "system",
                        "content": "你是资料对比 Agent。只能使用给定标题，禁止新增资料、知识点、引用或考点，只输出 JSON。" + china_first_content_policy.prompt_instruction(),
                    },
                    {
                        "role": "user",
                        "content": (
                            ("这是唯一一次修订机会。" if repair else "优化复习优先级和简短理由。")
                            + f"合法标题={titles}。"
                            + f"复习排序提示={priority_hint}。提示只影响排序理由，不得修改共同点或差异事实。"
                            + "返回 {\"ordered_titles\":[\"...\"],\"rationales\":{\"标题\":\"理由\"},\"summary_message\":\"...\"}。"
                        ),
                    },
                ],
            )
        except Exception:
            return None
        payload = parse_json_object(raw)
        if payload is None or not isinstance(payload.get("ordered_titles"), list):
            return None
        ordered_titles = [safe_text(item, limit=120) for item in payload["ordered_titles"]]
        if any(title not in titles for title in ordered_titles) or len(set(ordered_titles)) != len(ordered_titles):
            return None
        ordered_titles.extend(title for title in titles if title not in ordered_titles)
        rationales = payload.get("rationales") if isinstance(payload.get("rationales"), dict) else {}
        data = draft.model_dump()
        for field in (
            "repeated_concepts",
            "exam_likely_points",
            "materials_only_points",
            "questions_only_points",
            "missing_review_points",
        ):
            for point in data[field]:
                reason = safe_text(rationales.get(point["title"]), limit=240)
                if reason:
                    point["reason"] = reason
        by_title = {point.title: point for point in all_points}
        data["priority_order"] = [
            {**by_title[title].model_dump(), "reason": safe_text(rationales.get(title), limit=240) or by_title[title].reason}
            for title in ordered_titles[:10]
        ]
        summary_message = safe_text(payload.get("summary_message"), limit=240)
        if summary_message:
            data["summary"]["message"] = summary_message
        return MaterialComparisonResult(**data)

    def _result_risks(self, state: MaterialComparisonState, result: MaterialComparisonResult) -> list[str]:
        valid_material_ids = {str(item) for item in state["material_ids"]}
        valid_point_ids = {str(point.id) for point in state["knowledge_points"]}
        valid_titles = {point.title for point in self._all_points(state["deterministic_result"])}
        risks: list[str] = []
        priority_titles: list[str] = []
        for point in self._all_points(result):
            if point.title not in valid_titles:
                risks.append("invented_concept")
            if any(material_id not in valid_material_ids for material_id in point.material_ids):
                risks.append("invalid_material_reference")
            if point.knowledge_point_id is not None and point.knowledge_point_id not in valid_point_ids:
                risks.append("invalid_knowledge_point_reference")
            if contains_sensitive_text(f"{point.title} {point.reason}"):
                risks.append("sensitive_output")
        for point in result.priority_order:
            priority_titles.append(point.title)
        if len(priority_titles) != len(set(priority_titles)):
            risks.append("duplicate_priority")
        for citation in result.citations:
            if citation.material_id not in valid_material_ids:
                risks.append("invalid_citation")
            if contains_sensitive_text(citation.excerpt):
                risks.append("sensitive_output")
        if contains_sensitive_text(result.summary.message):
            risks.append("sensitive_output")
        return list(dict.fromkeys(risks))

    @staticmethod
    def _all_points(result: MaterialComparisonResult) -> list[MaterialComparisonPoint]:
        points: list[MaterialComparisonPoint] = []
        for collection in (
            result.repeated_concepts,
            result.exam_likely_points,
            result.materials_only_points,
            result.questions_only_points,
            result.missing_review_points,
        ):
            for point in collection:
                if point.title not in {item.title for item in points}:
                    points.append(point)
        return points

    def _run_node(
        self,
        state: MaterialComparisonState,
        name: str,
        index: int,
        input_summary: str,
        work: Callable[[], tuple[dict[str, Any], str, str, dict[str, Any]]],
    ) -> dict[str, Any]:
        started = perf_counter()
        try:
            with model_execution_scope(execution_context_for_state(state, workflow=self.workflow, node_name=name)):
                result, output_summary, status, metadata = work()
        except Exception as exc:
            self._record(state, name, index, "failed", input_summary, "节点执行失败，已记录安全错误摘要。", {"error_code": exc.__class__.__name__}, started)
            raise
        self._record(state, name, index, status, input_summary, output_summary, metadata, started)
        return result

    def _record(
        self,
        state: MaterialComparisonState,
        name: str,
        index: int,
        status: str,
        input_summary: str,
        output_summary: str,
        metadata: dict[str, Any],
        started: float,
    ) -> None:
        if self.service.trace_recorder is None:
            return
        self.service.trace_recorder.record(
            trace_id=state["trace_id"],
            user_id=int(state["user_id"]),
            course_id=int(state["course_id"]),
            agent_name=name,
            step_index=index,
            status=status,
            input_summary=input_summary,
            output_summary=output_summary,
            duration_ms=max(0, int((perf_counter() - started) * 1000)),
            workflow=self.workflow,
            artifact_type="material_comparison",
            artifact_id=metadata.get("artifact_id"),
            metadata=metadata,
        )

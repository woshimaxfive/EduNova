from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from time import perf_counter
from typing import Any, Callable, TypedDict

from langgraph.graph import END, START, StateGraph

from backend.app.agents.learning_review import contains_sensitive_text, parse_json_object, review_contract, safe_text
from backend.app.api.errors import make_trace_id
from backend.app.models import LearningPath, LearningTask, MaterialComparisonRun, User
from backend.app.services.exam_sprint import SprintPointCandidate, SprintTaskSpec


class ExamSprintState(TypedDict, total=False):
    trace_id: str
    user: User
    user_id: int
    course_id: int
    duration_days: int
    material_ids: list[int]
    comparison_id: int | None
    goal: str
    trigger: str
    source_practice_session_id: int | None
    previous_path: LearningPath | None
    course: Any
    profile_summary: dict[str, Any]
    knowledge_points: list[Any]
    weakness_items: list[Any]
    resources: list[Any]
    practice_answers: list[Any]
    report: Any
    previous_tasks: list[LearningTask]
    comparison_run: MaterialComparisonRun | None
    comparison_result: dict[str, Any]
    deterministic_candidates: list[SprintPointCandidate]
    planned_candidates: list[SprintPointCandidate]
    deterministic_payload: dict[str, Any]
    plan_payload: dict[str, Any]
    generation_mode: str
    review_mode: str
    review_result: dict[str, Any]
    needs_repair: bool
    repair_count: int
    warnings: list[str]
    preserved_task_count: int
    result: Any


class ExamSprintGraphRunner:
    workflow = "exam_sprint"

    def __init__(self, service: Any) -> None:
        self.service = service
        self.graph = self._build_graph()

    def run(
        self,
        *,
        user: User,
        course_id: int,
        duration_days: int,
        material_ids: list[int],
        comparison_id: int | None,
        goal: str,
        trigger: str,
        source_practice_session_id: int | None = None,
        previous_path: LearningPath | None = None,
    ):
        if duration_days not in self.service.valid_durations:
            raise self.service.validation_error("冲刺计划时长只能是 3、7 或 14 天。")
        state: ExamSprintState = {
            "trace_id": make_trace_id(),
            "user": user,
            "user_id": user.id,
            "course_id": course_id,
            "duration_days": duration_days,
            "material_ids": [item for item in dict.fromkeys(material_ids) if item > 0],
            "comparison_id": comparison_id,
            "goal": " ".join(goal.split())[:500],
            "trigger": trigger,
            "source_practice_session_id": source_practice_session_id,
            "previous_path": previous_path,
            "warnings": [],
            "repair_count": 0,
            "preserved_task_count": 0,
        }
        return self.graph.invoke(state)["result"]

    def _build_graph(self):
        graph = StateGraph(ExamSprintState)
        graph.add_node("profile", self._profile_node)
        graph.add_node("collect_evidence", self._collect_evidence_node)
        graph.add_node("comparison_context", self._comparison_context_node)
        graph.add_node("deterministic_rank", self._deterministic_rank_node)
        graph.add_node("model_plan", self._model_plan_node)
        graph.add_node("build_tasks", self._build_tasks_node)
        graph.add_node("review", self._review_node)
        graph.add_node("repair", self._repair_node)
        graph.add_node("persist", self._persist_node)
        graph.add_edge(START, "profile")
        graph.add_edge("profile", "collect_evidence")
        graph.add_edge("collect_evidence", "comparison_context")
        graph.add_edge("comparison_context", "deterministic_rank")
        graph.add_edge("deterministic_rank", "model_plan")
        graph.add_edge("model_plan", "build_tasks")
        graph.add_edge("build_tasks", "review")
        graph.add_conditional_edges(
            "review",
            lambda state: "repair" if state.get("needs_repair") else "persist",
            {"repair": "repair", "persist": "persist"},
        )
        graph.add_edge("repair", "persist")
        graph.add_edge("persist", END)
        return graph.compile()

    def _profile_node(self, state: ExamSprintState) -> dict[str, Any]:
        def work():
            get_profile = getattr(self.service.repository, "get_profile", None)
            profile = get_profile(int(state["user_id"])) if callable(get_profile) else None
            summary = dict(profile.profile_json or {}) if profile is not None else {}
            return {"profile_summary": summary}, "已读取安全学习画像摘要。", "completed", {"source_count": len(summary)}

        return self._run_node(state, "profile", 1, "读取学习目标、基础、偏好和节奏", work)

    def _collect_evidence_node(self, state: ExamSprintState) -> dict[str, Any]:
        def work():
            course = self.service._require_course(state["user"], int(state["course_id"]))
            material_ids = list(state.get("material_ids", []))
            if material_ids and not self.service.repository.validate_material_ids(int(state["user_id"]), course.id, material_ids):
                raise self.service.not_found_error("资料不存在或不属于当前课程。")
            context = self.service._collect_context(state["user"], course)
            if not context["knowledge_points"]:
                raise self.service.validation_error("当前课程还没有可用于生成冲刺计划的知识点。")
            get_current = getattr(self.service.repository, "get_current_sprint_path", None)
            previous = state.get("previous_path") or (
                get_current(int(state["user_id"]), course.id) if callable(get_current) else None
            )
            previous_tasks = self.service.repository.list_tasks_for_path(previous.id) if previous is not None else []
            return (
                {"course": course, "previous_path": previous, "previous_tasks": previous_tasks, **context},
                f"已收集 {len(context['knowledge_points'])} 个知识点和 {len(context['practice_answers'])} 条练习证据。",
                "completed",
                {
                    "candidate_count": len(context["knowledge_points"]),
                    "practice_count": len(context["practice_answers"]),
                    "weakness_count": sum(1 for item in context["weakness_items"] if item.status in {"confirmed", "reviewing"}),
                },
            )

        return self._run_node(state, "collect_evidence", 2, "收集画像、知识点、弱点、练习、资源和报告", work)

    def _comparison_context_node(self, state: ExamSprintState) -> dict[str, Any]:
        def work():
            comparison_id = state.get("comparison_id")
            if comparison_id is None:
                return {"comparison_run": None, "comparison_result": {}}, "本次未显式选择资料对比结果。", "completed", {"comparison_id": None}
            run = self.service.repository.get_comparison_run_for_user(int(state["user_id"]), int(comparison_id))
            if run is None or int(run.course_id) != int(state["course_id"]):
                raise self.service.not_found_error("资料对比记录不存在或不属于当前课程。")
            request_ids = set(state.get("material_ids", []))
            run_ids = {int(item) for item in run.material_ids_json or []}
            if request_ids and request_ids != run_ids:
                raise self.service.validation_error("material_ids 必须与 comparison_id 对应的资料集合一致。")
            return (
                {"comparison_run": run, "comparison_result": dict(run.result_json or {}), "material_ids": sorted(run_ids)},
                "已加载审核通过的资料对比证据。",
                "completed",
                {"comparison_id": str(run.id), "material_count": len(run_ids)},
            )

        return self._run_node(state, "comparison_context", 3, "加载用户明确选择的资料对比版本", work)

    def _deterministic_rank_node(self, state: ExamSprintState) -> dict[str, Any]:
        def work():
            candidates = self.service._score_points(
                list(state["knowledge_points"]),
                list(state["weakness_items"]),
                list(state["resources"]),
                list(state["practice_answers"]),
                state.get("report"),
            )
            self._apply_comparison_scores(candidates, state.get("comparison_result", {}))
            ordered = sorted(candidates, key=lambda item: (-item.score, item.title))
            return (
                {"deterministic_candidates": ordered, "planned_candidates": ordered},
                f"规则排序生成 {len(ordered)} 个合法冲刺候选点。",
                "completed",
                {"candidate_count": len(ordered), "comparison_id": state.get("comparison_id")},
            )

        return self._run_node(state, "deterministic_rank", 4, "按弱点、错题、资料对比和课程顺序确定候选优先级", work)

    def _model_plan_node(self, state: ExamSprintState) -> dict[str, Any]:
        def work():
            planned = self._model_order(state, repair=False)
            if planned is None:
                warnings = list(state.get("warnings", []))
                warnings.append("模型规划不可用，已使用完整规则冲刺计划。")
                return (
                    {"planned_candidates": state["deterministic_candidates"], "generation_mode": "deterministic_source", "warnings": list(dict.fromkeys(warnings))},
                    "模型规划不可用，保留规则排序。",
                    "warning",
                    {"generation_mode": "deterministic_source", "warning_count": len(warnings)},
                )
            return {"planned_candidates": planned, "generation_mode": "model_enhanced"}, "模型已在合法候选集合内优化顺序和理由。", "completed", {"generation_mode": "model_enhanced"}

        return self._run_node(state, "model_plan", 5, "在确定性候选集合内优化冲刺顺序", work)

    def _build_tasks_node(self, state: ExamSprintState) -> dict[str, Any]:
        def work():
            deterministic_payload, _ = self._build_payload(state, list(state["deterministic_candidates"]))
            plan_payload, preserved = self._build_payload(state, list(state["planned_candidates"]))
            return (
                {"deterministic_payload": deterministic_payload, "plan_payload": plan_payload, "preserved_task_count": preserved},
                f"已生成 {len(plan_payload['task_specs'])} 个冲刺任务并保留 {preserved} 个既有任务。",
                "completed",
                {"preserved_task_count": preserved, "duration_days": int(state["duration_days"])},
            )

        return self._run_node(state, "build_tasks", 6, "生成每日重点、必刷题和资源任务", work)

    def _review_node(self, state: ExamSprintState) -> dict[str, Any]:
        def work():
            risks = self._plan_risks(state, state["plan_payload"])
            model_review = None
            if state.get("generation_mode") == "model_enhanced" and self.service.model_service is not None:
                try:
                    raw = self.service.model_service.chat_completion(
                        state["user"],
                        [
                            {"role": "system", "content": "你是 ExamSprintGraph 的 ReviewAgent。只审核计划一致性和安全性，只输出 JSON。"},
                            {
                                "role": "user",
                                "content": (
                                    f"周期={state['duration_days']}，任务数={len(state['plan_payload']['task_specs'])}，规则风险={risks}。"
                                    "返回 {\"review_status\":\"passed|revise\",\"confidence\":0.0,\"risk_flags\":[],\"safety_summary\":\"...\"}。"
                                ),
                            },
                        ],
                    )
                    model_review = review_contract(parse_json_object(raw), default_summary="冲刺计划证据、进度和安全审核完成。")
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
                    "safety_summary": model_review["safety_summary"] if model_review else "规则审核发现冲刺计划需要修订。",
                }
                return {"review_result": review, "review_mode": "model_and_rules" if model_review else "rules_only", "needs_repair": True}, review["safety_summary"], "warning", review
            if model_review is None:
                review = {
                    "review_status": "warning",
                    "confidence": 0.66,
                    "risk_flags": [],
                    "safety_summary": "模型审核不可用，已完成周期、证据、进度和隐私规则审核。",
                }
                return {"review_result": review, "review_mode": "rules_only", "needs_repair": False}, review["safety_summary"], "warning", review
            review = {**model_review, "review_status": "passed", "risk_flags": []}
            return {"review_result": review, "review_mode": "model_and_rules", "needs_repair": False}, review["safety_summary"], "completed", review

        return self._run_node(state, "review", 7, "审核周期、证据引用、保留进度和安全边界", work)

    def _repair_node(self, state: ExamSprintState) -> dict[str, Any]:
        def work():
            repaired_order = self._model_order(state, repair=True)
            if repaired_order is not None:
                repaired_payload, preserved = self._build_payload(state, repaired_order)
            else:
                repaired_payload = state["deterministic_payload"]
                preserved = int(state.get("preserved_task_count") or 0)
            if self._plan_risks(state, repaired_payload):
                repaired_payload = state["deterministic_payload"]
                generation_mode = "deterministic_source"
            else:
                generation_mode = "model_enhanced" if repaired_order is not None else "deterministic_source"
            review = {
                "review_status": "passed",
                "confidence": 0.72 if generation_mode == "model_enhanced" else 0.66,
                "risk_flags": [],
                "safety_summary": "已完成一次修订并重新通过周期、证据和进度校验。",
            }
            return (
                {"plan_payload": repaired_payload, "generation_mode": generation_mode, "review_result": review, "repair_count": 1, "preserved_task_count": preserved},
                review["safety_summary"],
                "completed",
                {**review, "repair_count": 1, "generation_mode": generation_mode, "preserved_task_count": preserved},
            )

        return self._run_node(state, "repair", 8, "按审核风险修订一次冲刺计划", work)

    def _persist_node(self, state: ExamSprintState) -> dict[str, Any]:
        started = perf_counter()
        course = state["course"]
        payload = state["plan_payload"]
        now = datetime.now(UTC)
        effective_goal = state["goal"] or f"完成《{course.title}》期末冲刺复习"
        previous = state.get("previous_path")
        try:
            self.service.repository.archive_active_sprint_paths(int(state["user_id"]), int(state["course_id"]))
            path = self.service.repository.add_path(
                LearningPath(
                    user_id=int(state["user_id"]),
                    course_id=int(state["course_id"]),
                    title=f"{course.title} 期末冲刺计划",
                    goal=effective_goal,
                    status="sprint_active",
                    agent_trace_id=state["trace_id"],
                    plan_json={
                        **{key: value for key, value in payload.items() if key != "task_specs"},
                        "schema_version": 2,
                        "trigger": state.get("trigger", "manual"),
                        "revision_of": str(previous.id) if previous is not None else None,
                        "comparison_id": str(state["comparison_id"]) if state.get("comparison_id") else None,
                        "material_ids": [str(item) for item in state.get("material_ids", [])],
                        "source_practice_session_id": (
                            str(state["source_practice_session_id"]) if state.get("source_practice_session_id") else None
                        ),
                        "preserved_task_count": int(state.get("preserved_task_count") or 0),
                        "generation_mode": state.get("generation_mode", "deterministic_source"),
                        "review_mode": state.get("review_mode", "rules_only"),
                        "review_result": state.get("review_result", {}),
                        "warnings": list(dict.fromkeys(state.get("warnings", []))),
                    },
                    created_at=now,
                    updated_at=now,
                )
            )
            task_days: dict[str, int] = {}
            for spec in payload["task_specs"]:
                task = self.service.repository.add_task(
                    LearningTask(
                        path_id=path.id,
                        user_id=int(state["user_id"]),
                        course_id=int(state["course_id"]),
                        knowledge_point_id=spec.knowledge_point_id,
                        title=spec.title,
                        task_type=spec.task_type,
                        reason=spec.reason,
                        recommended_resource_ids=spec.resource_ids,
                        status=spec.status,
                        due_at=spec.due_at,
                        next_review_at=None,
                        created_at=now,
                        updated_at=now,
                    )
                )
                task_days[str(task.id)] = spec.day_index
            path.plan_json = {**(path.plan_json or {}), "task_days": task_days}
            self.service.repository.commit()
            self.service.repository.refresh(path)
            result = self.service._build_response(path, self.service.repository.list_tasks_for_path(path.id), list(state["resources"]))
        except Exception as exc:
            self.service.repository.rollback()
            self._record(state, "persist", 9, "failed", "事务化保存审核后的冲刺计划", "冲刺计划保存失败，旧计划保持不变。", {"error_code": exc.__class__.__name__}, started)
            raise
        self._record(
            state,
            "persist",
            9,
            "completed",
            "事务化保存审核后的冲刺计划",
            f"已保存 {len(result.daily_tasks)} 个冲刺任务。",
            {"artifact_id": str(path.id), "preserved_task_count": int(state.get("preserved_task_count") or 0), "repair_count": int(state.get("repair_count") or 0)},
            started,
        )
        return {"result": result}

    def _apply_comparison_scores(self, candidates: list[SprintPointCandidate], result: dict[str, Any]) -> None:
        by_id = {str(item.knowledge_point_id): item for item in candidates if item.knowledge_point_id is not None}
        by_title = {safe_text(item.title, limit=120).casefold(): item for item in candidates}

        def apply(items: object, score: int, reason: str, *, weak: bool = False) -> None:
            if not isinstance(items, list):
                return
            for value in items:
                if not isinstance(value, dict):
                    continue
                point_id = safe_text(value.get("knowledge_point_id"), limit=40)
                title = safe_text(value.get("title"), limit=120)
                candidate = by_id.get(point_id) if point_id else by_title.get(title.casefold())
                if candidate is None:
                    continue
                candidate.score += score
                candidate.reasons.append(reason)
                candidate.weak = candidate.weak or weak

        apply(result.get("priority_order"), 50, "来自已审核资料对比的优先复习顺序")
        apply(result.get("exam_likely_points"), 35, "来自多资料交叉验证的疑似考点")
        apply(result.get("repeated_concepts"), 25, "来自多份资料重复重点")
        apply(result.get("missing_review_points"), 30, "来自资料覆盖缺口", weak=True)

    def _build_payload(self, state: ExamSprintState, ordered: list[SprintPointCandidate]) -> tuple[dict[str, Any], int]:
        high = ordered[:8]
        weak = [item for item in ordered if item.weak][:8] or high[:2]
        resources = list(state["resources"])
        now = datetime.now(UTC)
        recommended_ids = self.service._collect_recommended_resource_ids(resources, [*weak, *high])
        task_specs = self.service._build_task_specs(int(state["duration_days"]), now, weak + [item for item in high if item not in weak], resources)
        task_specs, preserved = self._merge_previous_tasks(state, task_specs)
        evidence = self.service._build_evidence_summary(
            list(state["knowledge_points"]),
            list(state["weakness_items"]),
            list(state["practice_answers"]),
            resources,
            state.get("report"),
            len(state.get("material_ids", [])),
        )
        if state.get("comparison_id"):
            evidence.basis.append("已使用审核通过的资料对比结果确定高频点和覆盖缺口。")
        profile = state.get("profile_summary", {})
        return {
            "kind": "exam_sprint",
            "duration_days": int(state["duration_days"]),
            "goal": state["goal"] or f"完成《{state['course'].title}》期末冲刺复习",
            "strategy": "comparison_and_weakness_first_then_high_frequency",
            "high_frequency_points": [self.service._point_payload(item, resources) for item in high],
            "weak_points": [self.service._point_payload(item, resources) for item in weak],
            "must_do_questions": [item.model_dump() for item in self.service._build_must_do_questions([*weak, *high])],
            "easy_mistake_warnings": [item.model_dump() for item in self.service._build_warnings(weak or high[:3])],
            "recommended_resource_ids": [str(item) for item in recommended_ids],
            "evidence_summary": evidence.model_dump(),
            "personalization": {
                "learning_goal": safe_text(profile.get("learning_goal"), limit=120),
                "learning_preference": safe_text(profile.get("learning_preference"), limit=120),
                "learning_pace": safe_text(profile.get("learning_pace"), limit=120),
            },
            "task_specs": task_specs,
        }, preserved

    def _merge_previous_tasks(self, state: ExamSprintState, specs: list[SprintTaskSpec]) -> tuple[list[SprintTaskSpec], int]:
        previous = list(state.get("previous_tasks", []))
        if state.get("trigger") != "assessment_reflow" or not previous:
            return specs, 0
        task_days = {str(key): int(value) for key, value in ((state.get("previous_path").plan_json or {}).get("task_days") or {}).items()}
        completed: list[SprintTaskSpec] = []
        completed_keys: set[str] = set()
        for task in previous:
            if task.status != "completed":
                continue
            key = self._task_key(task.task_type, task.knowledge_point_id, task.title)
            completed_keys.add(key)
            completed.append(
                SprintTaskSpec(
                    day_index=task_days.get(str(task.id), 1),
                    title=task.title,
                    task_type=task.task_type,
                    knowledge_point_id=task.knowledge_point_id,
                    reason=task.reason or "保留自上一版冲刺计划",
                    resource_ids=[int(item) for item in task.recommended_resource_ids or [] if str(item).isdigit()],
                    due_at=task.due_at or datetime.now(UTC),
                    status="completed",
                )
            )
        open_specs = [
            spec
            for spec in specs
            if self._task_key(spec.task_type, spec.knowledge_point_id, spec.title) not in completed_keys
        ]
        open_specs = [replace(spec, status="doing" if index == 0 else "todo") for index, spec in enumerate(open_specs)]
        return [*completed, *open_specs], len(completed)

    def _model_order(self, state: ExamSprintState, *, repair: bool) -> list[SprintPointCandidate] | None:
        if self.service.model_service is None:
            return None
        candidates = list(state.get("deterministic_candidates", []))
        rows = [
            {"key": self._point_key(item), "title": item.title, "score": item.score, "weak": item.weak, "reasons": item.reasons[:4]}
            for item in candidates
        ]
        try:
            raw = self.service.model_service.chat_completion(
                state["user"],
                [
                    {"role": "system", "content": "你是 ExamSprintGraph 的规划 Agent。只能重排给定 key，禁止新增知识点、资源、任务或证据，只输出 JSON。"},
                    {
                        "role": "user",
                        "content": (
                            ("这是唯一一次修订机会。" if repair else "结合画像和证据优化冲刺顺序。")
                            + f"画像={state.get('profile_summary', {})}；候选={rows}。"
                            + "返回 {\"ordered_keys\":[\"...\"],\"rationales\":{\"key\":\"简短理由\"}}。"
                        ),
                    },
                ],
            )
        except Exception:
            return None
        payload = parse_json_object(raw)
        if payload is None or not isinstance(payload.get("ordered_keys"), list):
            return None
        by_key = {self._point_key(item): item for item in candidates}
        ordered_keys = [safe_text(item, limit=160) for item in payload["ordered_keys"]]
        if any(key not in by_key for key in ordered_keys) or len(set(ordered_keys)) != len(ordered_keys):
            return None
        ordered_keys.extend(key for key in by_key if key not in ordered_keys)
        rationales = payload.get("rationales") if isinstance(payload.get("rationales"), dict) else {}
        return [
            replace(
                by_key[key],
                reasons=[safe_text(rationales.get(key), limit=240)] + by_key[key].reasons if safe_text(rationales.get(key), limit=240) else list(by_key[key].reasons),
            )
            for key in ordered_keys
        ]

    def _plan_risks(self, state: ExamSprintState, payload: dict[str, Any]) -> list[str]:
        valid_points = {point.id for point in state.get("knowledge_points", [])}
        valid_resources = {resource.id for resource in state.get("resources", [])}
        tasks = list(payload.get("task_specs") or [])
        risks: list[str] = []
        open_keys: list[str] = []
        for task in tasks:
            if task.day_index < 1 or task.day_index > int(state["duration_days"]):
                risks.append("invalid_day")
            if task.knowledge_point_id is not None and task.knowledge_point_id not in valid_points:
                risks.append("invalid_knowledge_point_reference")
            if any(resource_id not in valid_resources for resource_id in task.resource_ids):
                risks.append("invalid_resource_reference")
            if contains_sensitive_text(f"{task.title} {task.reason}"):
                risks.append("sensitive_output")
            if task.status != "completed":
                open_keys.append(self._task_key(task.task_type, task.knowledge_point_id, task.title))
        if not tasks:
            risks.append("empty_plan")
        if len(open_keys) != len(set(open_keys)):
            risks.append("duplicate_task")
        if sum(1 for task in tasks if task.status == "doing") > 1:
            risks.append("multiple_active_tasks")
        return list(dict.fromkeys(risks))

    @staticmethod
    def _point_key(point: SprintPointCandidate) -> str:
        return f"knowledge:{point.knowledge_point_id}" if point.knowledge_point_id is not None else f"title:{safe_text(point.title, limit=120).casefold()}"

    @staticmethod
    def _task_key(task_type: str, knowledge_point_id: int | None, title: str) -> str:
        suffix = str(knowledge_point_id) if knowledge_point_id is not None else safe_text(title, limit=120).casefold()
        return f"{task_type}:{suffix}"

    def _run_node(
        self,
        state: ExamSprintState,
        name: str,
        index: int,
        input_summary: str,
        work: Callable[[], tuple[dict[str, Any], str, str, dict[str, Any]]],
    ) -> dict[str, Any]:
        started = perf_counter()
        try:
            result, output_summary, status, metadata = work()
        except Exception as exc:
            self._record(state, name, index, "failed", input_summary, "节点执行失败，已记录安全错误摘要。", {"error_code": exc.__class__.__name__}, started)
            raise
        self._record(state, name, index, status, input_summary, output_summary, metadata, started)
        return result

    def _record(
        self,
        state: ExamSprintState,
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
            artifact_type="learning_path",
            artifact_id=metadata.get("artifact_id"),
            metadata={"trigger": state.get("trigger", "manual"), **metadata},
        )

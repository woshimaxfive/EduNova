from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from math import ceil
import re
from time import perf_counter
from typing import Any, Callable, TypedDict

from langgraph.graph import END, START, StateGraph

from backend.app.agents.learning_review import contains_sensitive_text, parse_json_object, review_contract, safe_text
from backend.app.api.errors import make_trace_id
from backend.app.models import LearningPath, LearningTask, User
from backend.app.schemas.profiles import normalize_profile_json
from backend.app.services.paths import PathReplanResult, PathService, PlannedTask
from backend.app.services.model_execution import execution_context_for_state, model_execution_scope


class PathPlanningState(TypedDict, total=False):
    trace_id: str
    user: User
    user_id: int
    course_id: int
    duration_days: int
    goal: str
    trigger: str
    assessment_session_id: int | None
    previous_path: LearningPath | None
    previous_tasks: list[LearningTask]
    course: Any
    profile_summary: dict[str, Any]
    knowledge_points: list[Any]
    weaknesses: list[Any]
    resources: list[Any]
    deterministic_tasks: list[PlannedTask]
    planned_tasks: list[PlannedTask]
    generation_mode: str
    review_mode: str
    review_result: dict[str, Any]
    needs_repair: bool
    repair_count: int
    warnings: list[str]
    preserved_task_count: int
    daily_task_capacity: int
    path: LearningPath
    detail: Any


class PathPlanningGraphRunner:
    workflow = "path_planning"

    def __init__(self, service: PathService) -> None:
        self.service = service
        self.graph = self._build_graph()

    def run(
        self,
        *,
        user: User,
        course_id: int,
        duration_days: int,
        goal: str,
        trigger: str,
        assessment_session_id: int | None = None,
        previous_path: LearningPath | None = None,
    ) -> PathReplanResult:
        trace_id = make_trace_id()
        state: PathPlanningState = {
            "trace_id": trace_id,
            "user": user,
            "user_id": user.id,
            "course_id": course_id,
            "duration_days": duration_days,
            "goal": goal,
            "trigger": trigger,
            "assessment_session_id": assessment_session_id,
            "previous_path": previous_path,
            "previous_tasks": [],
            "warnings": [],
            "repair_count": 0,
        }
        with model_execution_scope(execution_context_for_state(state, workflow=self.workflow, purpose=trigger)):
            result = self.graph.invoke(state)
        return PathReplanResult(
            status="replanned" if trigger == "assessment" else "generated",
            trace_id=trace_id,
            detail=result.get("detail"),
            preserved_task_count=int(result.get("preserved_task_count") or 0),
        )

    def _build_graph(self):
        graph = StateGraph(PathPlanningState)
        graph.add_node("profile", self._profile_node)
        graph.add_node("collect_evidence", self._collect_evidence_node)
        graph.add_node("deterministic_rank", self._deterministic_rank_node)
        graph.add_node("model_plan", self._model_plan_node)
        graph.add_node("review", self._review_node)
        graph.add_node("repair", self._repair_node)
        graph.add_node("persist", self._persist_node)
        graph.add_edge(START, "profile")
        graph.add_edge("profile", "collect_evidence")
        graph.add_edge("collect_evidence", "deterministic_rank")
        graph.add_edge("deterministic_rank", "model_plan")
        graph.add_edge("model_plan", "review")
        graph.add_conditional_edges("review", self._review_route, {"repair": "repair", "persist": "persist"})
        graph.add_edge("repair", "persist")
        graph.add_edge("persist", END)
        return graph.compile()

    def _profile_node(self, state: PathPlanningState) -> dict[str, Any]:
        def work() -> tuple[dict[str, Any], str, str, dict[str, Any]]:
            profile = self.service.repository.get_profile(int(state["user_id"]))
            summary = normalize_profile_json(profile.profile_json if profile is not None else None)
            return {"profile_summary": summary}, "已读取安全画像摘要。", "completed", {}

        return self._run_node(state, "profile", 1, "读取用户级画像摘要", work)

    def _collect_evidence_node(self, state: PathPlanningState) -> dict[str, Any]:
        def work() -> tuple[dict[str, Any], str, str, dict[str, Any]]:
            course = self.service._require_course(state["user"], int(state["course_id"]))
            points = self.service.repository.list_knowledge_points(course.id)
            weaknesses = self.service.repository.list_weakness_review_items(int(state["user_id"]), course.id)
            resources = self.service.repository.list_generated_resources(int(state["user_id"]), course.id)
            previous = state.get("previous_path") or self.service.repository.get_active_path(int(state["user_id"]), course.id)
            previous_tasks = self.service.repository.list_tasks_for_path(previous.id) if previous is not None else []
            active_count = sum(1 for item in weaknesses if item.status in {"confirmed", "reviewing"})
            return (
                {
                    "course": course,
                    "knowledge_points": points,
                    "weaknesses": weaknesses,
                    "resources": resources,
                    "previous_path": previous,
                    "previous_tasks": previous_tasks,
                },
                f"已聚合 {len(points)} 个知识点、{active_count} 个确认弱点和 {len(resources)} 个资源。",
                "completed",
                {"weakness_count": active_count, "resource_count": len(resources)},
            )

        return self._run_node(state, "collect_evidence", 2, "聚合路径规划证据", work)

    def _deterministic_rank_node(self, state: PathPlanningState) -> dict[str, Any]:
        def work() -> tuple[dict[str, Any], str, str, dict[str, Any]]:
            active_weaknesses = [item for item in state.get("weaknesses", []) if item.status in {"reviewing", "confirmed"}]
            base = self.service._build_planned_tasks(
                list(state.get("knowledge_points", [])),
                active_weaknesses,
                list(state.get("resources", [])),
            )
            base, daily_capacity = self._personalize_tasks(base, state)
            base = [replace(task, status="doing" if index == 0 else "todo") for index, task in enumerate(base)]
            planned = base
            preserved = 0
            if state.get("trigger") == "assessment":
                planned, preserved = self._merge_previous_progress(list(state.get("previous_tasks", [])), base)
            return (
                {
                    "deterministic_tasks": planned,
                    "planned_tasks": planned,
                    "preserved_task_count": preserved,
                    "generation_mode": "deterministic_source",
                    "daily_task_capacity": daily_capacity,
                },
                f"规则排序生成 {len(planned)} 个任务，并保留 {preserved} 个既有任务。",
                "completed",
                {"preserved_task_count": preserved, "daily_task_capacity": daily_capacity},
            )

        return self._run_node(state, "deterministic_rank", 3, "按弱点、进度和课程顺序生成可信任务底稿", work)

    def _model_plan_node(self, state: PathPlanningState) -> dict[str, Any]:
        def work() -> tuple[dict[str, Any], str, str, dict[str, Any]]:
            ordered = self._model_order(state, repair=False)
            if ordered is None:
                warning = "模型不可用或排序输出无效，保留确定性路径。"
                return (
                    {"planned_tasks": list(state.get("deterministic_tasks", [])), "warnings": [*state.get("warnings", []), warning]},
                    warning,
                    "warning",
                    {"model_used": False, "generation_mode": "deterministic_source"},
                )
            return (
                {"planned_tasks": ordered, "generation_mode": "model_enhanced"},
                "模型已在合法任务集合内优化顺序与理由。",
                "completed",
                {"model_used": True, "generation_mode": "model_enhanced"},
            )

        return self._run_node(state, "model_plan", 4, "在确定性任务集合内优化学习顺序", work)

    def _review_node(self, state: PathPlanningState) -> dict[str, Any]:
        def work() -> tuple[dict[str, Any], str, str, dict[str, Any]]:
            risks = self._task_risks(state)
            model_review = None
            if state.get("generation_mode") == "model_enhanced" and self.service.model_service is not None:
                try:
                    raw = self.service.model_service.chat_completion(
                        state["user"],
                        [
                            {"role": "system", "content": "你是 PathPlanningGraph 的 ReviewAgent。只输出 JSON，不得更改任务 ID。"},
                            {
                                "role": "user",
                                "content": (
                                    "审核任务顺序是否与确认弱点、课程顺序和资源证据一致。"
                                    f"任务数={len(state.get('planned_tasks', []))}，弱点数="
                                    f"{sum(1 for item in state.get('weaknesses', []) if item.status in {'confirmed', 'reviewing'})}。"
                                    "返回 {\"review_status\":\"passed|revise\",\"confidence\":0.0,"
                                    "\"risk_flags\":[],\"safety_summary\":\"\"}。"
                                ),
                            },
                        ],
                    )
                    model_review = review_contract(parse_json_object(raw), default_summary="已完成路径证据与安全审核。")
                except Exception:
                    model_review = None
            if model_review and model_review["review_status"] == "revise":
                risks.extend(str(item) for item in model_review["risk_flags"])
            risks = list(dict.fromkeys(risks))
            if risks:
                review = {
                    "review_status": "revise",
                    "confidence": model_review["confidence"] if model_review else 0.45,
                    "risk_flags": risks,
                    "safety_summary": model_review["safety_summary"] if model_review else "规则审核发现路径任务需要修订。",
                }
                return {"review_result": review, "needs_repair": True, "review_mode": "model_and_rules" if model_review else "rules_only"}, "路径需要修订。", "warning", review
            if model_review is None:
                review = {
                    "review_status": "warning",
                    "confidence": 0.6,
                    "risk_flags": [],
                    "safety_summary": "模型审核不可用，已完成任务 ID、进度、资源和隐私规则审核。",
                }
                return {"review_result": review, "needs_repair": False, "review_mode": "rules_only"}, review["safety_summary"], "warning", review
            review = {**model_review, "review_status": "passed", "risk_flags": []}
            return {"review_result": review, "needs_repair": False, "review_mode": "model_and_rules"}, "ReviewAgent 审核通过。", "completed", review

        return self._run_node(state, "review", 5, "审核路径证据、进度和安全边界", work)

    @staticmethod
    def _review_route(state: PathPlanningState) -> str:
        return "repair" if state.get("needs_repair") else "persist"

    def _repair_node(self, state: PathPlanningState) -> dict[str, Any]:
        def work() -> tuple[dict[str, Any], str, str, dict[str, Any]]:
            repaired = self._model_order(state, repair=True)
            if repaired is None:
                repaired = list(state.get("deterministic_tasks", []))
                mode = "deterministic_source"
            else:
                mode = "model_enhanced"
            repaired_state = {**state, "planned_tasks": repaired}
            if self._task_risks(repaired_state):
                repaired = list(state.get("deterministic_tasks", []))
                mode = "deterministic_source"
            review = {
                "review_status": "passed",
                "confidence": 0.72 if mode == "model_enhanced" else 0.64,
                "risk_flags": [],
                "safety_summary": "已完成一次修订，并通过确定性任务与证据校验。",
            }
            return (
                {"planned_tasks": repaired, "generation_mode": mode, "review_result": review, "repair_count": 1},
                review["safety_summary"],
                "completed",
                {**review, "repair_count": 1, "generation_mode": mode},
            )

        return self._run_node(state, "repair", 6, "按审核风险修订一次路径", work)

    def _persist_node(self, state: PathPlanningState) -> dict[str, Any]:
        started = perf_counter()
        course = state["course"]
        profile = state.get("profile_summary", {})
        goal = safe_text(state.get("goal"), limit=500) or safe_text(profile.get("learning_goal"), limit=500)
        effective_goal = goal or f"完成《{course.title}》阶段复习"
        points = list(state.get("knowledge_points", []))
        weaknesses = list(state.get("weaknesses", []))
        resources = list(state.get("resources", []))
        active_weaknesses = [item for item in weaknesses if item.status in {"confirmed", "reviewing"}]
        previous = state.get("previous_path")
        try:
            self.service.repository.archive_active_paths(int(state["user_id"]), int(state["course_id"]))
            path = self.service.repository.add_path(
                LearningPath(
                    user_id=int(state["user_id"]),
                    course_id=int(state["course_id"]),
                    title=f"{course.title} 学习路径",
                    goal=effective_goal,
                    status="active",
                    agent_trace_id=state["trace_id"],
                    plan_json={
                        "schema_version": 2,
                        "duration_days": int(state["duration_days"]),
                        "strategy": "reviewing_first_then_confirmed_then_uncovered",
                        "trigger": state.get("trigger", "manual"),
                        "revision_of": str(previous.id) if previous is not None else None,
                        "assessment_session_id": str(state["assessment_session_id"]) if state.get("assessment_session_id") else None,
                        "preserved_task_count": int(state.get("preserved_task_count") or 0),
                        "generation_mode": state.get("generation_mode", "deterministic_source"),
                        "review_mode": state.get("review_mode", "rules_only"),
                        "review_result": state.get("review_result", {}),
                        "personalization": {
                            "daily_task_capacity": int(state.get("daily_task_capacity") or 2),
                            "learning_preference": safe_text(profile.get("learning_preference"), limit=80),
                            "knowledge_foundation": safe_text(profile.get("knowledge_foundation"), limit=80),
                        },
                        "source_counts": {
                            "knowledge_points": len(points),
                            "confirmed_or_reviewing_weaknesses": len(active_weaknesses),
                            "pending_weaknesses": sum(1 for item in weaknesses if item.status == "pending"),
                            "resources": len(resources),
                        },
                        "basis": [
                            "基于课程知识点和练习证据生成。",
                            "优先安排已确认或复习中的薄弱点。",
                            "模型只能在合法任务集合内优化顺序，规则负责最终校验。",
                        ],
                    },
                )
            )
            now = datetime.now(UTC)
            open_index = 0
            for planned in state.get("planned_tasks", []):
                due_at = planned.due_at
                if planned.status != "completed":
                    open_index += 1
                    capacity = max(1, int(state.get("daily_task_capacity") or 2))
                    due_at = now + timedelta(days=min(ceil(open_index / capacity), int(state["duration_days"])))
                self.service.repository.add_task(
                    LearningTask(
                        path_id=path.id,
                        user_id=int(state["user_id"]),
                        course_id=int(state["course_id"]),
                        knowledge_point_id=planned.knowledge_point_id,
                        title=planned.title,
                        task_type=planned.task_type,
                        reason=planned.reason,
                        recommended_resource_ids=planned.resource_ids,
                        status=planned.status,
                        due_at=due_at,
                        next_review_at=planned.next_review_at,
                    )
                )
            self.service.repository.commit()
            self.service.repository.refresh(path)
            detail = self.service._build_detail(
                state["user"],
                course,
                path,
                self.service.repository.list_tasks_for_path(path.id),
                resources,
                points,
                weaknesses,
            )
        except Exception as exc:
            self.service.repository.rollback()
            self._record(
                state,
                agent_name="persist",
                step_index=7,
                status="failed",
                input_summary="事务化保存审核通过的学习路径",
                output_summary="路径保存失败，旧 active 路径保持不变。",
                metadata={"error_code": exc.__class__.__name__},
                started_at=started,
            )
            raise
        self._record(
            state,
            agent_name="persist",
            step_index=7,
            status="completed",
            input_summary="事务化保存审核通过的学习路径",
            output_summary=f"已保存 {len(detail.tasks)} 个路径任务。",
            metadata={
                "artifact_id": str(path.id),
                "preserved_task_count": int(state.get("preserved_task_count") or 0),
                "repair_count": int(state.get("repair_count") or 0),
            },
            started_at=started,
        )
        return {"path": path, "detail": detail}

    def _model_order(self, state: PathPlanningState, *, repair: bool) -> list[PlannedTask] | None:
        if self.service.model_service is None:
            return None
        tasks = list(state.get("deterministic_tasks", []))
        completed = [task for task in tasks if task.status == "completed"]
        open_tasks = [task for task in tasks if task.status != "completed"]
        if not open_tasks:
            return tasks
        candidates = [
            {
                "task_key": self._task_key(task),
                "title": task.title,
                "task_type": task.task_type,
                "reason": task.reason,
                "resource_ids": task.resource_ids,
            }
            for task in open_tasks
        ]
        system = "你是 PathPlanningGraph 的规划 Agent。只能重排给定 task_key，禁止新增知识点、资源或任务。只输出 JSON。"
        instruction = "这是审核后的修订机会。" if repair else "根据确认弱点、课程顺序和资源证据优化任务顺序。"
        try:
            raw = self.service.model_service.chat_completion(
                state["user"],
                [
                    {"role": "system", "content": system},
                    {
                        "role": "user",
                        "content": (
                            f"{instruction} 画像目标={safe_text(state.get('profile_summary', {}).get('learning_goal'), limit=120)}；"
                            f"学习基础={safe_text(state.get('profile_summary', {}).get('knowledge_foundation'), limit=120)}；"
                            f"学习偏好={safe_text(state.get('profile_summary', {}).get('learning_preference'), limit=120)}。"
                            f"候选任务={candidates}。"
                            "返回 {\"ordered_task_keys\":[\"...\"],\"rationales\":{\"task_key\":\"简短理由\"}}。"
                        ),
                    },
                ],
            )
        except Exception:
            return None
        payload = parse_json_object(raw)
        if payload is None or not isinstance(payload.get("ordered_task_keys"), list):
            return None
        by_key = {self._task_key(task): task for task in open_tasks}
        ordered_keys = [safe_text(item, limit=160) for item in payload["ordered_task_keys"]]
        if any(key not in by_key for key in ordered_keys) or len(set(ordered_keys)) != len(ordered_keys):
            return None
        ordered_keys.extend(key for key in by_key if key not in ordered_keys)
        rationales = payload.get("rationales") if isinstance(payload.get("rationales"), dict) else {}
        ordered: list[PlannedTask] = []
        for index, key in enumerate(ordered_keys):
            task = by_key[key]
            rationale = safe_text(rationales.get(key), limit=240)
            ordered.append(replace(task, reason=rationale or task.reason, status="doing" if index == 0 else "todo"))
        return [*completed, *ordered]

    def _task_risks(self, state: PathPlanningState) -> list[str]:
        tasks = list(state.get("planned_tasks", []))
        if not tasks:
            return ["empty_plan"]
        valid_resources = {resource.id for resource in state.get("resources", [])}
        risks: list[str] = []
        open_keys: list[str] = []
        for task in tasks:
            if contains_sensitive_text(f"{task.title} {task.reason}"):
                risks.append("sensitive_output")
            if any(resource_id not in valid_resources for resource_id in task.resource_ids):
                risks.append("invalid_resource_reference")
            if task.status != "completed":
                open_keys.append(self._task_key(task))
        if len(open_keys) != len(set(open_keys)):
            risks.append("duplicate_task")
        if sum(1 for task in tasks if task.status == "doing") > 1:
            risks.append("multiple_active_tasks")
        return list(dict.fromkeys(risks))

    @classmethod
    def _merge_previous_progress(
        cls,
        previous_tasks: list[LearningTask],
        base_tasks: list[PlannedTask],
    ) -> tuple[list[PlannedTask], int]:
        completed: list[PlannedTask] = []
        retained_open: list[PlannedTask] = []
        used: set[str] = set()
        for task in previous_tasks:
            planned = PlannedTask(
                title=task.title,
                task_type=task.task_type,
                knowledge_point_id=task.knowledge_point_id,
                reason=task.reason or "保留自上一版路径",
                resource_ids=[int(item) for item in (task.recommended_resource_ids or []) if str(item).isdigit()],
                next_review_at=task.next_review_at,
                status="completed" if task.status == "completed" else "todo",
                due_at=task.due_at,
            )
            key = cls._task_key(planned)
            if task.status == "completed":
                completed.append(planned)
                used.add(key)
            elif task.status == "doing":
                retained_open.append(planned)

        merged_open: list[PlannedTask] = []
        for task in [item for item in base_tasks if item.task_type == "review"]:
            key = cls._task_key(task)
            if key not in used:
                merged_open.append(task)
                used.add(key)
        retained_count = 0
        for task in retained_open:
            key = cls._task_key(task)
            if key not in used:
                merged_open.append(task)
                used.add(key)
                retained_count += 1
        for task in [item for item in base_tasks if item.task_type != "review"]:
            key = cls._task_key(task)
            if key not in used:
                merged_open.append(task)
                used.add(key)
        merged_open = [replace(task, status="doing" if index == 0 else "todo") for index, task in enumerate(merged_open)]
        return [*completed, *merged_open], len(completed) + retained_count

    def _personalize_tasks(self, tasks: list[PlannedTask], state: PathPlanningState) -> tuple[list[PlannedTask], int]:
        profile = state.get("profile_summary", {})
        pace = safe_text(profile.get("learning_pace"), limit=80)
        minutes_match = re.search(r"(\d+)", pace)
        minutes = int(minutes_match.group(1)) if minutes_match else 45
        daily_capacity = 1 if minutes <= 30 else 3 if minutes >= 60 else 2
        preference = safe_text(profile.get("learning_preference"), limit=80)
        preferred_types: list[str] = []
        if any(word in preference for word in ("图", "视觉", "动画")):
            preferred_types = ["mindmap", "animation", "slide"]
        elif "代码" in preference:
            preferred_types = ["code"]
        elif any(word in preference for word in ("练习", "题")):
            preferred_types = ["quiz"]
        elif preference:
            preferred_types = ["doc"]
        resources = {resource.id: resource for resource in state.get("resources", [])}
        personalized: list[PlannedTask] = []
        for task in tasks:
            resource_ids = sorted(
                task.resource_ids,
                key=lambda resource_id: (
                    0
                    if resources.get(resource_id) is not None
                    and resources[resource_id].resource_type in preferred_types
                    else 1,
                    resource_id,
                ),
            )
            reason = task.reason
            if preference:
                reason = f"{reason}；结合学习偏好：{preference}"
            personalized.append(replace(task, resource_ids=resource_ids, reason=reason))
        return personalized, daily_capacity

    @staticmethod
    def _task_key(task: PlannedTask) -> str:
        if task.knowledge_point_id is not None:
            return f"knowledge:{task.knowledge_point_id}"
        return f"title:{safe_text(task.title, limit=120).casefold()}"

    def _run_node(
        self,
        state: PathPlanningState,
        agent_name: str,
        step_index: int,
        input_summary: str,
        work: Callable[[], tuple[dict[str, Any], str, str, dict[str, Any]]],
    ) -> dict[str, Any]:
        started = perf_counter()
        try:
            with model_execution_scope(execution_context_for_state(state, workflow=self.workflow, node_name=agent_name)):
                result, output_summary, status, metadata = work()
        except Exception as exc:
            self._record(
                state,
                agent_name=agent_name,
                step_index=step_index,
                status="failed",
                input_summary=input_summary,
                output_summary="节点执行失败，已记录安全错误摘要。",
                metadata={"error_code": exc.__class__.__name__},
                started_at=started,
            )
            raise
        self._record(
            state,
            agent_name=agent_name,
            step_index=step_index,
            status=status,
            input_summary=input_summary,
            output_summary=output_summary,
            metadata=metadata,
            started_at=started,
        )
        return result

    def _record(
        self,
        state: PathPlanningState,
        *,
        agent_name: str,
        step_index: int,
        status: str,
        input_summary: str,
        output_summary: str,
        metadata: dict[str, Any],
        started_at: float,
    ) -> None:
        recorder = self.service.trace_recorder
        if recorder is None:
            return
        recorder.record(
            trace_id=state["trace_id"],
            user_id=int(state["user_id"]),
            course_id=int(state["course_id"]),
            agent_name=agent_name,
            step_index=step_index,
            status=status,
            input_summary=input_summary,
            output_summary=output_summary,
            duration_ms=max(0, int((perf_counter() - started_at) * 1000)),
            workflow=self.workflow,
            artifact_type="learning_path",
            artifact_id=metadata.get("artifact_id"),
            metadata={"operation": state.get("trigger", "manual"), **metadata},
        )

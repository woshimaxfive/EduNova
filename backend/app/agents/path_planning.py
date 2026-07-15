from __future__ import annotations

import json
from dataclasses import replace
from time import perf_counter
from typing import Any, Callable, TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.agents.learning_review import contains_sensitive_text, parse_json_object, safe_text
from backend.app.api.errors import make_trace_id
from backend.app.models import GeneratedResource, LearningPath, LearningTask, User
from backend.app.schemas.profiles import normalize_profile_json
from backend.app.services.paths import PathReplanResult, PathService, PlannedTask
from backend.app.services.model_execution import execution_context_for_state, model_execution_scope
from backend.app.services.learner_context import context_service_from_repository
from backend.app.services.content_locale import china_first_content_policy
from backend.app.services.resource_feedback import (
    RESOURCE_TYPES,
    deterministic_bundle_types,
    rank_resource_types,
)


class PathPlanningChoice(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_key: str = Field(min_length=1, max_length=160)
    rationale: str = Field(min_length=1, max_length=240)
    bundle_types: list[str] = Field(min_length=2, max_length=4)
    resource_ids: list[int] = Field(default_factory=list, max_length=6)
    teaching_strategy: str = Field(min_length=1, max_length=80)
    difficulty: str = Field(pattern="^(easy|medium|hard)$")
    used_profile_factor_codes: list[str] = Field(default_factory=list, max_length=8)

    @field_validator("bundle_types", "resource_ids", "used_profile_factor_codes")
    @classmethod
    def unique_values(cls, value: list[Any]) -> list[Any]:
        if len(value) != len(set(value)):
            raise ValueError("列表项目不能重复。")
        return value


class PathPlanningDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    priority_tasks: list[PathPlanningChoice] = Field(min_length=1, max_length=8)


class PathPlanningState(TypedDict, total=False):
    trace_id: str
    user: User
    user_id: int
    course_id: int
    goal: str
    trigger: str
    assessment_session_id: int | None
    previous_path: LearningPath | None
    previous_tasks: list[LearningTask]
    course: Any
    profile_summary: dict[str, Any]
    learner_context: Any
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
    path: LearningPath
    detail: Any
    job_context: Any


class PathPlanningGraphRunner:
    workflow = "path_planning"
    job_progress = {
        "profile": (12, "已读取可信学习画像"),
        "collect_evidence": (25, "已聚合课程学习证据"),
        "deterministic_rank": (38, "已生成安全路径底稿"),
        "model_plan": (65, "已完成个性化路径规划"),
        "review": (82, "已审核路径结构与权限"),
        "repair": (92, "已恢复安全路径方案"),
        "persist": (100, "学习路径已更新"),
    }

    def __init__(self, service: PathService) -> None:
        self.service = service
        self.graph = self._build_graph()

    def run(
        self,
        *,
        user: User,
        course_id: int,
        trigger: str,
        goal: str = "",
        assessment_session_id: int | None = None,
        previous_path: LearningPath | None = None,
        trace_id: str | None = None,
        job_context: Any | None = None,
    ) -> PathReplanResult:
        effective_trace_id = trace_id or make_trace_id()
        state: PathPlanningState = {
            "trace_id": effective_trace_id,
            "user": user,
            "user_id": user.id,
            "course_id": course_id,
            "goal": goal,
            "trigger": trigger,
            "assessment_session_id": assessment_session_id,
            "previous_path": previous_path,
            "previous_tasks": [],
            "warnings": [],
            "repair_count": 0,
            "job_context": job_context,
        }
        with model_execution_scope(execution_context_for_state(state, workflow=self.workflow, purpose=trigger)):
            result = self.graph.invoke(state)
        return PathReplanResult(
            status="replanned" if trigger == "assessment" else "generated",
            trace_id=effective_trace_id,
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
            context_service = context_service_from_repository(self.service.repository)
            if context_service is not None:
                learner_context = context_service.course_context(int(state["user_id"]), int(state["course_id"]))
                return (
                    {"profile_summary": learner_context.prompt_summary(), "learner_context": learner_context},
                    "已读取可信总画像与当前课程学习状态。",
                    "completed",
                    learner_context.trace_metadata(),
                )
            profile = self.service.repository.get_profile(int(state["user_id"]))
            summary = normalize_profile_json(profile.profile_json if profile is not None else None)
            return {"profile_summary": summary}, "已读取安全画像摘要。", "completed", {"profile_context_used": bool(profile)}

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
            base = self._personalize_tasks(base, state)
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
                },
                f"规则排序生成 {len(planned)} 个任务，并保留 {preserved} 个既有任务。",
                "completed",
                {"preserved_task_count": preserved},
            )

        return self._run_node(state, "deterministic_rank", 3, "按弱点、进度和课程顺序生成可信任务底稿", work)

    def _model_plan_node(self, state: PathPlanningState) -> dict[str, Any]:
        def work() -> tuple[dict[str, Any], str, str, dict[str, Any]]:
            ordered = self._model_order(state)
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
            if risks:
                review = {
                    "review_status": "revise",
                    "confidence": 0.95,
                    "risk_flags": risks,
                    "safety_summary": "确定性审核发现路径任务需要恢复为安全底稿。",
                }
                return {"review_result": review, "needs_repair": True, "review_mode": "rules_only"}, "路径需要恢复安全底稿。", "warning", review
            review = {
                "review_status": "passed",
                "confidence": 1.0,
                "risk_flags": [],
                "safety_summary": "已完成任务、权限、资源、画像因素和隐私确定性审核。",
            }
            return {"review_result": review, "needs_repair": False, "review_mode": "rules_only"}, review["safety_summary"], "completed", review

        return self._run_node(state, "review", 5, "审核路径证据、进度和安全边界", work)

    @staticmethod
    def _review_route(state: PathPlanningState) -> str:
        return "repair" if state.get("needs_repair") else "persist"

    def _repair_node(self, state: PathPlanningState) -> dict[str, Any]:
        def work() -> tuple[dict[str, Any], str, str, dict[str, Any]]:
            repaired = list(state.get("deterministic_tasks", []))
            mode = "deterministic_source"
            review = {
                "review_status": "passed",
                "confidence": 1.0,
                "risk_flags": [],
                "safety_summary": "模型方案未通过确定性审核，已恢复安全默认路径。",
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
        context = state.get("job_context")
        if context is not None:
            context.before_node("persist")
        course = state["course"]
        profile = state.get("profile_summary", {})
        goal = safe_text(state.get("goal"), limit=500) or safe_text(profile.get("learning_goal"), limit=500)
        effective_goal = goal or f"完成《{course.title}》学习"
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
                        "schema_version": 5,
                        "path_mode": "ordered",
                        "strategy": "reviewing_first_then_confirmed_then_uncovered",
                        "trigger": state.get("trigger", "manual"),
                        "revision_of": str(previous.id) if previous is not None else None,
                        "assessment_session_id": str(state["assessment_session_id"]) if state.get("assessment_session_id") else None,
                        "preserved_task_count": int(state.get("preserved_task_count") or 0),
                        "generation_mode": state.get("generation_mode", "deterministic_source"),
                        "review_mode": state.get("review_mode", "rules_only"),
                        "review_result": state.get("review_result", {}),
                        "profile_applied_version": (
                            state["learner_context"].global_context.profile_applied_version
                            if state.get("learner_context") is not None
                            else 0
                        ),
                        "course_context_hash": (
                            state["learner_context"].context_hash
                            if state.get("learner_context") is not None
                            else "legacy"
                        ),
                        **china_first_content_policy.metadata(),
                        "personalization": {
                            code: safe_text(profile.get(code), limit=80)
                            for code in self._trusted_factor_codes(state)
                            if code in {"major_background", "learning_preference", "knowledge_foundation"}
                            and safe_text(profile.get(code), limit=80)
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
            for planned in state.get("planned_tasks", []):
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
                        learning_bundle_json=self._learning_bundle(planned, resources, profile),
                        status=planned.status,
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
            if context is not None:
                context.after_node(name="persist", label="学习路径保存失败", progress_percent=96, status="failed")
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
        if context is not None:
            context.after_node(name="persist", label=self.job_progress["persist"][1], progress_percent=100, status="completed")
        return {"path": path, "detail": detail}

    def _model_order(self, state: PathPlanningState) -> list[PlannedTask] | None:
        if self.service.model_service is None:
            return None
        tasks = list(state.get("deterministic_tasks", []))
        completed = [task for task in tasks if task.status == "completed"]
        open_tasks = [task for task in tasks if task.status != "completed"]
        if not open_tasks:
            return tasks
        candidate_tasks = open_tasks[:24]
        candidates = [
            {
                "task_key": self._task_key(task),
                "title": task.title,
                "task_type": task.task_type,
                "reason": task.reason,
                "resource_ids": task.resource_ids,
                "bundle_types": list(task.bundle_types),
            }
            for task in candidate_tasks
        ]
        resources = {
            resource.id: {
                "id": resource.id,
                "resource_type": resource.resource_type,
                "title": safe_text(resource.title, limit=120),
                "status": resource.status,
            }
            for resource in state.get("resources", [])
            if resource.status == "completed"
        }
        allowed_factor_codes = self._trusted_factor_codes(state)
        profile = state.get("profile_summary", {})
        trusted_profile = {
            code: profile.get(code)
            for code in allowed_factor_codes
            if code in profile and profile.get(code) not in (None, "", [], {})
        }
        try:
            raw = self.service.model_service.chat_completion(
                state["user"],
                [
                    {
                        "role": "system",
                        "content": (
                            "你是 PathPlanningGraph 的规划 Agent。只能从候选任务中选择最多8个近期优先任务，"
                            "不能新增知识点、资源、画像因素或任务。只输出合法 JSON，不输出解释或思维链。"
                            + china_first_content_policy.prompt_instruction()
                        ),
                    },
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "trusted_profile": trusted_profile,
                                "allowed_profile_factor_codes": sorted(allowed_factor_codes),
                                "course_state": {
                                    "active_weaknesses": profile.get("active_weaknesses", []),
                                    "mastery_average": profile.get("mastery_average"),
                                    "current_task_title": profile.get("current_task_title"),
                                    "resource_feedback": profile.get("resource_feedback", {}),
                                },
                                "candidate_tasks": candidates,
                                "available_resources": list(resources.values()),
                                "allowed_bundle_types": list(RESOURCE_TYPES),
                                "output": {
                                    "priority_tasks": [
                                        {
                                            "task_key": "候选task_key",
                                            "rationale": "面向学生的简短安排理由",
                                            "bundle_types": ["doc", "quiz"],
                                            "resource_ids": [],
                                            "teaching_strategy": "简短教学策略",
                                            "difficulty": "easy|medium|hard",
                                            "used_profile_factor_codes": [],
                                        }
                                    ]
                                },
                            },
                            ensure_ascii=False,
                            separators=(",", ":"),
                        )[:12000],
                    },
                ],
            )
        except Exception:
            return None
        payload = parse_json_object(raw, PathPlanningDecision)
        if payload is None:
            return None
        by_key = {self._task_key(task): task for task in candidate_tasks}
        choices = list(payload.get("priority_tasks", []))
        selected_keys = [safe_text(item.get("task_key"), limit=160) for item in choices]
        if any(key not in by_key for key in selected_keys) or len(selected_keys) != len(set(selected_keys)):
            return None
        prioritized: list[PlannedTask] = []
        for index, choice in enumerate(choices):
            key = selected_keys[index]
            task = by_key[key]
            selected_types = tuple(str(item) for item in choice.get("bundle_types", []))
            selected_resources = [int(item) for item in choice.get("resource_ids", [])]
            used_factors = tuple(str(item) for item in choice.get("used_profile_factor_codes", []))
            if any(item not in RESOURCE_TYPES for item in selected_types):
                return None
            if any(item not in task.resource_ids or item not in resources for item in selected_resources):
                return None
            if any(item not in allowed_factor_codes for item in used_factors):
                return None
            ranked_resources = [*selected_resources, *(item for item in task.resource_ids if item not in selected_resources)]
            prioritized.append(
                replace(
                    task,
                    reason=safe_text(choice.get("rationale"), limit=240),
                    resource_ids=ranked_resources,
                    bundle_types=selected_types,
                    teaching_strategy=safe_text(choice.get("teaching_strategy"), limit=80),
                    difficulty=str(choice.get("difficulty") or "medium"),
                    used_profile_factor_codes=used_factors,
                    generation_mode="model_enhanced",
                    status="doing" if index == 0 else "todo",
                )
            )
        remaining = [
            replace(task, status="todo")
            for task in open_tasks
            if self._task_key(task) not in set(selected_keys)
        ]
        return [*completed, *prioritized, *remaining]

    def _task_risks(self, state: PathPlanningState) -> list[str]:
        tasks = list(state.get("planned_tasks", []))
        if not tasks:
            return ["empty_plan"]
        valid_resources = {resource.id for resource in state.get("resources", [])}
        valid_factor_codes = self._trusted_factor_codes(state)
        risks: list[str] = []
        open_keys: list[str] = []
        for task in tasks:
            if contains_sensitive_text(f"{task.title} {task.reason}"):
                risks.append("sensitive_output")
            if any(resource_id not in valid_resources for resource_id in task.resource_ids):
                risks.append("invalid_resource_reference")
            if not (2 <= len(task.bundle_types) <= 4) or any(item not in RESOURCE_TYPES for item in task.bundle_types):
                risks.append("invalid_bundle_types")
            if len(task.bundle_types) != len(set(task.bundle_types)):
                risks.append("duplicate_bundle_type")
            if task.difficulty not in {"easy", "medium", "hard"}:
                risks.append("invalid_difficulty")
            if not safe_text(task.teaching_strategy, limit=80):
                risks.append("missing_teaching_strategy")
            if any(code not in valid_factor_codes for code in task.used_profile_factor_codes):
                risks.append("invalid_profile_factor")
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
            previous_bundle = task.learning_bundle_json if isinstance(task.learning_bundle_json, dict) else {}
            previous_items = previous_bundle.get("items") if isinstance(previous_bundle.get("items"), list) else []
            previous_types = tuple(
                str(item.get("resource_type"))
                for item in previous_items
                if isinstance(item, dict) and str(item.get("resource_type")) in RESOURCE_TYPES
            )
            planned = PlannedTask(
                title=task.title,
                task_type=task.task_type,
                knowledge_point_id=task.knowledge_point_id,
                reason=task.reason or "保留自上一版路径",
                resource_ids=[int(item) for item in (task.recommended_resource_ids or []) if str(item).isdigit()],
                bundle_types=previous_types or deterministic_bundle_types(None),
                teaching_strategy=safe_text(previous_bundle.get("teaching_strategy"), limit=80) or "safe_default",
                difficulty=(
                    str(previous_bundle.get("difficulty"))
                    if str(previous_bundle.get("difficulty")) in {"easy", "medium", "hard"}
                    else "medium"
                ),
                used_profile_factor_codes=tuple(
                    str(item)
                    for item in previous_bundle.get("used_profile_factor_codes", [])
                    if str(item).strip()
                ),
                generation_mode=str(previous_bundle.get("generation_mode") or "legacy"),
                status="completed" if task.status == "completed" else "todo",
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

    def _personalize_tasks(self, tasks: list[PlannedTask], state: PathPlanningState) -> list[PlannedTask]:
        profile = state.get("profile_summary", {})
        feedback = profile.get("resource_feedback") if isinstance(profile.get("resource_feedback"), dict) else {}
        fallback_types = deterministic_bundle_types(feedback)
        personalized: list[PlannedTask] = []
        for task in tasks:
            personalized.append(
                replace(
                    task,
                    resource_ids=sorted(task.resource_ids),
                    bundle_types=fallback_types,
                    teaching_strategy="safe_default",
                    difficulty="medium",
                    used_profile_factor_codes=(),
                    generation_mode="deterministic_source",
                )
            )
        return personalized

    @staticmethod
    def _learning_bundle(
        task: PlannedTask,
        resources: list[GeneratedResource],
        profile: dict[str, Any],
    ) -> dict[str, Any]:
        resources_by_id = {resource.id: resource for resource in resources if resource.status == "completed"}
        feedback = profile.get("resource_feedback") if isinstance(profile.get("resource_feedback"), dict) else {}
        selected_types = task.bundle_types or deterministic_bundle_types(feedback)
        selected_types = tuple(rank_resource_types(selected_types, feedback))
        role_labels = {
            "doc": "建立证据型概念框架",
            "mindmap": "梳理概念关系与复习线索",
            "quiz": "检查本知识点是否掌握",
            "code": "通过可运行实验验证结论",
            "slide": "按讲授顺序完成结构化复述",
            "animation": "观察状态与过程变化",
            "video": "使用外部视频形成直观理解",
        }
        preferred_resources = [resources_by_id[item] for item in task.resource_ids if item in resources_by_id]
        items: list[dict[str, Any]] = []
        for resource_type in selected_types:
            available = next(
                (item for item in preferred_resources if item.resource_type == resource_type),
                next((item for item in resources_by_id.values() if item.resource_type == resource_type), None),
            )
            items.append(
                {
                    "resource_type": resource_type,
                    "resource_id": available.id if available is not None else None,
                    "role": role_labels[resource_type],
                    "status": "available" if available is not None else "recommended",
                }
            )
        model_enhanced = task.generation_mode == "model_enhanced"
        return {
            "strategy": task.teaching_strategy if model_enhanced else "安全默认组合",
            "teaching_strategy": task.teaching_strategy,
            "difficulty": task.difficulty if task.difficulty in {"easy", "medium", "hard"} else "medium",
            "used_profile_factor_codes": list(task.used_profile_factor_codes),
            "generation_mode": task.generation_mode,
            "rationale": (
                task.reason
                if model_enhanced
                else "模型规划未生效，使用课程证据、学习进度和资源反馈生成安全默认组合。"
            ),
            "items": items,
        }

    @staticmethod
    def _trusted_factor_codes(state: PathPlanningState) -> set[str]:
        learner_context = state.get("learner_context")
        if learner_context is None:
            return set()
        metadata = learner_context.trace_metadata()
        values = (metadata.get("personalization_factors") or []) if isinstance(metadata, dict) else []
        return {str(item) for item in values if str(item).strip()}

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
        context = state.get("job_context")
        if context is not None:
            context.before_node(agent_name)
        try:
            with model_execution_scope(execution_context_for_state(state, workflow=self.workflow, node_name=agent_name)):
                result, output_summary, status, metadata = work()
        except Exception as exc:
            if context is not None:
                progress, _ = self.job_progress.get(agent_name, (0, agent_name))
                context.after_node(
                    name=agent_name,
                    label="路径规划节点执行失败",
                    progress_percent=max(0, progress - 1),
                    status="failed",
                )
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
        if context is not None:
            progress, label = self.job_progress.get(agent_name, (0, output_summary))
            context.after_node(
                name=agent_name,
                label=label,
                progress_percent=progress,
                status=status,
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

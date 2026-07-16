from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
import json
import re
from time import perf_counter
from typing import Any, Callable, TypedDict

from langgraph.graph import END, START, StateGraph

from backend.app.agents.learning_review import contains_sensitive_text, parse_json_object, review_contract, safe_string_list, safe_text
from backend.app.api.errors import make_trace_id
from backend.app.models import AssessmentReport, PracticeAnswer, PracticeSession, User
from backend.app.schemas.reports import ReportEnvelope, report_to_api
from backend.app.services.reports import ReportNotFoundError, ReportService
from backend.app.services.model_execution import execution_context_for_state, model_execution_scope
from backend.app.services.learner_context import context_service_from_repository
from backend.app.services.content_locale import china_first_content_policy


REPORT_PROMPT_VERSION = "report-v3.2"
REPORT_REVIEW_PROMPT_VERSION = "report-review-v3.2-embedded"
OPTIONAL_GENERATION_TIMEOUT_SECONDS = 40.0


class ReportState(TypedDict, total=False):
    trace_id: str
    job_context: Any
    user: User
    user_id: int
    course_id: int
    practice_session_id: int | None
    course: Any
    practices: list[PracticeSession]
    latest_practice: PracticeSession | None
    answers_by_session: dict[int, list[PracticeAnswer]]
    points: list[Any]
    weaknesses: list[Any]
    active_path: Any
    path_tasks: list[Any]
    resources: list[Any]
    learner_context: Any
    score: int | None
    deterministic_report: dict[str, Any]
    report_json: dict[str, Any]
    generation_mode: str
    review_mode: str
    review_result: dict[str, Any]
    generation_review: dict[str, Any] | None
    needs_repair: bool
    repair_count: int
    report: AssessmentReport
    detail: ReportEnvelope


class ReportGraphRunner:
    workflow = "report"

    def __init__(self, service: ReportService) -> None:
        self.service = service
        self.graph = self._build_graph()

    def run(
        self,
        *,
        user: User,
        course_id: int,
        practice_session_id: int | None,
        trace_id: str | None = None,
        job_context: Any = None,
    ) -> ReportEnvelope:
        self.service._require_course(user, course_id)
        if practice_session_id is None and self.service.repository.get_latest_completed_practice_session(user.id, course_id) is None:
            existing = self.service.repository.get_latest_report(user.id, course_id)
            if existing is not None:
                return report_to_api(existing, self.service._report_freshness(user.id, existing))
        state: ReportState = {
            "trace_id": trace_id or make_trace_id(),
            "job_context": job_context,
            "user": user,
            "user_id": user.id,
            "course_id": course_id,
            "practice_session_id": practice_session_id,
            "repair_count": 0,
        }
        with model_execution_scope(execution_context_for_state(state, workflow=self.workflow)):
            return self.graph.invoke(state)["detail"]

    def _build_graph(self):
        graph = StateGraph(ReportState)
        graph.add_node("collect_practice", self._collect_practice_node)
        graph.add_node("collect_mastery", self._collect_mastery_node)
        graph.add_node("aggregate_evidence", self._aggregate_node)
        graph.add_node("generate_narrative", self._generate_node)
        graph.add_node("review", self._review_node)
        graph.add_node("repair", self._repair_node)
        graph.add_node("persist", self._persist_node)
        graph.add_edge(START, "collect_practice")
        graph.add_edge("collect_practice", "collect_mastery")
        graph.add_edge("collect_mastery", "aggregate_evidence")
        graph.add_edge("aggregate_evidence", "generate_narrative")
        graph.add_edge("generate_narrative", "review")
        graph.add_conditional_edges("review", self._review_route, {"repair": "repair", "persist": "persist"})
        graph.add_edge("repair", "persist")
        graph.add_edge("persist", END)
        return graph.compile()

    def _collect_practice_node(self, state: ReportState) -> dict[str, Any]:
        def work() -> tuple[dict[str, Any], str, str, dict[str, Any]]:
            course = self.service._require_course(state["user"], int(state["course_id"]))
            requested_id = state.get("practice_session_id")
            if requested_id is not None:
                practice = self.service.repository.get_practice_session_for_user(int(state["user_id"]), requested_id)
                if practice is None or practice.course_id != course.id:
                    raise ReportNotFoundError("练习不存在或无权访问。")
                practices = [practice]
            else:
                list_recent = getattr(self.service.repository, "list_recent_completed_practice_sessions", None)
                practices = list_recent(int(state["user_id"]), course.id, 5) if callable(list_recent) else []
                if not practices:
                    latest = self.service.repository.get_latest_completed_practice_session(int(state["user_id"]), course.id)
                    practices = [latest] if latest is not None else []
            latest_practice = practices[0] if practices else None
            answers_by_session = {practice.id: self.service.repository.list_answers_for_session(practice.id) for practice in practices}
            return {"course": course, "practices": practices, "latest_practice": latest_practice, "answers_by_session": answers_by_session}, f"已聚合最近 {len(practices)} 次已完成练习。", "completed", {"practice_count": len(practices)}

        return self._run_node(state, "collect_practice", 1, "读取最近练习与安全作答证据", work)

    def _collect_mastery_node(self, state: ReportState) -> dict[str, Any]:
        def work() -> tuple[dict[str, Any], str, str, dict[str, Any]]:
            course_id = int(state["course_id"])
            user_id = int(state["user_id"])
            points = self.service.repository.list_knowledge_points(course_id)
            weaknesses = self.service.repository.list_weakness_review_items(user_id, course_id)
            get_path = getattr(self.service.repository, "get_active_path", None)
            path = get_path(user_id, course_id) if callable(get_path) else None
            list_tasks = getattr(self.service.repository, "list_tasks_for_path", None)
            tasks = list_tasks(path.id) if path is not None and callable(list_tasks) else []
            list_resources = getattr(self.service.repository, "list_generated_resources", None)
            resources = list_resources(user_id, course_id) if callable(list_resources) else []
            context_service = context_service_from_repository(self.service.repository)
            learner_context = context_service.course_context(user_id, course_id) if context_service is not None else None
            active_weaknesses = sum(1 for item in weaknesses if item.status in {"confirmed", "reviewing"})
            return (
                {"points": points, "weaknesses": weaknesses, "active_path": path, "path_tasks": tasks, "resources": resources, "learner_context": learner_context},
                f"已聚合 {len(points)} 个知识点、{active_weaknesses} 个活跃弱点和 {len(tasks)} 个路径任务。",
                "completed",
                {
                    "weakness_count": active_weaknesses,
                    "resource_count": len(resources),
                    **(learner_context.trace_metadata() if learner_context is not None else {"profile_context_used": False}),
                },
            )

        return self._run_node(state, "collect_mastery", 2, "聚合掌握度、弱点、路径与资源", work)

    def _aggregate_node(self, state: ReportState) -> dict[str, Any]:
        def work() -> tuple[dict[str, Any], str, str, dict[str, Any]]:
            latest = state.get("latest_practice")
            answers = state.get("answers_by_session", {}).get(latest.id, []) if latest is not None else []
            score = int(latest.score) if latest is not None and latest.score is not None else self.service._score_from_answers(answers)
            report = self.service._build_report(
                state["course"],
                list(state.get("points", [])),
                list(state.get("weaknesses", [])),
                answers,
                score,
            )
            scores = [int(item.score) for item in reversed(state.get("practices", [])) if item.score is not None]
            if len(scores) >= 2:
                delta = scores[-1] - scores[0]
                direction = "improved" if delta > 0 else ("declined" if delta < 0 else "stable")
            else:
                delta = 0
                direction = "insufficient"
            answered_count = sum(
                1
                for rows in state.get("answers_by_session", {}).values()
                for answer in rows
                if answer.answer_text is not None
            )
            all_answered = [
                answer
                for rows in state.get("answers_by_session", {}).values()
                for answer in rows
                if answer.answer_text is not None
            ]
            correct_count = sum(1 for answer in all_answered if answer.is_correct is True)
            assessed_point_ids = {
                str((answer.question_json or {}).get("knowledge_point_id"))
                for answer in all_answered
                if (answer.question_json or {}).get("knowledge_point_id") is not None
            }
            completed_task_count = sum(1 for task in state.get("path_tasks", []) if task.status == "completed")
            report["trend"] = {
                "direction": direction,
                "score_delta": delta,
                "sessions_compared": len(scores),
                "scores": scores,
            }
            report["evidence_summary"] = {
                "practice_count": len(state.get("practices", [])),
                "answer_count": answered_count,
                "correct_answer_count": correct_count,
                "assessed_knowledge_point_count": len(assessed_point_ids),
                "completed_path_task_count": completed_task_count,
                "weakness_count": sum(1 for item in state.get("weaknesses", []) if item.status in {"confirmed", "reviewing"}),
                "path_status": state.get("active_path").status if state.get("active_path") is not None else "not_started",
                "resource_count": len(state.get("resources", [])),
            }
            report["deterministic_statistics"] = {
                "practice_session_count": len(state.get("practices", [])),
                "answered_question_count": answered_count,
                "correct_answer_count": correct_count,
                "assessed_knowledge_point_count": len(assessed_point_ids),
                "completed_path_task_count": completed_task_count,
            }
            report["quality"] = {
                "prompt_version": REPORT_PROMPT_VERSION,
                "review_prompt_version": REPORT_REVIEW_PROMPT_VERSION,
                "statistics_locked": True,
                **china_first_content_policy.metadata(),
            }
            learner_context = state.get("learner_context")
            if learner_context is not None:
                report["resource_usage_summary"] = learner_context.resource_feedback_summary
                report["profile_changes"] = [
                    f"报告应用画像版本 {learner_context.global_context.profile_applied_version}，"
                    f"参考 {len(learner_context.global_context.trusted_dimensions)} 个可信维度。"
                ]
            return {"score": score, "deterministic_report": report, "report_json": report}, f"已形成 {len(report.get('evidence_refs', []))} 条报告证据，趋势为 {direction}。", "completed", {"practice_count": len(scores), "trend_direction": direction}

        return self._run_node(state, "aggregate_evidence", 3, "计算不可篡改的分数、掌握度与趋势", work)

    def _generate_node(self, state: ReportState) -> dict[str, Any]:
        def work() -> tuple[dict[str, Any], str, str, dict[str, Any]]:
            generated = self._model_narrative(state)
            if generated is None:
                return {"report_json": dict(state["deterministic_report"]), "generation_mode": "deterministic_source"}, "模型不可用或叙事结构无效，保留规则报告。", "warning", {"model_used": False, "generation_mode": "deterministic_source"}
            narrative, generation_review = generated
            report = {**state["deterministic_report"], **narrative}
            return (
                {"report_json": report, "generation_mode": "model_enhanced", "generation_review": generation_review},
                "模型已生成基于证据的报告总结，并在同一次调用中完成安全自审。",
                "completed",
                {"model_used": True, "generation_mode": "model_enhanced", "embedded_review": generation_review is not None, "model_call_budget": 1},
            )

        return self._run_node(state, "generate_narrative", 4, "生成不改写统计数据的报告叙事", work)

    def _review_node(self, state: ReportState) -> dict[str, Any]:
        def work() -> tuple[dict[str, Any], str, str, dict[str, Any]]:
            risks = self._report_risks(state)
            model_review = state.get("generation_review") if state.get("generation_mode") == "model_enhanced" else None
            if model_review and model_review["review_status"] == "revise":
                risks.extend(str(item) for item in model_review["risk_flags"] or ["model_review_requested_revision"])
            risks = list(dict.fromkeys(risks))
            if risks:
                review = {"review_status": "revise", "confidence": model_review["confidence"] if model_review else 0.42, "risk_flags": risks, "safety_summary": model_review["safety_summary"] if model_review else "规则审核发现报告需要修订。"}
                return {"review_result": review, "review_mode": "embedded_model_and_rules" if model_review else "rules_only", "needs_repair": True}, "报告需要修订。", "warning", review
            if model_review is None:
                review = {"review_status": "warning", "confidence": 0.62, "risk_flags": [], "safety_summary": "模型审核不可用，已完成统计、证据引用和隐私规则审核。"}
                return {"review_result": review, "review_mode": "rules_only", "needs_repair": False}, review["safety_summary"], "warning", review
            review = {**model_review, "review_status": "passed", "risk_flags": []}
            return {"review_result": review, "review_mode": "embedded_model_and_rules", "needs_repair": False}, "模型自审与确定性规则审核通过。", "completed", review

        return self._run_node(state, "review", 5, "审核报告统计、趋势、来源和隐私", work)

    @staticmethod
    def _review_route(state: ReportState) -> str:
        return "repair" if state.get("needs_repair") else "persist"

    def _repair_node(self, state: ReportState) -> dict[str, Any]:
        def work() -> tuple[dict[str, Any], str, str, dict[str, Any]]:
            report = dict(state["deterministic_report"])
            review = {
                "review_status": "warning",
                "confidence": 0.72,
                "risk_flags": safe_string_list((state.get("review_result") or {}).get("risk_flags"), limit=8, item_limit=60),
                "safety_summary": "模型叙事未通过完整审核，已直接保留数字和证据锁定的确定性报告。",
            }
            return (
                {
                    "report_json": report,
                    "generation_mode": "deterministic_source",
                    "review_mode": "rules_only",
                    "review_result": review,
                    "repair_count": 1,
                },
                review["safety_summary"],
                "warning",
                {**review, "repair_count": 1, "model_call_budget": 0},
            )

        return self._run_node(state, "repair", 6, "按审核风险回退到确定性报告", work)

    def _persist_node(self, state: ReportState) -> dict[str, Any]:
        started = perf_counter()
        latest = state.get("latest_practice")
        learner_context = state.get("learner_context")
        report_json = {
            **state["report_json"],
            "review_result": state.get("review_result", {}),
            "quality": {
                **dict(state.get("report_json", {}).get("quality", {})),
                "generation_mode": state.get("generation_mode", "deterministic_source"),
                "review_mode": state.get("review_mode", "rules_only"),
                "repair_count": int(state.get("repair_count", 0)),
            },
            "profile_applied_version": (
                learner_context.global_context.profile_applied_version if learner_context is not None else 0
            ),
            "course_context_hash": learner_context.context_hash if learner_context is not None else "legacy",
        }
        report = AssessmentReport(
            user_id=int(state["user_id"]),
            course_id=int(state["course_id"]),
            practice_session_id=latest.id if latest is not None else None,
            agent_trace_id=state["trace_id"],
            report_json=report_json,
            score=Decimal(str(state["score"])) if state.get("score") is not None else None,
            created_at=datetime.now(UTC),
        )
        try:
            self.service.repository.add_assessment_report(report)
            self.service.repository.commit()
            self.service.repository.refresh(report)
            detail = report_to_api(report, self.service._report_freshness(int(state["user_id"]), report))
        except Exception as exc:
            self.service.repository.rollback()
            self._record_failure(state, "persist", 7, "保存审核通过的学习报告", exc, started)
            raise
        self._record(state, "persist", 7, "completed", "保存审核通过的学习报告", "学习报告已保存。", {"artifact_id": str(report.id), "repair_count": int(state.get("repair_count") or 0)}, started)
        return {"report": report, "detail": detail}

    def _model_narrative(
        self,
        state: ReportState,
    ) -> tuple[dict[str, Any], dict[str, Any] | None] | None:
        if self.service.model_service is None:
            return None
        deterministic = state["deterministic_report"]
        evidence = {
            "score": state.get("score"),
            "mastery_update": deterministic.get("mastery_update"),
            "trend": deterministic.get("trend"),
            "weakness_titles": [safe_text(item.get("title"), limit=120) for item in deterministic.get("weakness_list", [])],
            "evidence_summary": deterministic.get("evidence_summary"),
            "deterministic_statistics": deterministic.get("deterministic_statistics"),
        }
        learner_context = state.get("learner_context")
        personalization = learner_context.prompt_summary() if learner_context is not None else {}
        instruction = "根据结构化证据生成简洁学习总结和 2 到 4 条下一步建议。"
        try:
            messages = [
                    {"role": "system", "content": "你是 ReportGraph 报告 Agent。不得修改数字、编造练习或输出隐私，只输出 JSON。" + china_first_content_policy.prompt_instruction()},
                    {
                        "role": "user",
                        "content": (
                            f"协议={REPORT_PROMPT_VERSION}，内嵌审核协议={REPORT_REVIEW_PROMPT_VERSION}。{instruction} "
                            f"可信课程画像提示={personalization}。不可变证据={json.dumps(evidence, ensure_ascii=False)}。"
                            "summary 和 next_step_suggestions 不得出现阿拉伯数字、中文数字、百分比、次数或时长；"
                            "所有统计数字由确定性指标区单独展示，叙事只解释趋势、薄弱点和下一步策略。"
                            "生成后在同一次响应中自审数字一致性、证据边界、隐私和是否编造学习记录；"
                            "发现风险时 review_status 必须为 revise。"
                            "返回 {\"summary\":\"\",\"next_step_suggestions\":[],"
                            "\"quality_review\":{\"review_status\":\"passed|revise\",\"confidence\":0.0,"
                            "\"risk_flags\":[],\"safety_summary\":\"\"}}。"
                        ),
                    },
                ]
            completion_with_timeout = getattr(self.service.model_service, "chat_completion_with_timeout", None)
            raw = (
                completion_with_timeout(
                    state["user"],
                    messages,
                    timeout_seconds=OPTIONAL_GENERATION_TIMEOUT_SECONDS,
                    max_attempts=1,
                )
                if callable(completion_with_timeout)
                else self.service.model_service.chat_completion(state["user"], messages)
            )
        except Exception:
            return None
        payload = parse_json_object(raw)
        if payload is None:
            return None
        summary = safe_text(payload.get("summary"), limit=600)
        suggestions = safe_string_list(payload.get("next_step_suggestions"), limit=4, item_limit=240)
        if not summary or not suggestions or contains_sensitive_text(payload):
            return None
        quality_review = review_contract(
            payload.get("quality_review") if isinstance(payload.get("quality_review"), dict) else None,
            default_summary="已完成报告数字、证据和隐私自审。",
        )
        return {"summary": summary, "next_step_suggestions": suggestions}, quality_review

    @staticmethod
    def _report_risks(state: ReportState) -> list[str]:
        report = state.get("report_json", {})
        deterministic = state.get("deterministic_report", {})
        risks: list[str] = []
        for key in ("mastery_update", "weakness_list", "evidence_refs", "trend", "evidence_summary", "deterministic_statistics", "quality"):
            if report.get(key) != deterministic.get(key):
                risks.append("deterministic_evidence_changed")
        if contains_sensitive_text(report.get("summary")) or contains_sensitive_text(report.get("next_step_suggestions")):
            risks.append("sensitive_output")
        allowed_numbers = {
            int(value)
            for value in [
                state.get("score"),
                deterministic.get("trend", {}).get("score_delta"),
                *deterministic.get("trend", {}).get("scores", []),
                *deterministic.get("deterministic_statistics", {}).values(),
            ]
            if isinstance(value, (int, float))
        }
        narrative_text = " ".join([
            safe_text(report.get("summary"), limit=600),
            *safe_string_list(report.get("next_step_suggestions"), limit=4, item_limit=240),
        ])
        narrative_numbers = {int(value) for value in re.findall(r"(?<![A-Za-z])\d{1,4}(?![A-Za-z])", narrative_text)}
        if narrative_numbers - allowed_numbers:
            risks.append("numeric_inconsistency")
        valid_answer_ids = {
            str(answer.id)
            for rows in state.get("answers_by_session", {}).values()
            for answer in rows
        }
        for ref in report.get("evidence_refs", []):
            if str(ref.get("practice_answer_id")) not in valid_answer_ids:
                risks.append("invalid_evidence_reference")
        return list(dict.fromkeys(risks))

    def _run_node(
        self,
        state: ReportState,
        agent_name: str,
        step_index: int,
        input_summary: str,
        work: Callable[[], tuple[dict[str, Any], str, str, dict[str, Any]]],
    ) -> dict[str, Any]:
        started = perf_counter()
        job_context = state.get("job_context")
        if job_context is not None:
            job_context.before_node(agent_name, input_summary)
        try:
            with model_execution_scope(execution_context_for_state(state, workflow=self.workflow, node_name=agent_name)):
                result, output_summary, status, metadata = work()
        except Exception as exc:
            self._record_failure(state, agent_name, step_index, input_summary, exc, started)
            if job_context is not None:
                job_context.after_node(
                    name=agent_name,
                    label="学习报告节点失败",
                    progress_percent=min(95, step_index * 13),
                    status="failed",
                )
            raise
        self._record(state, agent_name, step_index, status, input_summary, output_summary, metadata, started)
        if job_context is not None:
            job_context.after_node(
                name=agent_name,
                label=input_summary,
                progress_percent=min(95, step_index * 13),
                status=status,
            )
        return result

    def _record_failure(self, state: ReportState, agent_name: str, step_index: int, input_summary: str, exc: Exception, started: float) -> None:
        self._record(state, agent_name, step_index, "failed", input_summary, "节点执行失败，已记录安全错误摘要。", {"error_code": exc.__class__.__name__}, started)

    def _record(
        self,
        state: ReportState,
        agent_name: str,
        step_index: int,
        status: str,
        input_summary: str,
        output_summary: str,
        metadata: dict[str, Any],
        started: float,
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
            duration_ms=max(0, int((perf_counter() - started) * 1000)),
            workflow=self.workflow,
            artifact_type="assessment_report",
            artifact_id=metadata.get("artifact_id"),
            metadata=metadata,
        )

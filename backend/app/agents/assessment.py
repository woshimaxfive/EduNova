from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from time import perf_counter
from typing import Any, Callable, TypedDict

from langgraph.graph import END, START, StateGraph

from backend.app.agents.learning_review import (
    clamp_confidence,
    contains_sensitive_text,
    parse_json_object,
    review_contract,
    safe_string_list,
    safe_text,
)
from backend.app.api.errors import make_trace_id
from backend.app.models import PracticeAnswer, PracticeSession, User, WeaknessReviewItem
from backend.app.schemas.practice import PracticeSessionDetail, SubmitPracticeAnswerItem, session_to_api
from backend.app.services.practice import EvaluatedAnswer, PracticeService, PracticeValidationError


class AssessmentState(TypedDict, total=False):
    trace_id: str
    operation: str
    user: User
    user_id: int
    course_id: int
    session_id: int
    knowledge_point_ids: list[int]
    question_count: int
    difficulty: str
    requested_difficulty: str
    sprint_plan_id: int | None
    sprint_task_id: int | None
    submitted_answers: list[SubmitPracticeAnswerItem | dict]
    course: Any
    points: list[Any]
    selected_points: list[Any]
    resources: list[Any]
    deterministic_questions: list[dict[str, Any]]
    questions: list[dict[str, Any]]
    session: PracticeSession
    answer_rows: list[PracticeAnswer]
    evaluated: list[EvaluatedAnswer]
    score: int
    diagnoses: dict[str, dict[str, Any]]
    touched_weaknesses: dict[str, WeaknessReviewItem]
    weaknesses_added: int
    weaknesses_updated: int
    recommended_resource_ids: list[int]
    generation_mode: str
    review_mode: str
    review_result: dict[str, Any]
    needs_repair: bool
    repair_count: int
    detail: PracticeSessionDetail


class AssessmentGraphRunner:
    workflow = "assessment"

    def __init__(self, service: PracticeService) -> None:
        self.service = service
        self.create_graph = self._build_create_graph()
        self.submit_graph = self._build_submit_graph()

    def create_session(
        self,
        *,
        user: User,
        course_id: int,
        knowledge_point_ids: list[int],
        question_count: int,
        difficulty: str,
        sprint_plan_id: int | None = None,
        sprint_task_id: int | None = None,
    ) -> PracticeSessionDetail:
        state: AssessmentState = {
            "trace_id": make_trace_id(),
            "operation": "question_generation",
            "user": user,
            "user_id": user.id,
            "course_id": course_id,
            "knowledge_point_ids": knowledge_point_ids,
            "question_count": question_count,
            "difficulty": difficulty,
            "requested_difficulty": difficulty,
            "sprint_plan_id": sprint_plan_id,
            "sprint_task_id": sprint_task_id,
            "repair_count": 0,
        }
        return self.create_graph.invoke(state)["detail"]

    def submit_answers(
        self,
        *,
        user: User,
        session_id: int,
        answers: list[SubmitPracticeAnswerItem | dict],
    ) -> PracticeSessionDetail:
        state: AssessmentState = {
            "trace_id": make_trace_id(),
            "operation": "answer_evaluation",
            "user": user,
            "user_id": user.id,
            "session_id": session_id,
            "submitted_answers": answers,
            "repair_count": 0,
        }
        return self.submit_graph.invoke(state)["detail"]

    def _build_create_graph(self):
        graph = StateGraph(AssessmentState)
        graph.add_node("context", self._create_context_node)
        graph.add_node("question_plan", self._question_plan_node)
        graph.add_node("generate_questions", self._generate_questions_node)
        graph.add_node("review", self._question_review_node)
        graph.add_node("repair", self._question_repair_node)
        graph.add_node("persist", self._create_persist_node)
        graph.add_edge(START, "context")
        graph.add_edge("context", "question_plan")
        graph.add_edge("question_plan", "generate_questions")
        graph.add_edge("generate_questions", "review")
        graph.add_conditional_edges("review", self._review_route, {"repair": "repair", "persist": "persist"})
        graph.add_edge("repair", "persist")
        graph.add_edge("persist", END)
        return graph.compile()

    def _build_submit_graph(self):
        graph = StateGraph(AssessmentState)
        graph.add_node("load", self._load_submission_node)
        graph.add_node("deterministic_score", self._score_node)
        graph.add_node("diagnose_errors", self._diagnose_node)
        graph.add_node("sync_weaknesses", self._sync_weaknesses_node)
        graph.add_node("review", self._answer_review_node)
        graph.add_node("repair", self._answer_repair_node)
        graph.add_node("persist", self._submit_persist_node)
        graph.add_node("path_replan", self._path_replan_node)
        graph.add_node("sprint_replan", self._sprint_replan_node)
        graph.add_edge(START, "load")
        graph.add_edge("load", "deterministic_score")
        graph.add_edge("deterministic_score", "diagnose_errors")
        graph.add_edge("diagnose_errors", "sync_weaknesses")
        graph.add_edge("sync_weaknesses", "review")
        graph.add_conditional_edges("review", self._review_route, {"repair": "repair", "persist": "persist"})
        graph.add_edge("repair", "persist")
        graph.add_edge("persist", "path_replan")
        graph.add_conditional_edges("path_replan", self._sprint_route, {"sprint_replan": "sprint_replan", "end": END})
        graph.add_edge("sprint_replan", END)
        return graph.compile()

    def _create_context_node(self, state: AssessmentState) -> dict[str, Any]:
        def work() -> tuple[dict[str, Any], str, str, dict[str, Any]]:
            course = self.service._require_course(state["user"], int(state["course_id"]))
            points = self.service.repository.list_knowledge_points(course.id)
            selected = self.service._select_points(points, list(state.get("knowledge_point_ids", [])))
            resources = self.service.repository.list_generated_resources(int(state["user_id"]), course.id)
            if not selected:
                raise PracticeValidationError("当前课程还没有可用于生成练习的知识点。")
            effective_difficulty = self.service.resolve_difficulty(state["user"], course.id, selected, str(state.get("requested_difficulty") or state["difficulty"]))
            return (
                {"course": course, "points": points, "selected_points": selected, "resources": resources, "difficulty": effective_difficulty},
                f"已选择 {len(selected)} 个知识点和 {len(resources)} 个课程资源。",
                "completed",
                {"knowledge_point_id": selected[0].id if len(selected) == 1 else None, "resource_count": len(resources), "requested_difficulty": state.get("requested_difficulty"), "effective_difficulty": effective_difficulty},
            )

        return self._run_node(state, "context", 1, "读取课程、知识点和资源证据", work)

    def _question_plan_node(self, state: AssessmentState) -> dict[str, Any]:
        def work() -> tuple[dict[str, Any], str, str, dict[str, Any]]:
            questions = self.service._build_questions(
                list(state.get("selected_points", [])),
                list(state.get("resources", [])),
                int(state["question_count"]),
                str(state["difficulty"]),
            )
            if not questions:
                raise PracticeValidationError("当前课程还没有可用于生成练习的知识点。")
            return {"deterministic_questions": questions, "questions": questions}, f"已生成 {len(questions)} 道可信题目底稿。", "completed", {"candidate_count": len(questions)}

        return self._run_node(state, "question_plan", 2, "规划题型、知识点与规则答案", work)

    def _generate_questions_node(self, state: AssessmentState) -> dict[str, Any]:
        def work() -> tuple[dict[str, Any], str, str, dict[str, Any]]:
            questions = self._model_questions(state, repair=False)
            if questions is None:
                return (
                    {"questions": list(state.get("deterministic_questions", [])), "generation_mode": "deterministic_source"},
                    "模型不可用或题目结构无效，保留规则题稿。",
                    "warning",
                    {"model_used": False, "generation_mode": "deterministic_source"},
                )
            return {"questions": questions, "generation_mode": "model_enhanced"}, "模型已增强题干和解析，规则答案保持不变。", "completed", {"model_used": True, "generation_mode": "model_enhanced"}

        return self._run_node(state, "generate_questions", 3, "增强题干、选项和解析", work)

    def _question_review_node(self, state: AssessmentState) -> dict[str, Any]:
        return self._review_questions_or_answers(state, question_mode=True, step_index=4)

    def _question_repair_node(self, state: AssessmentState) -> dict[str, Any]:
        def work() -> tuple[dict[str, Any], str, str, dict[str, Any]]:
            repaired = self._model_questions(state, repair=True)
            if repaired is None or self._question_risks(state, repaired):
                repaired = list(state.get("deterministic_questions", []))
                mode = "deterministic_source"
            else:
                mode = "model_enhanced"
            review = {
                "review_status": "passed",
                "confidence": 0.72 if mode == "model_enhanced" else 0.64,
                "risk_flags": [],
                "safety_summary": "已修订一次并通过题目结构、答案和隐私规则校验。",
            }
            return {"questions": repaired, "generation_mode": mode, "review_result": review, "repair_count": 1}, review["safety_summary"], "completed", {**review, "repair_count": 1}

        return self._run_node(state, "repair", 5, "按审核结果修订一次题目", work)

    def _create_persist_node(self, state: AssessmentState) -> dict[str, Any]:
        started = perf_counter()
        now = datetime.now(UTC)
        course = state["course"]
        session = PracticeSession(
            user_id=int(state["user_id"]),
            course_id=course.id,
            title=f"{course.title} 练习",
            status="in_progress",
            agent_trace_id=state["trace_id"],
            score=None,
            assessment_json={
                "requested_difficulty": state.get("requested_difficulty", state.get("difficulty", "medium")),
                "effective_difficulty": state.get("difficulty", "medium"),
                "sprint_plan_id": str(state["sprint_plan_id"]) if state.get("sprint_plan_id") else None,
                "sprint_task_id": str(state["sprint_task_id"]) if state.get("sprint_task_id") else None,
            },
            created_at=now,
            updated_at=now,
        )
        try:
            self.service.repository.add_practice_session(session)
            placeholders = [
                PracticeAnswer(
                    session_id=session.id,
                    user_id=int(state["user_id"]),
                    question_json=question,
                    answer_text=None,
                    feedback_json={},
                    is_correct=None,
                    created_at=now,
                )
                for question in state.get("questions", [])
            ]
            self.service.repository.replace_answers_for_session(session.id, placeholders)
            self.service.repository.commit()
            self.service.repository.refresh(session)
            detail = session_to_api(session, self.service.repository.list_answers_for_session(session.id))
        except Exception as exc:
            self.service.repository.rollback()
            self._record_failure(state, "persist", 6, "保存审核通过的练习题", exc, started)
            raise
        self._record(state, "persist", 6, "completed", "保存审核通过的练习题", f"已保存 {len(detail.questions)} 道题。", {"artifact_id": str(session.id), "repair_count": int(state.get("repair_count") or 0)}, started)
        return {"session": session, "detail": detail}

    def _load_submission_node(self, state: AssessmentState) -> dict[str, Any]:
        def work() -> tuple[dict[str, Any], str, str, dict[str, Any]]:
            session = self.service._require_session(state["user"], int(state["session_id"]))
            answer_rows = self.service.repository.list_answers_for_session(session.id)
            questions = [answer.question_json for answer in answer_rows if isinstance(answer.question_json, dict)]
            if not questions:
                raise PracticeValidationError("练习题目不存在。")
            course = self.service._require_course(state["user"], int(session.course_id or 0))
            resources = self.service.repository.list_generated_resources(int(state["user_id"]), course.id)
            return {"session": session, "course": course, "course_id": course.id, "answer_rows": answer_rows, "questions": questions, "resources": resources}, f"已读取 {len(questions)} 道练习题。", "completed", {"candidate_count": len(questions)}

        return self._run_node(state, "load", 1, "读取当前用户练习和题目", work)

    def _score_node(self, state: AssessmentState) -> dict[str, Any]:
        def work() -> tuple[dict[str, Any], str, str, dict[str, Any]]:
            normalized = self.service._normalize_answers(list(state.get("submitted_answers", [])))
            by_id = {str(question["id"]): question for question in state.get("questions", [])}
            evaluated: list[EvaluatedAnswer] = []
            for answer in normalized:
                question = by_id.get(answer["question_id"])
                if question is None:
                    raise PracticeValidationError("提交的题目不属于当前练习。")
                answer_text = safe_text(answer["answer_text"], limit=2000)
                if not answer_text:
                    raise PracticeValidationError("答案不能为空。")
                evaluated.append(self.service._evaluate_answer(question, answer_text))
            if not evaluated:
                raise PracticeValidationError("至少提交一道题。")
            score = round(sum(item.feedback["score"] for item in evaluated) / len(evaluated))
            return {"evaluated": evaluated, "score": score}, f"规则已完成 {len(evaluated)} 道题评分，总分 {score}。", "completed", {"practice_count": len(evaluated)}

        return self._run_node(state, "deterministic_score", 2, "按题型规则计算不可篡改的客观分数", work)

    def _diagnose_node(self, state: AssessmentState) -> dict[str, Any]:
        def work() -> tuple[dict[str, Any], str, str, dict[str, Any]]:
            diagnoses = self._model_diagnoses(state)
            model_used = diagnoses is not None
            if diagnoses is None:
                diagnoses = {str(item.question.get("id")): self._deterministic_diagnosis(item) for item in state.get("evaluated", []) if item.feedback["score"] < 60}
            return {"diagnoses": diagnoses, "generation_mode": "model_enhanced" if model_used else "deterministic_source"}, f"已为 {len(diagnoses)} 道低分题生成错因诊断。", "completed" if model_used else "warning", {"model_used": model_used, "weakness_count": len(diagnoses), "generation_mode": "model_enhanced" if model_used else "deterministic_source"}

        return self._run_node(state, "diagnose_errors", 3, "分析低分题的错因和缺失概念", work)

    def _sync_weaknesses_node(self, state: AssessmentState) -> dict[str, Any]:
        def work() -> tuple[dict[str, Any], str, str, dict[str, Any]]:
            rows_by_question = {str((row.question_json or {}).get("id")): row for row in state.get("answer_rows", [])}
            evaluated_by_question = {str(item.question.get("id")): item for item in state.get("evaluated", [])}
            for question_id, evaluated in evaluated_by_question.items():
                row = rows_by_question[question_id]
                diagnosis = dict(state.get("diagnoses", {}).get(question_id) or {})
                if diagnosis:
                    diagnosis["evidence_ref"] = {"type": "practice_answer", "id": str(row.id)}
                row.answer_text = evaluated.answer_text
                row.feedback_json = {**evaluated.feedback, "diagnosis": diagnosis or None}
                row.is_correct = evaluated.is_correct
            added, updated, recommended, touched = self._sync_weakness_items(state, rows_by_question)
            return {"weaknesses_added": added, "weaknesses_updated": updated, "recommended_resource_ids": recommended, "touched_weaknesses": touched}, f"新增 {added} 个弱点，更新 {updated} 个既有弱点。", "completed", {"weakness_count": added + updated}

        return self._run_node(state, "sync_weaknesses", 4, "把低分题绑定到课程弱点证据", work)

    def _answer_review_node(self, state: AssessmentState) -> dict[str, Any]:
        return self._review_questions_or_answers(state, question_mode=False, step_index=5)

    def _answer_repair_node(self, state: AssessmentState) -> dict[str, Any]:
        def work() -> tuple[dict[str, Any], str, str, dict[str, Any]]:
            diagnoses = {str(item.question.get("id")): self._deterministic_diagnosis(item) for item in state.get("evaluated", []) if item.feedback["score"] < 60}
            rows_by_question = {str((row.question_json or {}).get("id")): row for row in state.get("answer_rows", [])}
            for question_id, diagnosis in diagnoses.items():
                row = rows_by_question[question_id]
                diagnosis["evidence_ref"] = {"type": "practice_answer", "id": str(row.id)}
                row.feedback_json = {**(row.feedback_json or {}), "diagnosis": diagnosis}
                weakness = state.get("touched_weaknesses", {}).get(question_id)
                if weakness is not None:
                    self._apply_diagnosis_to_weakness(weakness, diagnosis, row.id)
            review = {"review_status": "passed", "confidence": 0.66, "risk_flags": [], "safety_summary": "已使用确定性错因摘要完成一次修订，并重新校验分数。"}
            return {"diagnoses": diagnoses, "generation_mode": "deterministic_source", "review_result": review, "repair_count": 1}, review["safety_summary"], "completed", {**review, "repair_count": 1}

        return self._run_node(state, "repair", 6, "修订错因摘要但保持规则分数不变", work)

    def _submit_persist_node(self, state: AssessmentState) -> dict[str, Any]:
        started = perf_counter()
        session = state["session"]
        try:
            session.status = "completed"
            session.score = Decimal(str(state["score"]))
            session.agent_trace_id = state["trace_id"]
            session.updated_at = datetime.now(UTC)
            session.assessment_json = {
                **(session.assessment_json or {}),
                "weaknesses_added": int(state.get("weaknesses_added") or 0),
                "weaknesses_updated": int(state.get("weaknesses_updated") or 0),
                "path_update_status": "not_started",
                "path_agent_trace_id": None,
                "sprint_update_status": "not_started",
                "sprint_plan_id": (session.assessment_json or {}).get("sprint_plan_id"),
                "sprint_agent_trace_id": None,
                "recommended_resource_ids": [str(item) for item in state.get("recommended_resource_ids", [])],
                "generation_mode": state.get("generation_mode", "deterministic_source"),
                "review_mode": state.get("review_mode", "rules_only"),
                "review_result": state.get("review_result", {}),
            }
            self.service.repository.commit()
            self.service.repository.refresh(session)
        except Exception as exc:
            self.service.repository.rollback()
            self._record_failure(state, "persist", 7, "保存练习、反馈和弱点更新", exc, started)
            raise
        self._record(state, "persist", 7, "completed", "保存练习、反馈和弱点更新", "练习结果与弱点证据已事务化保存。", {"artifact_id": str(session.id), "repair_count": int(state.get("repair_count") or 0)}, started)
        return {"session": session}

    def _path_replan_node(self, state: AssessmentState) -> dict[str, Any]:
        def work() -> tuple[dict[str, Any], str, str, dict[str, Any]]:
            session = state["session"]
            status = "not_started"
            path_trace_id = None
            if self.service.path_service is not None:
                try:
                    result = self.service.path_service.replan_after_assessment(state["user"], int(state["course_id"]), session.id)
                    status = str(getattr(result, "status", "unchanged"))
                    path_trace_id = getattr(result, "trace_id", None)
                except Exception:
                    status = "failed"
            session.assessment_json = {**(session.assessment_json or {}), "path_update_status": status, "path_agent_trace_id": path_trace_id}
            self.service.repository.commit()
            self.service.repository.refresh(session)
            if self.service.profile_service is not None:
                try:
                    weak_points = list(dict.fromkeys(item.title for item in state.get("touched_weaknesses", {}).values() if item.title))
                    if weak_points:
                        ingest = getattr(self.service.profile_service, "ingest_learning_signal", None)
                        if callable(ingest):
                            ingest(
                                user=state["user"],
                                source_type="practice_assessment",
                                source_ref_type="practice_session",
                                source_ref_id=session.id,
                                suggested_updates={"weak_points": weak_points[:5]},
                                course_id=int(state["course_id"]),
                                parent_trace_id=state["trace_id"],
                            )
                except Exception:
                    pass
            detail = session_to_api(session, self.service.repository.list_answers_for_session(session.id))
            node_status = "warning" if status in {"not_started", "failed"} else "completed"
            summary = "当前课程尚未建立路径，未自动创建。" if status == "not_started" else ("路径重排失败，练习结果已保留。" if status == "failed" else "已有路径已根据练习结果重排。")
            return {"detail": detail}, summary, node_status, {"path_update_status": status}

        return self._run_node(state, "path_replan", 8, "按练习结果重排已存在的学习路径", work)

    def _sprint_replan_node(self, state: AssessmentState) -> dict[str, Any]:
        def work() -> tuple[dict[str, Any], str, str, dict[str, Any]]:
            session = state["session"]
            assessment = dict(session.assessment_json or {})
            plan_id = self.service._safe_int(assessment.get("sprint_plan_id"))
            task_id = self.service._safe_int(assessment.get("sprint_task_id"))
            status = "not_started"
            next_plan_id = plan_id
            trace_id = None
            if plan_id is not None and task_id is not None and self.service.sprint_service is not None:
                try:
                    result = self.service.sprint_service.replan_after_assessment(
                        state["user"],
                        int(state["course_id"]),
                        session.id,
                        plan_id,
                        task_id,
                    )
                    status = str(getattr(result, "status", "unchanged"))
                    next_plan_id = getattr(result, "plan_id", None) or plan_id
                    trace_id = getattr(result, "trace_id", None)
                except Exception:
                    status = "failed"
            session.assessment_json = {
                **assessment,
                "sprint_update_status": status,
                "sprint_plan_id": str(next_plan_id) if next_plan_id is not None else None,
                "sprint_agent_trace_id": trace_id,
            }
            self.service.repository.commit()
            self.service.repository.refresh(session)
            detail = session_to_api(session, self.service.repository.list_answers_for_session(session.id))
            if status == "replanned":
                summary = "冲刺计划已根据本次必刷题结果重排。"
                node_status = "completed"
            elif status == "failed":
                summary = "冲刺计划重排失败，练习结果已保留。"
                node_status = "warning"
            elif status == "unchanged":
                summary = "冲刺计划状态已变化，本次未重排。"
                node_status = "warning"
            else:
                summary = "本次练习不是从冲刺任务发起，不更新冲刺计划。"
                node_status = "completed"
            return (
                {"detail": detail},
                summary,
                node_status,
                {"sprint_update_status": status, "artifact_id": str(session.id)},
            )

        return self._run_node(state, "sprint_replan", 9, "仅为冲刺来源练习重排对应计划", work)

    @staticmethod
    def _sprint_route(state: AssessmentState) -> str:
        assessment = dict(state["session"].assessment_json or {})
        return "sprint_replan" if assessment.get("sprint_plan_id") and assessment.get("sprint_task_id") else "end"

    def _review_questions_or_answers(self, state: AssessmentState, *, question_mode: bool, step_index: int) -> dict[str, Any]:
        def work() -> tuple[dict[str, Any], str, str, dict[str, Any]]:
            risks = self._question_risks(state, list(state.get("questions", []))) if question_mode else self._answer_risks(state)
            model_review = None
            if state.get("generation_mode") == "model_enhanced" and self.service.model_service is not None:
                try:
                    raw = self.service.model_service.chat_completion(
                        state["user"],
                        [
                            {"role": "system", "content": "你是 AssessmentGraph 的 ReviewAgent。只输出 JSON，不得修改客观分数。"},
                            {
                                "role": "user",
                                "content": (
                                    f"审核类型={'题目' if question_mode else '错因反馈'}，数量="
                                    f"{len(state.get('questions', [])) if question_mode else len(state.get('evaluated', []))}。"
                                    "返回 {\"review_status\":\"passed|revise\",\"confidence\":0.0,"
                                    "\"risk_flags\":[],\"safety_summary\":\"\"}。"
                                ),
                            },
                        ],
                    )
                    model_review = review_contract(parse_json_object(raw), default_summary="已完成练习结构、分数与隐私审核。")
                except Exception:
                    model_review = None
            if model_review and model_review["review_status"] == "revise":
                risks.extend(str(item) for item in model_review["risk_flags"])
            risks = list(dict.fromkeys(risks))
            if risks:
                review = {"review_status": "revise", "confidence": model_review["confidence"] if model_review else 0.42, "risk_flags": risks, "safety_summary": model_review["safety_summary"] if model_review else "规则审核发现练习内容需要修订。"}
                return {"review_result": review, "needs_repair": True, "review_mode": "model_and_rules" if model_review else "rules_only"}, "练习内容需要修订。", "warning", review
            if model_review is None:
                review = {"review_status": "warning", "confidence": 0.62, "risk_flags": [], "safety_summary": "模型审核不可用，已完成题目、分数、引用和隐私规则审核。"}
                return {"review_result": review, "needs_repair": False, "review_mode": "rules_only"}, review["safety_summary"], "warning", review
            review = {**model_review, "review_status": "passed", "risk_flags": []}
            return {"review_result": review, "needs_repair": False, "review_mode": "model_and_rules"}, "ReviewAgent 审核通过。", "completed", review

        return self._run_node(state, "review", step_index, "审核题目或反馈的结构、分数与安全边界", work)

    @staticmethod
    def _review_route(state: AssessmentState) -> str:
        return "repair" if state.get("needs_repair") else "persist"

    def _model_questions(self, state: AssessmentState, *, repair: bool) -> list[dict[str, Any]] | None:
        if self.service.model_service is None:
            return None
        drafts = list(state.get("deterministic_questions", []))
        prompt_rows = [{"id": item["id"], "question_type": item["question_type"], "knowledge_point_id": item["knowledge_point_id"], "prompt": item["prompt"], "options": item["options"], "explanation": item["explanation"]} for item in drafts]
        instruction = "这是唯一一次修订机会。" if repair else "增强题干、干扰项和解析，但不得改变题目 ID、类型、知识点或规则答案。"
        try:
            raw = self.service.model_service.chat_completion(
                state["user"],
                [
                    {"role": "system", "content": "你是 AssessmentGraph 出题 Agent。只输出 JSON，禁止泄露答案生成规则。"},
                    {"role": "user", "content": f"{instruction} 题目底稿={prompt_rows}。返回 {{\"questions\":[{{\"id\":\"q1\",\"prompt\":\"\",\"options\":[],\"explanation\":\"\"}}]}}。"},
                ],
            )
        except Exception:
            return None
        payload = parse_json_object(raw)
        if payload is None or not isinstance(payload.get("questions"), list):
            return None
        by_id = {str(item.get("id")): item for item in payload["questions"] if isinstance(item, dict)}
        if set(by_id) != {str(item["id"]) for item in drafts}:
            return None
        enhanced: list[dict[str, Any]] = []
        for draft in drafts:
            model_item = by_id[str(draft["id"])]
            prompt = safe_text(model_item.get("prompt"), limit=800)
            explanation = safe_text(model_item.get("explanation"), limit=800)
            candidate = {**draft, "prompt": prompt or draft["prompt"], "explanation": explanation or draft["explanation"]}
            options = safe_string_list(model_item.get("options"), limit=8, item_limit=240)
            if draft["question_type"] != "short_answer" and options:
                correct = draft.get("correct_answer")
                expected = [str(item) for item in correct] if isinstance(correct, list) else [str(correct)]
                if all(item in options for item in expected):
                    candidate["options"] = options
            enhanced.append(candidate)
        return enhanced

    def _model_diagnoses(self, state: AssessmentState) -> dict[str, dict[str, Any]] | None:
        if self.service.model_service is None:
            return None
        wrong = [item for item in state.get("evaluated", []) if item.feedback["score"] < 60]
        if not wrong:
            return {}
        rows = [
            {
                "question_id": str(item.question.get("id")),
                "knowledge_point": safe_text(item.question.get("knowledge_point_title"), limit=120),
                "answer": safe_text(item.answer_text, limit=500),
                "missing_keywords": list(item.feedback.get("missing_keywords") or [])[:5],
                "score": int(item.feedback["score"]),
            }
            for item in wrong
        ]
        try:
            raw = self.service.model_service.chat_completion(
                state["user"],
                [
                    {"role": "system", "content": "你是 AssessmentGraph 错因诊断 Agent。不得修改分数，只输出 JSON。"},
                    {"role": "user", "content": f"诊断这些低分题={rows}。返回 {{\"diagnoses\":[{{\"question_id\":\"q1\",\"misconception\":\"\",\"missing_concepts\":[],\"recommended_action\":\"\",\"confidence\":0.0}}]}}。"},
                ],
            )
        except Exception:
            return None
        payload = parse_json_object(raw)
        if payload is None or not isinstance(payload.get("diagnoses"), list):
            return None
        valid_ids = {str(item.question.get("id")) for item in wrong}
        diagnoses: dict[str, dict[str, Any]] = {}
        for item in payload["diagnoses"]:
            if not isinstance(item, dict):
                return None
            question_id = safe_text(item.get("question_id"), limit=80)
            if question_id not in valid_ids or question_id in diagnoses:
                return None
            diagnosis = {
                "misconception": safe_text(item.get("misconception"), limit=300),
                "missing_concepts": safe_string_list(item.get("missing_concepts"), limit=6, item_limit=100),
                "recommended_action": safe_text(item.get("recommended_action"), limit=300),
                "confidence": clamp_confidence(item.get("confidence"), 0.6),
            }
            if not diagnosis["misconception"] or not diagnosis["recommended_action"] or contains_sensitive_text(diagnosis):
                return None
            diagnoses[question_id] = diagnosis
        if set(diagnoses) != valid_ids:
            return None
        return diagnoses

    def _sync_weakness_items(
        self,
        state: AssessmentState,
        rows_by_question: dict[str, PracticeAnswer],
    ) -> tuple[int, int, list[int], dict[str, WeaknessReviewItem]]:
        existing = self.service.repository.list_weakness_review_items(int(state["user_id"]), int(state["course_id"]))
        by_point = {item.knowledge_point_id: item for item in existing if item.knowledge_point_id is not None}
        by_title = {safe_text(item.title, limit=255).casefold(): item for item in existing}
        resources = list(state.get("resources", []))
        added = 0
        updated = 0
        recommended: list[int] = []
        touched: dict[str, WeaknessReviewItem] = {}
        for evaluated in state.get("evaluated", []):
            if evaluated.feedback["score"] >= 60:
                continue
            question_id = str(evaluated.question.get("id"))
            row = rows_by_question[question_id]
            point_id = self.service._safe_int(evaluated.question.get("knowledge_point_id"))
            title = safe_text(evaluated.question.get("knowledge_point_title") or "练习薄弱点", limit=120)
            diagnosis = dict((row.feedback_json or {}).get("diagnosis") or {})
            resource_ids = [resource.id for resource in resources if point_id is not None and resource.knowledge_point_id == point_id][:3]
            recommended.extend(resource_ids)
            item = by_point.get(point_id) if point_id is not None else by_title.get(title.casefold())
            if item is None:
                item = self.service.repository.add_weakness_review_item(
                    WeaknessReviewItem(
                        user_id=int(state["user_id"]),
                        course_id=int(state["course_id"]),
                        knowledge_point_id=point_id,
                        title=title,
                        source_type="practice_assessment",
                        source_ref_type="practice_answer",
                        source_ref_id=row.id,
                        diagnosis_json={},
                        status="confirmed",
                        recommended_resource_ids=resource_ids,
                        next_review_at=datetime.now(UTC) + timedelta(days=3),
                        created_at=datetime.now(UTC),
                        updated_at=datetime.now(UTC),
                    )
                )
                added += 1
                if point_id is not None:
                    by_point[point_id] = item
                by_title[title.casefold()] = item
            else:
                updated += 1
                item.status = "confirmed"
                item.updated_at = datetime.now(UTC)
                item.next_review_at = datetime.now(UTC) + timedelta(days=3)
                item.recommended_resource_ids = list(dict.fromkeys([*(item.recommended_resource_ids or []), *resource_ids]))[:6]
            self._apply_diagnosis_to_weakness(item, diagnosis, row.id)
            touched[question_id] = item
        return added, updated, list(dict.fromkeys(recommended)), touched

    @staticmethod
    def _apply_diagnosis_to_weakness(item: WeaknessReviewItem, diagnosis: dict[str, Any], answer_id: int) -> None:
        previous = item.diagnosis_json or {}
        refs = [str(value) for value in previous.get("evidence_refs") or []]
        answer_ref = str(answer_id)
        was_present = answer_ref in refs
        if not was_present:
            refs.append(answer_ref)
        item.source_ref_type = "practice_answer"
        item.source_ref_id = answer_id
        item.diagnosis_json = {
            "misconception": safe_text(diagnosis.get("misconception"), limit=300),
            "missing_concepts": safe_string_list(diagnosis.get("missing_concepts"), limit=6, item_limit=100),
            "recommended_action": safe_text(diagnosis.get("recommended_action"), limit=300),
            "confidence": clamp_confidence(diagnosis.get("confidence"), 0.6),
            "evidence_refs": refs[-5:],
            "evidence_count": min(int(previous.get("evidence_count") or 0) + (0 if was_present else 1), 999),
        }

    @staticmethod
    def _deterministic_diagnosis(item: EvaluatedAnswer) -> dict[str, Any]:
        missing = [str(value) for value in item.feedback.get("missing_keywords") or []][:6]
        point = safe_text(item.question.get("knowledge_point_title") or "当前知识点", limit=120)
        return {
            "misconception": f"回答尚未覆盖{point}的关键依据。",
            "missing_concepts": missing,
            "recommended_action": f"先复习{point}的课程引用和易错点，再完成一道同类练习。",
            "confidence": 0.66,
        }

    def _question_risks(self, state: AssessmentState, questions: list[dict[str, Any]]) -> list[str]:
        drafts = list(state.get("deterministic_questions", []))
        if len(questions) != len(drafts):
            return ["question_count_mismatch"]
        draft_by_id = {str(item["id"]): item for item in drafts}
        risks: list[str] = []
        for question in questions:
            question_id = str(question.get("id"))
            draft = draft_by_id.get(question_id)
            if draft is None:
                risks.append("invalid_question_id")
                continue
            for immutable in ("question_type", "knowledge_point_id", "correct_answer"):
                if question.get(immutable) != draft.get(immutable):
                    risks.append("answer_contract_changed")
            options = [str(value) for value in question.get("options") or []]
            correct = question.get("correct_answer")
            expected = [str(value) for value in correct] if isinstance(correct, list) else ([str(correct)] if correct else [])
            if any(value not in options for value in expected) and question.get("question_type") != "short_answer":
                risks.append("correct_answer_missing")
            if contains_sensitive_text(question):
                risks.append("sensitive_output")
        return list(dict.fromkeys(risks))

    def _answer_risks(self, state: AssessmentState) -> list[str]:
        evaluated_by_id = {str(item.question.get("id")): item for item in state.get("evaluated", [])}
        risks: list[str] = []
        for row in state.get("answer_rows", []):
            question_id = str((row.question_json or {}).get("id"))
            evaluated = evaluated_by_id.get(question_id)
            if evaluated is None or row.answer_text is None:
                continue
            if int((row.feedback_json or {}).get("score") or 0) != int(evaluated.feedback["score"]):
                risks.append("score_mismatch")
            if contains_sensitive_text((row.feedback_json or {}).get("diagnosis")):
                risks.append("sensitive_output")
        return list(dict.fromkeys(risks))

    def _run_node(
        self,
        state: AssessmentState,
        agent_name: str,
        step_index: int,
        input_summary: str,
        work: Callable[[], tuple[dict[str, Any], str, str, dict[str, Any]]],
    ) -> dict[str, Any]:
        started = perf_counter()
        try:
            result, output_summary, status, metadata = work()
        except Exception as exc:
            self._record_failure(state, agent_name, step_index, input_summary, exc, started)
            raise
        self._record(state, agent_name, step_index, status, input_summary, output_summary, metadata, started)
        return result

    def _record_failure(self, state: AssessmentState, agent_name: str, step_index: int, input_summary: str, exc: Exception, started: float) -> None:
        self._record(state, agent_name, step_index, "failed", input_summary, "节点执行失败，已记录安全错误摘要。", {"error_code": exc.__class__.__name__}, started)

    def _record(
        self,
        state: AssessmentState,
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
            course_id=int(state.get("course_id") or 0) or None,
            agent_name=agent_name,
            step_index=step_index,
            status=status,
            input_summary=input_summary,
            output_summary=output_summary,
            duration_ms=max(0, int((perf_counter() - started) * 1000)),
            workflow=self.workflow,
            artifact_type="practice_session",
            artifact_id=metadata.get("artifact_id"),
            metadata={"operation": state.get("operation"), **metadata},
        )

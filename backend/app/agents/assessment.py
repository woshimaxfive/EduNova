from __future__ import annotations

from difflib import SequenceMatcher
import json
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
from backend.app.services.practice import EvaluatedAnswer, PracticeGenerationError, PracticeService, PracticeValidationError
from backend.app.services.model_execution import execution_context_for_state, model_execution_scope
from backend.app.services.learner_context import context_service_from_repository
from backend.app.services.semantic_grading import SemanticShortAnswerGrader
from backend.app.services.content_locale import china_first_content_policy
from backend.app.providers.model_tasks import ModelTaskProfile


ASSESSMENT_PROMPT_VERSION = "assessment-v3.2"
ASSESSMENT_REVIEW_PROMPT_VERSION = "assessment-review-v3.1"
ASSESSMENT_EMBEDDED_REVIEW_PROMPT_VERSION = "assessment-review-v3.2-embedded"
DIAGNOSIS_PROMPT_VERSION = "diagnosis-v3.1"
OPTIONAL_GENERATION_TIMEOUT_SECONDS = 30.0


class AssessmentState(TypedDict, total=False):
    trace_id: str
    job_context: Any
    operation: str
    user: User
    user_id: int
    course_id: int
    session_id: int
    knowledge_point_ids: list[int]
    question_count: int
    difficulty: str
    requested_difficulty: str
    submitted_answers: list[SubmitPracticeAnswerItem | dict]
    course: Any
    points: list[Any]
    selected_points: list[Any]
    resources: list[Any]
    chunks: list[Any]
    learner_context: Any
    historical_question_summaries: list[dict[str, Any]]
    deterministic_questions: list[dict[str, Any]]
    questions: list[dict[str, Any]]
    session: PracticeSession
    answer_rows: list[PracticeAnswer]
    evaluated: list[EvaluatedAnswer]
    score: int | None
    diagnoses: dict[str, dict[str, Any]]
    touched_weaknesses: dict[str, WeaknessReviewItem]
    weaknesses_added: int
    weaknesses_updated: int
    recommended_resource_ids: list[int]
    generation_mode: str
    review_mode: str
    review_result: dict[str, Any]
    generation_review: dict[str, Any] | None
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
        trace_id: str | None = None,
        job_context: Any = None,
    ) -> PracticeSessionDetail:
        state: AssessmentState = {
            "trace_id": trace_id or make_trace_id(),
            "job_context": job_context,
            "operation": "question_generation",
            "user": user,
            "user_id": user.id,
            "course_id": course_id,
            "knowledge_point_ids": knowledge_point_ids,
            "question_count": question_count,
            "difficulty": difficulty,
            "requested_difficulty": difficulty,
            "repair_count": 0,
        }
        with model_execution_scope(execution_context_for_state(state, workflow=self.workflow, purpose="question_generation")):
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
        with model_execution_scope(execution_context_for_state(state, workflow=self.workflow, purpose="answer_evaluation")):
            return self.submit_graph.invoke(state)["detail"]

    def regrade_answers(self, *, user: User, session_id: int) -> PracticeSessionDetail:
        session = self.service._require_session(user, session_id)
        rows = self.service.repository.list_answers_for_session(session.id)
        pending = [
            row
            for row in rows
            if row.answer_text
            and (row.question_json or {}).get("question_type") == "short_answer"
            and (row.feedback_json or {}).get("grading_status") == "ungraded"
        ]
        if not pending:
            return session_to_api(session, rows)
        items = [self._grading_item(row.question_json or {}, str(row.answer_text)) for row in pending]
        grades = SemanticShortAnswerGrader(self.service.model_service).grade(user=user, items=items)
        if grades is None:
            return session_to_api(session, rows)
        evaluated = [self._semantic_evaluated(row.question_json or {}, str(row.answer_text), grades[str((row.question_json or {}).get("id"))]) for row in pending]
        diagnoses = {str(item.question.get("id")): self._diagnosis_from_evaluation(item) for item in evaluated if item.feedback.get("score") is not None and item.feedback["score"] < 60}
        by_question = {str((row.question_json or {}).get("id")): row for row in rows}
        for item in evaluated:
            question_id = str(item.question.get("id"))
            row = by_question[question_id]
            diagnosis = diagnoses.get(question_id)
            if diagnosis:
                diagnosis = {**diagnosis, "evidence_ref": {"type": "practice_answer", "id": str(row.id)}}
            row.feedback_json = {**item.feedback, "diagnosis": diagnosis}
            row.is_correct = item.is_correct
        course = self.service._require_course(user, int(session.course_id or 0))
        state: AssessmentState = {
            "trace_id": make_trace_id(),
            "operation": "answer_regrade",
            "user": user,
            "user_id": user.id,
            "course_id": course.id,
            "session": session,
            "resources": self.service.repository.list_generated_resources(user.id, course.id),
            "evaluated": evaluated,
            "diagnoses": diagnoses,
        }
        try:
            added, updated, recommended, touched = self._sync_weakness_items(state, by_question)
            session.score = self._score_from_rows(rows)
            session.assessment_json = {
                **(session.assessment_json or {}),
                "grading_status": self._grading_status_from_rows(rows),
                "weaknesses_added": int((session.assessment_json or {}).get("weaknesses_added") or 0) + added,
                "weaknesses_updated": int((session.assessment_json or {}).get("weaknesses_updated") or 0) + updated,
                "recommended_resource_ids": list(dict.fromkeys([*(session.assessment_json or {}).get("recommended_resource_ids", []), *[str(value) for value in recommended]])),
            }
            session.updated_at = datetime.now(UTC)
            self.service.repository.commit()
            self.service.repository.refresh(session)
        except Exception:
            self.service.repository.rollback()
            raise
        self._run_post_grade_closure(user, session, touched, state["trace_id"])
        return session_to_api(session, self.service.repository.list_answers_for_session(session.id))

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
        graph.add_edge(START, "load")
        graph.add_edge("load", "deterministic_score")
        graph.add_edge("deterministic_score", "diagnose_errors")
        graph.add_edge("diagnose_errors", "sync_weaknesses")
        graph.add_edge("sync_weaknesses", "review")
        graph.add_conditional_edges("review", self._review_route, {"repair": "repair", "persist": "persist"})
        graph.add_edge("repair", "persist")
        graph.add_edge("persist", "path_replan")
        graph.add_edge("path_replan", END)
        return graph.compile()

    def _create_context_node(self, state: AssessmentState) -> dict[str, Any]:
        def work() -> tuple[dict[str, Any], str, str, dict[str, Any]]:
            course = self.service._require_course(state["user"], int(state["course_id"]))
            points = self.service.repository.list_knowledge_points(course.id)
            selected = self.service._select_points(points, list(state.get("knowledge_point_ids", [])))
            resources = self.service.repository.list_generated_resources(int(state["user_id"]), course.id)
            list_chunks = getattr(self.service.repository, "list_knowledge_chunks", None)
            chunks = list_chunks(course.id) if callable(list_chunks) else []
            if not selected:
                raise PracticeValidationError("当前课程还没有可用于生成练习的知识点。")
            effective_difficulty = self.service.resolve_difficulty(state["user"], course.id, selected, str(state.get("requested_difficulty") or state["difficulty"]))
            context_service = context_service_from_repository(self.service.repository)
            learner_context = context_service.course_context(int(state["user_id"]), course.id) if context_service is not None else None
            selected_ids = {point.id for point in selected}
            historical_question_summaries = [
                {
                    "prompt": safe_text((answer.question_json or {}).get("prompt"), limit=320),
                    "knowledge_point_id": (answer.question_json or {}).get("knowledge_point_id"),
                    "cognitive_level": safe_text((answer.question_json or {}).get("cognitive_level"), limit=40),
                    "scenario_type": safe_text((answer.question_json or {}).get("scenario_type"), limit=80),
                    "target_misconception": safe_text(
                        (answer.question_json or {}).get("target_misconception"), limit=120
                    ),
                    "reasoning_pattern": safe_text((answer.question_json or {}).get("reasoning_pattern"), limit=80),
                }
                for answer in self.service.repository.list_answers_for_course(int(state["user_id"]), course.id)
                if (answer.question_json or {}).get("knowledge_point_id") in selected_ids
                and (answer.question_json or {}).get("prompt")
            ][:20]
            return (
                {
                    "course": course,
                    "points": points,
                    "selected_points": selected,
                    "resources": resources,
                    "chunks": chunks,
                    "difficulty": effective_difficulty,
                    "learner_context": learner_context,
                    "historical_question_summaries": historical_question_summaries,
                },
                f"已选择 {len(selected)} 个知识点和 {len(resources)} 个课程资源。",
                "completed",
                {
                    "knowledge_point_id": selected[0].id if len(selected) == 1 else None,
                    "resource_count": len(resources),
                    "requested_difficulty": state.get("requested_difficulty"),
                    "effective_difficulty": effective_difficulty,
                    **(learner_context.trace_metadata() if learner_context is not None else {"profile_context_used": False}),
                },
            )

        return self._run_node(state, "context", 1, "读取课程、知识点和资源证据", work)

    def _question_plan_node(self, state: AssessmentState) -> dict[str, Any]:
        def work() -> tuple[dict[str, Any], str, str, dict[str, Any]]:
            questions = self.service._build_questions(
                list(state.get("selected_points", [])),
                list(state.get("resources", [])),
                int(state["question_count"]),
                str(state["difficulty"]),
                list(state.get("chunks", [])),
            )
            if not questions:
                raise PracticeValidationError("当前课程还没有可用于生成练习的知识点。")
            return {"deterministic_questions": questions, "questions": questions}, f"已生成 {len(questions)} 道可信题目底稿。", "completed", {"candidate_count": len(questions)}

        return self._run_node(state, "question_plan", 2, "规划题型、知识点与规则答案", work)

    def _generate_questions_node(self, state: AssessmentState) -> dict[str, Any]:
        def work() -> tuple[dict[str, Any], str, str, dict[str, Any]]:
            generated = self._model_questions(state)
            if generated is None:
                raise PracticeGenerationError("AI练习题生成失败，未创建练习，请重试或检查结构化模型能力。")
            questions, generation_review = generated
            return (
                {"questions": questions, "generation_mode": "model_generated", "generation_review": generation_review},
                "模型已增强题干和解析，并在同一次调用中完成安全自审。",
                "completed",
                {
                    "model_used": True,
                    "generation_mode": "model_generated",
                    "embedded_review": generation_review is not None,
                    "model_call_budget": 1,
                },
            )

        return self._run_node(state, "generate_questions", 3, "增强题干、选项和解析", work)

    def _question_review_node(self, state: AssessmentState) -> dict[str, Any]:
        return self._review_questions_or_answers(state, question_mode=True, step_index=4)

    def _question_repair_node(self, state: AssessmentState) -> dict[str, Any]:
        risks = safe_string_list((state.get("review_result") or {}).get("risk_flags"), limit=8, item_limit=60)
        generated = self._model_questions(
            state,
            revision_risks=risks,
            revision_questions=list(state.get("questions", [])),
        )
        if generated is None:
            raise PracticeValidationError(
                f"AI练习题未通过质量审核，单次修订失败，未创建练习。风险：{'、'.join(risks) or '结构不完整'}"
            )
        questions, generation_review = generated
        remaining_risks = self._question_risks(state, questions)
        if remaining_risks:
            raise PracticeValidationError(
                f"AI练习题单次修订后仍未通过质量审核，未创建练习。风险：{'、'.join(remaining_risks[:4])}"
            )
        return {
            "questions": questions,
            "generation_mode": "model_generated",
            "generation_review": generation_review,
            "review_result": {
                "review_status": "passed",
                "confidence": 0.78,
                "risk_flags": [],
                "safety_summary": "模型已定向修订失败字段，并通过确定性题目合同审核。",
            },
            "review_mode": "embedded_model_and_rules",
            "needs_repair": False,
            "repair_count": 1,
        }

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
                **china_first_content_policy.metadata(),
            },
            created_at=now,
            updated_at=now,
        )
        try:
            self.service.repository.add_practice_session(session)
            persisted_questions = [
                {
                    **question,
                    "generation_mode": state.get("generation_mode", "deterministic_source"),
                    "review_mode": state.get("review_mode", "rules_only"),
                    "review_result": dict(state.get("review_result") or {}),
                    "quality": {
                        **dict(question.get("quality") or {}),
                        "review_prompt_version": ASSESSMENT_EMBEDDED_REVIEW_PROMPT_VERSION,
                        "review_mode": state.get("review_mode", "rules_only"),
                        "review_status": (state.get("review_result") or {}).get("review_status", "warning"),
                        "personalization_factors": (
                            state["learner_context"].trace_metadata().get("personalization_factors", [])
                            if state.get("learner_context") is not None
                            else []
                        ),
                        "repair_count": int(state.get("repair_count") or 0),
                    },
                }
                for question in state.get("questions", [])
            ]
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
                for question in persisted_questions
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
            context_service = context_service_from_repository(self.service.repository)
            learner_context = context_service.course_context(int(state["user_id"]), course.id) if context_service is not None else None
            return (
                {"session": session, "course": course, "course_id": course.id, "answer_rows": answer_rows, "questions": questions, "resources": resources, "learner_context": learner_context},
                f"已读取 {len(questions)} 道练习题。",
                "completed",
                {"candidate_count": len(questions), **(learner_context.trace_metadata() if learner_context is not None else {"profile_context_used": False})},
            )

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
            short_answers = [item for item in evaluated if item.feedback.get("grading_status") == "ungraded"]
            grades = SemanticShortAnswerGrader(self.service.model_service).grade(
                user=state["user"],
                items=[self._grading_item(item.question, item.answer_text) for item in short_answers],
            )
            if grades is not None:
                evaluated = [
                    self._semantic_evaluated(item.question, item.answer_text, grades[str(item.question.get("id"))])
                    if item in short_answers
                    else item
                    for item in evaluated
                ]
            graded_scores = [int(item.feedback["score"]) for item in evaluated if item.feedback.get("score") is not None]
            score = round(sum(graded_scores) / len(graded_scores)) if graded_scores else None
            ungraded_count = len(evaluated) - len(graded_scores)
            status = "warning" if ungraded_count else "completed"
            summary = f"已评分 {len(graded_scores)} 道题，{ungraded_count} 道简答题暂未评分。"
            return {"evaluated": evaluated, "score": score}, summary, status, {
                "practice_count": len(evaluated),
                "graded_count": len(graded_scores),
                "ungraded_count": ungraded_count,
                "semantic_grading_used": grades is not None,
            }

        return self._run_node(state, "deterministic_score", 2, "按题型规则计算不可篡改的客观分数", work)

    def _diagnose_node(self, state: AssessmentState) -> dict[str, Any]:
        def work() -> tuple[dict[str, Any], str, str, dict[str, Any]]:
            diagnoses = {
                str(item.question.get("id")): self._diagnosis_from_evaluation(item)
                for item in state.get("evaluated", [])
                if item.feedback.get("score") is not None and item.feedback["score"] < 60
            }
            model_used = any(item.feedback.get("grading_status") == "model" for item in state.get("evaluated", []))
            mode = "semantic_grading" if model_used else "deterministic_source"
            return {"diagnoses": diagnoses, "generation_mode": mode}, f"已为 {len(diagnoses)} 道低分题生成错因诊断。", "completed", {"model_used": model_used, "weakness_count": len(diagnoses), "generation_mode": mode}

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
            diagnoses = {
                str(item.question.get("id")): self._diagnosis_from_evaluation(item)
                for item in state.get("evaluated", [])
                if item.feedback.get("score") is not None and item.feedback["score"] < 60
            }
            rows_by_question = {str((row.question_json or {}).get("id")): row for row in state.get("answer_rows", [])}
            for question_id, diagnosis in diagnoses.items():
                row = rows_by_question[question_id]
                diagnosis["evidence_ref"] = {"type": "practice_answer", "id": str(row.id)}
                row.feedback_json = {**(row.feedback_json or {}), "diagnosis": diagnosis}
                weakness = state.get("touched_weaknesses", {}).get(question_id)
                if weakness is not None:
                    self._apply_diagnosis_to_weakness(weakness, diagnosis, row.id)
            review = {"review_status": "warning", "confidence": 0.66, "risk_flags": [], "safety_summary": "模型诊断未通过审核，已使用逐题确定性错因摘要并重新校验分数。"}
            return {"diagnoses": diagnoses, "generation_mode": "deterministic_source", "review_mode": "rules_only", "review_result": review, "repair_count": 1}, review["safety_summary"], "warning", {**review, "repair_count": 1}

        return self._run_node(state, "repair", 6, "修订错因摘要但保持规则分数不变", work)

    def _submit_persist_node(self, state: AssessmentState) -> dict[str, Any]:
        started = perf_counter()
        session = state["session"]
        try:
            session.status = "completed"
            session.score = Decimal(str(state["score"])) if state.get("score") is not None else None
            session.agent_trace_id = state["trace_id"]
            session.updated_at = datetime.now(UTC)
            session.assessment_json = {
                **(session.assessment_json or {}),
                "weaknesses_added": int(state.get("weaknesses_added") or 0),
                "weaknesses_updated": int(state.get("weaknesses_updated") or 0),
                "path_update_status": "not_started",
                "path_agent_trace_id": None,
                "recommended_resource_ids": [str(item) for item in state.get("recommended_resource_ids", [])],
                "generation_mode": state.get("generation_mode", "deterministic_source"),
                "review_mode": state.get("review_mode", "rules_only"),
                "review_result": state.get("review_result", {}),
                "grading_status": self._grading_status(state.get("evaluated", [])),
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
            if state.get("score") is not None and self.service.path_service is not None:
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

    def _review_questions_or_answers(self, state: AssessmentState, *, question_mode: bool, step_index: int) -> dict[str, Any]:
        def work() -> tuple[dict[str, Any], str, str, dict[str, Any]]:
            risks = self._question_risks(state, list(state.get("questions", []))) if question_mode else self._answer_risks(state)
            model_review = (
                state.get("generation_review")
                if question_mode and state.get("generation_mode") == "model_generated"
                else self._model_review(state, question_mode=question_mode)
                if state.get("generation_mode") in {"model_generated", "model_enhanced"}
                else None
            )
            if model_review and model_review["review_status"] == "revise":
                risks.extend(str(item) for item in model_review["risk_flags"] or ["model_review_requested_revision"])
            risks = list(dict.fromkeys(risks))
            if risks:
                review = {"review_status": "revise", "confidence": model_review["confidence"] if model_review else 0.42, "risk_flags": risks, "safety_summary": model_review["safety_summary"] if model_review else "规则审核发现练习内容需要修订。"}
                return {"review_result": review, "needs_repair": True, "review_mode": "embedded_model_and_rules" if question_mode and model_review else "model_and_rules" if model_review else "rules_only"}, "练习内容需要修订。", "warning", review
            if model_review is None:
                review = {"review_status": "warning", "confidence": 0.62, "risk_flags": [], "safety_summary": "模型审核不可用，已完成题目、分数、引用和隐私规则审核。"}
                return {"review_result": review, "needs_repair": False, "review_mode": "rules_only"}, review["safety_summary"], "warning", review
            review = {**model_review, "review_status": "passed", "risk_flags": []}
            review_mode = "embedded_model_and_rules" if question_mode else "model_and_rules"
            return {"review_result": review, "needs_repair": False, "review_mode": review_mode}, "模型自审与确定性规则审核通过。" if question_mode else "ReviewAgent 审核通过。", "completed", review

        return self._run_node(state, "review", step_index, "审核题目或反馈的结构、分数与安全边界", work)

    def _model_review(
        self,
        state: AssessmentState,
        *,
        question_mode: bool,
        candidate: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any] | None:
        if self.service.model_service is None:
            return None
        payload_state = {**state, "questions": candidate} if question_mode and candidate is not None else state
        try:
            messages = [
                    {"role": "system", "content": "你是 AssessmentGraph 的 ReviewAgent。只输出 JSON，不得修改客观分数。" + china_first_content_policy.prompt_instruction()},
                    {
                        "role": "user",
                        "content": (
                            f"审核协议={ASSESSMENT_REVIEW_PROMPT_VERSION}。"
                            f"审核类型={'题目' if question_mode else '错因反馈'}。"
                            f"候选内容={json.dumps(self._safe_review_payload(payload_state, question_mode=question_mode), ensure_ascii=False)}。"
                            "返回 {\"review_status\":\"passed|revise\",\"confidence\":0.0,"
                            "\"risk_flags\":[],\"safety_summary\":\"\"}。"
                        ),
                    },
                ]
            task_call = getattr(self.service.model_service, "chat_completion_for_task", None)
            raw = (
                task_call(
                    state["user"],
                    messages,
                    ModelTaskProfile(
                        task_type="practice_review" if question_mode else "answer_review",
                        reasoning="disabled",
                        output_mode="json_object",
                        creativity="stable",
                        timeout_seconds=15.0,
                        max_attempts=1,
                    ),
                )
                if callable(task_call)
                else self.service.model_service.chat_completion(state["user"], messages)
            )
            return review_contract(parse_json_object(raw), default_summary="已完成练习结构、分数与隐私审核。")
        except Exception:
            return None

    @staticmethod
    def _review_route(state: AssessmentState) -> str:
        return "repair" if state.get("needs_repair") else "persist"

    def _model_questions(
        self,
        state: AssessmentState,
        *,
        revision_risks: list[str] | None = None,
        revision_questions: list[dict[str, Any]] | None = None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any] | None] | None:
        if self.service.model_service is None:
            return None
        drafts = list(state.get("deterministic_questions", []))
        prompt_rows = [
            {
                "id": item["id"],
                "question_type": item["question_type"],
                "knowledge_point_id": item["knowledge_point_id"],
                "knowledge_point_title": safe_text(item.get("knowledge_point_title"), limit=120),
                "source_excerpt": safe_text(item.get("source_excerpt"), limit=360),
                "prompt": safe_text(item["prompt"], limit=500),
                "options": safe_string_list(item["options"], limit=8, item_limit=180),
                "correct_answer": item.get("correct_answer"),
                "required_scope_term": safe_text(item.get("required_scope_term"), limit=80),
            }
            for item in drafts
        ]
        learner_context = state.get("learner_context")
        personalization = learner_context.prompt_summary() if learner_context is not None else {}
        instruction = "增强题干、干扰项和解析，但不得改变题目 ID、类型、知识点或规则答案。"
        try:
            messages = [
                    {"role": "system", "content": "你是 AssessmentGraph 出题 Agent。依据课程证据生成各不相同、可回答且干扰项合理的题目，只输出 JSON。" + china_first_content_policy.prompt_instruction()},
                    {
                        "role": "user",
                        "content": (
                            f"协议={ASSESSMENT_PROMPT_VERSION}，内嵌审核协议={ASSESSMENT_EMBEDDED_REVIEW_PROMPT_VERSION}。"
                            f"{instruction} 可信课程画像提示={personalization}。"
                            f"题目蓝图={json.dumps(prompt_rows, ensure_ascii=False, separators=(',', ':'))}。"
                            f"近期同知识点题目摘要={json.dumps(state.get('historical_question_summaries', []), ensure_ascii=False, separators=(',', ':'))}。"
                            "选择题必须保留正确答案原文并生成四个互不重复的合理选项；不同题目不得复用题面。"
                            "简答题题干必须原样点名蓝图中的 required_scope_term，不得改成‘一个维度’‘某个概念’等泛指；"
                            "题干允许的答案范围必须与锁定的 correct_answer 和评分量规完全一致。"
                            "每题必须另外输出 cognitive_level、scenario_type、target_misconception、reasoning_pattern；"
                            "不得复用历史题目的知识关系、场景和目标误区组合，也不得只替换名词。"
                            "生成后在同一次响应中自审重复题面、无效干扰项、证据缺失、隐私和答案合同；"
                            "发现风险时 review_status 必须为 revise。"
                            "返回 {\"questions\":[{\"id\":\"q1\",\"prompt\":\"\",\"options\":[],\"explanation\":\"\","
                            "\"cognitive_level\":\"understand|apply|analyze|create\",\"scenario_type\":\"\","
                            "\"target_misconception\":\"\",\"reasoning_pattern\":\"\"}],"
                            "\"quality_review\":{\"review_status\":\"passed|revise\",\"confidence\":0.0,"
                            "\"risk_flags\":[],\"safety_summary\":\"\"}}。"
                        ),
                    },
                ]
            if revision_risks:
                revision_guidance: list[str] = []
                for risk in revision_risks:
                    if risk.startswith("short_answer_answer_leakage"):
                        revision_guidance.append("删除简答题题干中的参考答案、结论和完整结构化数据，只保留作答对象、角度与任务要求")
                    elif risk.startswith("short_answer_scope_ambiguous"):
                        revision_guidance.append("在简答题题干中原样点名 required_scope_term，禁止使用泛指代词")
                    elif risk.startswith("missing_pedagogical_fingerprint"):
                        revision_guidance.append("补齐风险码点名的教学指纹字段，并保持其余已通过字段不变")
                    elif risk.startswith("reused_pedagogical_fingerprint"):
                        revision_guidance.append("改用不同的认知层级、场景、目标误区或推理方式组合")
                revision_rows = [
                    {
                        "id": item.get("id"),
                        "prompt": safe_text(item.get("prompt"), limit=800),
                        "options": safe_string_list(item.get("options"), limit=8, item_limit=240),
                        "explanation": safe_text(item.get("explanation"), limit=800),
                        "cognitive_level": safe_text(item.get("cognitive_level"), limit=40),
                        "scenario_type": safe_text(item.get("scenario_type"), limit=80),
                        "target_misconception": safe_text(item.get("target_misconception"), limit=120),
                        "reasoning_pattern": safe_text(item.get("reasoning_pattern"), limit=80),
                    }
                    for item in (revision_questions or [])
                ]
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "上一版题目="
                            f"{json.dumps(revision_rows, ensure_ascii=False, separators=(',', ':'))}。"
                            "以下字段未通过审核："
                            f"{','.join(revision_risks[:6])}。"
                            f"具体修订要求={'；'.join(dict.fromkeys(revision_guidance)) or '依据风险码修复失败项'}。"
                            "只修订失败项并重新输出完整 JSON；"
                            "所有未被点名的已通过字段必须逐字保留；"
                            "不得改变题目 ID、类型、知识点、规则答案和课程引用。"
                        ),
                    }
                )
            task_call = getattr(self.service.model_service, "chat_completion_for_task", None)
            completion_with_timeout = getattr(self.service.model_service, "chat_completion_with_timeout", None)
            raw = (
                task_call(
                    state["user"],
                    messages,
                    ModelTaskProfile(
                        task_type="practice_revision" if revision_risks else "practice_generation",
                        reasoning="disabled",
                        output_mode="json_object",
                        creativity="creative",
                        timeout_seconds=15.0 if revision_risks else OPTIONAL_GENERATION_TIMEOUT_SECONDS,
                        max_attempts=1,
                    ),
                )
                if callable(task_call)
                else completion_with_timeout(
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
            candidate.update(
                {
                    "cognitive_level": safe_text(model_item.get("cognitive_level"), limit=40),
                    "scenario_type": safe_text(model_item.get("scenario_type"), limit=80),
                    "target_misconception": safe_text(model_item.get("target_misconception"), limit=120),
                    "reasoning_pattern": safe_text(model_item.get("reasoning_pattern"), limit=80),
                }
            )
            options = safe_string_list(model_item.get("options"), limit=8, item_limit=240)
            if draft["question_type"] != "short_answer" and options:
                correct = draft.get("correct_answer")
                expected = [str(item) for item in correct] if isinstance(correct, list) else [str(correct)]
                if all(item in options for item in expected):
                    candidate["options"] = options
            enhanced.append(candidate)
        if enhanced == drafts:
            return None
        quality_review = review_contract(
            payload.get("quality_review") if isinstance(payload.get("quality_review"), dict) else None,
            default_summary="已完成题目结构、答案、引用和隐私自审。",
        )
        return enhanced, quality_review

    @staticmethod
    def _grading_item(question: dict[str, Any], answer_text: str) -> dict[str, Any]:
        return {
            "question_id": str(question.get("id") or ""),
            "question": question.get("prompt"),
            "knowledge_point": question.get("knowledge_point_title"),
            "student_answer": answer_text,
            "reference_answer": question.get("correct_answer"),
            "course_evidence": question.get("source_excerpt") or question.get("explanation"),
            "rubric": (
                "0-39：核心概念错误或与题目无关；40-59：有相关内容但关键关系错误或缺失；"
                "60-79：核心含义正确但存在遗漏；80-100：概念、关系和课程依据均准确。"
            ),
            "allowed_evidence_refs": list(question.get("citation_refs") or []),
        }

    @staticmethod
    def _semantic_evaluated(question: dict[str, Any], answer_text: str, grade: dict[str, Any]) -> EvaluatedAnswer:
        missing = [str(value) for value in grade.get("missing_concepts") or []]
        return EvaluatedAnswer(
            question=question,
            answer_text=answer_text,
            is_correct=bool(grade["is_correct"]),
            feedback={
                "score": int(grade["score"]),
                "grading_status": "model",
                "message": safe_text(grade.get("feedback"), limit=500),
                "matched_concepts": [str(value) for value in grade.get("matched_concepts") or []],
                "missing_concepts": missing,
                "confidence": float(grade.get("confidence") or 0.0),
                "evidence_refs": [str(value) for value in grade.get("evidence_refs") or []],
                "misconception": safe_text(grade.get("misconception"), limit=300),
                "matched_keywords": [],
                "missing_keywords": [],
                "explanation": str(question.get("explanation") or ""),
            },
        )

    @classmethod
    def _diagnosis_from_evaluation(cls, item: EvaluatedAnswer) -> dict[str, Any]:
        if item.feedback.get("grading_status") == "model":
            point = safe_text(item.question.get("knowledge_point_title") or "当前知识点", limit=120)
            return {
                "misconception": safe_text(item.feedback.get("misconception"), limit=300)
                or f"回答尚未完整说明{point}的关键关系。",
                "missing_concepts": [str(value) for value in item.feedback.get("missing_concepts") or []][:6],
                "recommended_action": safe_text(item.feedback.get("message"), limit=300)
                or f"复习{point}的课程证据后重新作答。",
                "confidence": clamp_confidence(item.feedback.get("confidence"), 0.6),
            }
        return cls._deterministic_diagnosis(item)

    @staticmethod
    def _grading_status(evaluated: list[EvaluatedAnswer]) -> str:
        graded = sum(1 for item in evaluated if item.feedback.get("score") is not None)
        if graded == len(evaluated):
            return "complete"
        return "partial" if graded else "ungraded"

    @staticmethod
    def _grading_status_from_rows(rows: list[PracticeAnswer]) -> str:
        submitted = [row for row in rows if row.answer_text is not None]
        graded = sum(1 for row in submitted if (row.feedback_json or {}).get("score") is not None)
        if submitted and graded == len(submitted):
            return "complete"
        return "partial" if graded else "ungraded"

    @staticmethod
    def _score_from_rows(rows: list[PracticeAnswer]) -> Decimal | None:
        scores = [int((row.feedback_json or {})["score"]) for row in rows if (row.feedback_json or {}).get("score") is not None]
        return Decimal(str(round(sum(scores) / len(scores)))) if scores else None

    def _run_post_grade_closure(
        self,
        user: User,
        session: PracticeSession,
        touched: dict[str, WeaknessReviewItem],
        trace_id: str,
    ) -> None:
        path_status = str((session.assessment_json or {}).get("path_update_status") or "not_started")
        path_trace_id = (session.assessment_json or {}).get("path_agent_trace_id")
        if self.service.path_service is not None:
            try:
                result = self.service.path_service.replan_after_assessment(user, int(session.course_id or 0), session.id)
                path_status = str(getattr(result, "status", "unchanged"))
                path_trace_id = getattr(result, "trace_id", None)
            except Exception:
                path_status = "failed"
        session.assessment_json = {
            **(session.assessment_json or {}),
            "path_update_status": path_status,
            "path_agent_trace_id": path_trace_id,
        }
        self.service.repository.commit()
        self.service.repository.refresh(session)
        if self.service.profile_service is None or not touched:
            return
        ingest = getattr(self.service.profile_service, "ingest_learning_signal", None)
        if callable(ingest):
            try:
                ingest(
                    user=user,
                    source_type="practice_assessment",
                    source_ref_type="practice_session",
                    source_ref_id=session.id,
                    suggested_updates={"weak_points": list(dict.fromkeys(item.title for item in touched.values()))[:5]},
                    course_id=int(session.course_id or 0),
                    parent_trace_id=trace_id,
                )
            except Exception:
                pass

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
                "question": safe_text(item.question.get("prompt"), limit=800),
                "correct_answer": item.question.get("correct_answer"),
                "standard_explanation": safe_text(item.question.get("explanation"), limit=800),
                "student_answer": safe_text(item.answer_text, limit=500),
                "missing_keywords": list(item.feedback.get("missing_keywords") or [])[:5],
                "source_excerpt": safe_text(item.question.get("source_excerpt"), limit=500),
                "score": int(item.feedback["score"]),
            }
            for item in wrong
        ]
        learner_context = state.get("learner_context")
        personalization = learner_context.prompt_summary() if learner_context is not None else {}
        try:
            messages = [
                    {"role": "system", "content": "你是 AssessmentGraph 错因诊断 Agent。逐题对照题干、正确答案、学生答案和课程证据诊断，不得修改分数，只输出 JSON。" + china_first_content_policy.prompt_instruction()},
                    {"role": "user", "content": f"协议={DIAGNOSIS_PROMPT_VERSION}。可信课程画像提示={personalization}。低分题={json.dumps(rows, ensure_ascii=False)}。每道题必须给出与本题直接相关且不重复套用的错因。返回 {{\"diagnoses\":[{{\"question_id\":\"q1\",\"misconception\":\"\",\"missing_concepts\":[],\"recommended_action\":\"\",\"confidence\":0.0}}]}}。"},
                ]
            task_call = getattr(self.service.model_service, "chat_completion_for_task", None)
            raw = (
                task_call(
                    state["user"],
                    messages,
                    ModelTaskProfile(
                        task_type="misconception_diagnosis",
                        reasoning="disabled",
                        output_mode="json_object",
                        creativity="stable",
                        timeout_seconds=20.0,
                        max_attempts=1,
                    ),
                )
                if callable(task_call)
                else self.service.model_service.chat_completion(state["user"], messages)
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
            if evaluated.feedback.get("score") is None or evaluated.feedback["score"] >= 60:
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
        normalized_prompts: list[str] = []
        historical = list(state.get("historical_question_summaries", []))
        historical_prompts = [
            "".join(safe_text(item.get("prompt"), limit=320).casefold().split())
            for item in historical
            if item.get("prompt")
        ]
        historical_fingerprints = {
            (
                safe_text(item.get("cognitive_level"), limit=40),
                safe_text(item.get("scenario_type"), limit=80),
                safe_text(item.get("target_misconception"), limit=120),
                safe_text(item.get("reasoning_pattern"), limit=80),
            )
            for item in historical
        }
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
            normalized_options = [" ".join(value.split()).casefold() for value in options]
            correct = question.get("correct_answer")
            expected = [str(value) for value in correct] if isinstance(correct, list) else ([str(correct)] if correct else [])
            if any(value not in options for value in expected) and question.get("question_type") != "short_answer":
                risks.append("correct_answer_missing")
            if question.get("question_type") != "short_answer" and (len(options) < 4 or len(normalized_options) != len(set(normalized_options))):
                risks.append("invalid_options")
            if any(value in {"无关概念", "跳过资料依据", "只背结论", "无关提示"} for value in options):
                risks.append("trivial_distractor")
            prompt = "".join(safe_text(question.get("prompt"), limit=800).casefold().split())
            required_scope = "".join(safe_text(draft.get("required_scope_term"), limit=80).casefold().split())
            if question.get("question_type") == "short_answer" and required_scope and required_scope not in prompt:
                risks.append("short_answer_scope_ambiguous")
            expected_short_answer = "".join(safe_text(draft.get("correct_answer"), limit=800).casefold().split())
            if (
                question.get("question_type") == "short_answer"
                and len(expected_short_answer) >= max(24, len(required_scope) + 8)
                and expected_short_answer in prompt
            ):
                risks.append("short_answer_answer_leakage")
            if len(prompt) < 12:
                risks.append("question_too_short")
            if any(SequenceMatcher(None, prompt, previous).ratio() >= 0.86 for previous in normalized_prompts):
                risks.append("duplicate_question")
            if any(SequenceMatcher(None, prompt, previous).ratio() >= 0.82 for previous in historical_prompts):
                risks.append("cross_batch_duplicate_question")
            normalized_prompts.append(prompt)
            fingerprint = (
                safe_text(question.get("cognitive_level"), limit=40),
                safe_text(question.get("scenario_type"), limit=80),
                safe_text(question.get("target_misconception"), limit=120),
                safe_text(question.get("reasoning_pattern"), limit=80),
            )
            missing_fingerprint_fields = [
                name
                for name, value in zip(
                    ("cognitive_level", "scenario_type", "target_misconception", "reasoning_pattern"),
                    fingerprint,
                    strict=True,
                )
                if not value or (name == "cognitive_level" and value not in {"understand", "apply", "analyze", "create"})
            ]
            if missing_fingerprint_fields:
                risks.append(
                    f"missing_pedagogical_fingerprint:{question_id}:{','.join(missing_fingerprint_fields)}"
                )
            elif fingerprint in historical_fingerprints:
                risks.append("reused_pedagogical_fingerprint")
            source_excerpt = safe_text(question.get("source_excerpt"), limit=500)
            if not source_excerpt:
                risks.append("missing_evidence")
            if contains_sensitive_text(
                {
                    "prompt": question.get("prompt"),
                    "options": question.get("options"),
                    "explanation": question.get("explanation"),
                }
            ):
                risks.append("sensitive_output")
        return list(dict.fromkeys(risks))

    @staticmethod
    def _safe_review_payload(state: AssessmentState, *, question_mode: bool) -> list[dict[str, Any]]:
        if question_mode:
            return [
                {
                    "id": item.get("id"),
                    "question_type": item.get("question_type"),
                    "knowledge_point": safe_text(item.get("knowledge_point_title"), limit=120),
                    "prompt": safe_text(item.get("prompt"), limit=800),
                    "options": safe_string_list(item.get("options"), limit=8, item_limit=240),
                    "correct_answer": item.get("correct_answer"),
                    "explanation": safe_text(item.get("explanation"), limit=800),
                    "source_excerpt": safe_text(item.get("source_excerpt"), limit=500),
                }
                for item in state.get("questions", [])
            ]
        return [
            {
                "question_id": str(item.question.get("id")),
                "question": safe_text(item.question.get("prompt"), limit=800),
                "correct_answer": item.question.get("correct_answer"),
                "student_answer": safe_text(item.answer_text, limit=500),
                "score": item.feedback.get("score"),
                "diagnosis": state.get("diagnoses", {}).get(str(item.question.get("id"))),
            }
            for item in state.get("evaluated", [])
            if item.feedback.get("score") is not None and int(item.feedback["score"]) < 60
        ]

    def _answer_risks(self, state: AssessmentState) -> list[str]:
        evaluated_by_id = {str(item.question.get("id")): item for item in state.get("evaluated", [])}
        risks: list[str] = []
        for row in state.get("answer_rows", []):
            question_id = str((row.question_json or {}).get("id"))
            evaluated = evaluated_by_id.get(question_id)
            if evaluated is None or row.answer_text is None:
                continue
            persisted_score = (row.feedback_json or {}).get("score")
            expected_score = evaluated.feedback.get("score")
            if persisted_score != expected_score:
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
                    label="练习生成节点失败",
                    progress_percent=min(95, step_index * 15),
                    status="failed",
                )
            raise
        self._record(state, agent_name, step_index, status, input_summary, output_summary, metadata, started)
        if job_context is not None:
            job_context.after_node(
                name=agent_name,
                label=input_summary,
                progress_percent=min(95, step_index * 15),
                status=status,
            )
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

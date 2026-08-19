from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from langgraph.graph import END, START, StateGraph

from backend.app.agents.assessment_contracts import (
    AssessmentState,
)
from backend.app.agents.assessment_evaluation import AssessmentEvaluationMixin
from backend.app.agents.assessment_generation import AssessmentGenerationMixin
from backend.app.agents.assessment_runtime import AssessmentRuntimeMixin
from backend.app.api.errors import make_trace_id
from backend.app.models import User
from backend.app.schemas.practice import PracticeSessionDetail, SubmitPracticeAnswerItem, session_to_api
from backend.app.services.model_execution import execution_context_for_state, model_execution_scope
from backend.app.services.practice import EvaluatedAnswer, PracticeService
from backend.app.services.semantic_grading import SemanticShortAnswerGrader


class AssessmentGraphRunner(AssessmentGenerationMixin, AssessmentEvaluationMixin, AssessmentRuntimeMixin):
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
        weakness_item_id: int | None = None,
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
            "weakness_item_id": weakness_item_id,
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
        by_question = {str(row.question_id or (row.question_json or {}).get("id")): row for row in rows}
        for item in evaluated:
            question_id = str(item.question.get("id"))
            row = by_question[question_id]
            diagnosis = diagnoses.get(question_id)
            if diagnosis:
                diagnosis = {**diagnosis, "evidence_ref": {"type": "practice_answer", "id": str(row.id)}}
            row.feedback_json = {**item.feedback, "diagnosis": diagnosis}
            row.is_correct = item.is_correct
        course = self.service._require_course(user, int(session.course_id or 0))
        assessment = session.assessment_json if isinstance(session.assessment_json, dict) else {}
        target_id = self.service._safe_int(assessment.get("targeted_weakness_id"))
        target_weakness = next(
            (
                item
                for item in self.service.repository.list_weakness_review_items(user.id, course.id)
                if target_id is not None and item.id == target_id
            ),
            None,
        )
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
            "target_weakness": target_weakness,
        }
        try:
            added, updated, recommended, touched = self._sync_weakness_items(state, by_question)
            all_evaluated = [
                EvaluatedAnswer(
                    question=dict(row.question_json or {}),
                    answer_text=str(row.answer_text or ""),
                    is_correct=row.is_correct,
                    feedback=dict(row.feedback_json or {}),
                )
                for row in rows
            ]
            target_update = self._apply_targeted_retest(state, all_evaluated, session)
            session.score = self._score_from_rows(rows)
            session.assessment_json = {
                **(session.assessment_json or {}),
                "grading_status": self._grading_status_from_rows(rows),
                "weaknesses_added": int((session.assessment_json or {}).get("weaknesses_added") or 0) + added,
                "weaknesses_updated": int((session.assessment_json or {}).get("weaknesses_updated") or 0) + updated,
                "recommended_resource_ids": list(dict.fromkeys([*(session.assessment_json or {}).get("recommended_resource_ids", []), *[str(value) for value in recommended]])),
                **target_update,
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

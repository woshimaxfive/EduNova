from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from time import perf_counter
from typing import Any

from backend.app.agents.assessment_contracts import (
    DIAGNOSIS_PROMPT_VERSION,
    AssessmentState,
)
from backend.app.agents.learning_review import (
    clamp_confidence,
    contains_sensitive_text,
    parse_json_object,
    safe_string_list,
    safe_text,
)
from backend.app.models import PracticeAnswer, PracticeSession, User, WeaknessReviewItem
from backend.app.providers.model_tasks import ModelTaskProfile
from backend.app.schemas.practice import session_to_api
from backend.app.services.content_locale import china_first_content_policy
from backend.app.services.learner_context import context_service_from_repository
from backend.app.services.mastery_progress import is_review_due
from backend.app.services.practice import EvaluatedAnswer, PracticeValidationError
from backend.app.services.semantic_grading import SemanticShortAnswerGrader


class AssessmentEvaluationMixin:
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
            assessment = session.assessment_json if isinstance(session.assessment_json, dict) else {}
            target_weakness_id = self.service._safe_int(assessment.get("targeted_weakness_id"))
            target_weakness = None
            if target_weakness_id is not None:
                target_weakness = next(
                    (
                        item
                        for item in self.service.repository.list_weakness_review_items(int(state["user_id"]), course.id)
                        if item.id == target_weakness_id and item.status in {"confirmed", "reviewing", "completed"}
                    ),
                    None,
                )
            return (
                {"session": session, "course": course, "course_id": course.id, "answer_rows": answer_rows, "questions": questions, "resources": resources, "learner_context": learner_context, "target_weakness": target_weakness},
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
            target_update = self._apply_targeted_retest(state, list(state.get("evaluated", [])), state["session"])
            return {"weaknesses_added": added, "weaknesses_updated": updated, "recommended_resource_ids": recommended, "touched_weaknesses": touched, "target_update": target_update}, f"新增 {added} 个弱点，更新 {updated} 个既有弱点。", "completed", {"weakness_count": added + updated, "targeted_retest": bool(target_update)}

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
                **dict(state.get("target_update") or {}),
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
            progress = item.diagnosis_json if isinstance(item.diagnosis_json, dict) else {}
            score = int(evaluated.feedback["score"])
            item.diagnosis_json = {
                **progress,
                "baseline_score": progress.get("baseline_score") if progress.get("baseline_score") is not None else score,
                "latest_score": score,
            }
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
            "baseline_score": previous.get("baseline_score"),
            "latest_score": previous.get("latest_score"),
            "attempt_count": int(previous.get("attempt_count") or 0),
            "practice_session_ids": list(previous.get("practice_session_ids") or [])[-8:],
            "last_practice_session_id": previous.get("last_practice_session_id"),
        }

    def _targeted_weakness(
        self,
        state: AssessmentState,
        course_id: int,
        selected_point_ids: set[int],
    ) -> WeaknessReviewItem | None:
        weakness_item_id = state.get("weakness_item_id")
        if weakness_item_id is None:
            return None
        item = next(
            (
                candidate
                for candidate in self.service.repository.list_weakness_review_items(int(state["user_id"]), course_id)
                if candidate.id == int(weakness_item_id)
            ),
            None,
        )
        if item is None:
            raise PracticeValidationError("待复习弱点不存在或当前用户无权访问。")
        if item.status not in {"confirmed", "reviewing"} and not is_review_due(item):
            raise PracticeValidationError("该薄弱点当前不能创建针对性练习。")
        if item.knowledge_point_id is None or item.knowledge_point_id not in selected_point_ids:
            raise PracticeValidationError("针对性练习的知识点必须与待复习弱点一致。")
        return item

    def _apply_targeted_retest(
        self,
        state: AssessmentState,
        evaluated: list[EvaluatedAnswer],
        session: PracticeSession,
    ) -> dict[str, Any]:
        item = state.get("target_weakness")
        if item is None or item.knowledge_point_id is None:
            return {}
        relevant = [
            answer
            for answer in evaluated
            if self.service._safe_int(answer.question.get("knowledge_point_id")) == item.knowledge_point_id
        ]
        if not relevant:
            return {}
        scores = [int(answer.feedback["score"]) for answer in relevant if answer.feedback.get("score") is not None]
        all_graded = len(scores) == len(relevant)
        latest_score = round(sum(scores) / len(scores)) if scores else None
        previous = item.diagnosis_json if isinstance(item.diagnosis_json, dict) else {}
        baseline_score = self.service._safe_int(previous.get("baseline_score"))
        if baseline_score is None:
            baseline_score = latest_score
        session_ids = [str(value) for value in previous.get("practice_session_ids") or []]
        session_id = str(session.id)
        if session_id not in session_ids:
            session_ids.append(session_id)
        passed = bool(all_graded and latest_score is not None and latest_score >= 80)
        now = datetime.now(UTC)
        item.status = "completed" if passed else "reviewing"
        item.next_review_at = now + timedelta(days=7 if passed else 3)
        item.updated_at = now
        item.diagnosis_json = {
            **previous,
            "baseline_score": baseline_score,
            "latest_score": latest_score,
            "attempt_count": len(session_ids),
            "practice_session_ids": session_ids[-8:],
            "last_practice_session_id": session_id,
        }
        return {
            "targeted_weakness_id": str(item.id),
            "targeted_weakness_status": item.status,
            "targeted_weakness_improvement": (
                latest_score - baseline_score
                if latest_score is not None and baseline_score is not None
                else None
            ),
            "targeted_weakness_passed": passed,
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

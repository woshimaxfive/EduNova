from __future__ import annotations

from difflib import SequenceMatcher
import json
import re
from datetime import UTC, datetime, timedelta
from time import perf_counter
from typing import Any

from backend.app.agents.assessment_contracts import (
    ASSESSMENT_EMBEDDED_REVIEW_PROMPT_VERSION,
    ASSESSMENT_PROMPT_VERSION,
    ASSESSMENT_REVIEW_PROMPT_VERSION,
    OPTIONAL_GENERATION_TIMEOUT_SECONDS,
    PRACTICE_REVISION_TIMEOUT_SECONDS,
    AssessmentState,
)
from backend.app.agents.learning_review import (
    contains_sensitive_text,
    parse_json_object,
    review_contract,
    safe_string_list,
    safe_text,
)
from backend.app.models import PracticeAnswer, PracticeSession
from backend.app.providers.model_tasks import ModelTaskProfile
from backend.app.schemas.practice import session_to_api
from backend.app.services.content_locale import china_first_content_policy
from backend.app.services.learner_context import context_service_from_repository
from backend.app.services.practice import PracticeGenerationError, PracticeValidationError


class AssessmentGenerationMixin:
    def _create_context_node(self, state: AssessmentState) -> dict[str, Any]:
        def work() -> tuple[dict[str, Any], str, str, dict[str, Any]]:
            course = self.service._require_course(state["user"], int(state["course_id"]))
            points = self.service.repository.list_knowledge_points(course.id)
            selected = self.service._select_points(points, list(state.get("knowledge_point_ids", [])))
            resources = self.service.repository.list_generated_resources(int(state["user_id"]), course.id)
            chunks = self.service.repository.list_knowledge_chunks(course.id)
            if not selected:
                raise PracticeValidationError("当前课程还没有可用于生成练习的知识点。")
            effective_difficulty = self.service.resolve_difficulty(state["user"], course.id, selected, str(state.get("requested_difficulty") or state["difficulty"]))
            context_service = context_service_from_repository(self.service.repository)
            learner_context = context_service.course_context(int(state["user_id"]), course.id) if context_service is not None else None
            selected_ids = {point.id for point in selected}
            target_weakness = self._targeted_weakness(state, course.id, selected_ids)
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
                    "target_weakness": target_weakness,
                    "historical_question_summaries": historical_question_summaries,
                },
                f"已选择 {len(selected)} 个知识点和 {len(resources)} 个课程资源。",
                "completed",
                {
                    "knowledge_point_id": selected[0].id if len(selected) == 1 else None,
                    "resource_count": len(resources),
                    "requested_difficulty": state.get("requested_difficulty"),
                    "effective_difficulty": effective_difficulty,
                    "targeted_weakness_id": target_weakness.id if target_weakness is not None else None,
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
        redacted_questions = self._redact_revised_short_answer_leakage(
            state,
            list(state.get("questions", [])),
        )
        remaining_after_redaction = self._question_risks(state, redacted_questions)
        if not remaining_after_redaction:
            return {
                "questions": redacted_questions,
                "generation_mode": "model_generated",
                "generation_review": state.get("generation_review"),
                "review_result": {
                    "review_status": "passed",
                    "confidence": 0.78,
                    "risk_flags": [],
                    "safety_summary": "已对模型题干中的锁定参考答案执行精确脱敏，并通过完整题目合同审核。",
                },
                "review_mode": "embedded_model_and_rules",
                "needs_repair": False,
                "repair_count": 1,
            }
        risks = remaining_after_redaction
        generated = self._model_questions(
            {**state, "questions": redacted_questions},
            revision_risks=risks,
            revision_questions=redacted_questions,
        )
        if generated is None:
            raise PracticeValidationError(
                f"AI练习题未通过质量审核，单次修订失败，未创建练习。风险：{'、'.join(risks) or '结构不完整'}"
            )
        questions, generation_review = generated
        questions = self._redact_revised_short_answer_leakage(state, questions)
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

    @classmethod
    def _redact_revised_short_answer_leakage(
        cls,
        state: AssessmentState,
        questions: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Remove an exact locked answer copied into a model-authored short-answer prompt.

        This safety redaction runs before an optional model repair and again after it.
        It is not a deterministic question fallback: all remaining wording stays
        model-authored and `_question_risks` reviews the complete contract again.
        """
        drafts = {
            str(item.get("id")): item
            for item in state.get("deterministic_questions", [])
            if isinstance(item, dict)
        }
        redacted: list[dict[str, Any]] = []
        for question in questions:
            draft = drafts.get(str(question.get("id")))
            if draft is None or question.get("question_type") != "short_answer":
                redacted.append(question)
                continue
            expected = safe_text(draft.get("correct_answer"), limit=800)
            scope = safe_text(draft.get("required_scope_term"), limit=80)
            prompt = safe_text(question.get("prompt"), limit=800)
            sanitized = cls._replace_normalized_span(prompt, expected, scope)
            sanitized = cls._keep_single_normalized_term(sanitized, scope, "该概念")
            sanitized = re.sub(
                r"要求回答中必须包含对以下概念的直接阐释\s*[：:]\s*[。；;]?",
                "",
                sanitized,
            ).strip()
            if not scope:
                sanitized = re.sub(
                    r"(?:要求回答中必须体现|答案必须包含)\s*[：:]?\s*[‘’“”\"']*\s*[。；;]?",
                    "",
                    sanitized,
                ).strip()
            if sanitized == prompt:
                redacted.append(question)
                continue
            quality = dict(question.get("quality") or {})
            quality["answer_leakage_redacted"] = True
            redacted.append({**question, "prompt": sanitized, "quality": quality})
        return redacted

    @staticmethod
    def _replace_normalized_span(text: str, needle: str, replacement: str) -> str:
        normalized_chars: list[str] = []
        source_indexes: list[int] = []
        for index, char in enumerate(text):
            if char.isspace():
                continue
            normalized_chars.append(char.casefold())
            source_indexes.append(index)
        normalized_needle = "".join(char.casefold() for char in needle if not char.isspace())
        if not normalized_needle:
            return text
        start = "".join(normalized_chars).find(normalized_needle)
        if start < 0:
            return text
        source_start = source_indexes[start]
        source_end = source_indexes[start + len(normalized_needle) - 1] + 1
        return f"{text[:source_start]}{replacement}{text[source_end:]}"

    @classmethod
    def _keep_single_normalized_term(cls, text: str, term: str, replacement: str) -> str:
        normalized_term = "".join(char.casefold() for char in term if not char.isspace())
        if not normalized_term:
            return text
        result = text
        while True:
            normalized = "".join(char.casefold() for char in result if not char.isspace())
            first = normalized.find(normalized_term)
            second = normalized.find(normalized_term, first + len(normalized_term)) if first >= 0 else -1
            if second < 0:
                return result
            prefix_chars = 0
            source_start = 0
            for index, char in enumerate(result):
                if not char.isspace():
                    if prefix_chars == second:
                        source_start = index
                        break
                    prefix_chars += 1
            source_end = source_start
            consumed = 0
            while source_end < len(result) and consumed < len(normalized_term):
                if not result[source_end].isspace():
                    consumed += 1
                source_end += 1
            result = f"{result[:source_start]}{replacement}{result[source_end:]}"

    def _create_persist_node(self, state: AssessmentState) -> dict[str, Any]:
        job_context = state.get("job_context")
        if job_context is not None:
            job_context.before_node("persist", "保存审核通过的练习")
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
                "targeted_weakness_id": state["target_weakness"].id if state.get("target_weakness") is not None else None,
                "targeted_weakness_title": state["target_weakness"].title if state.get("target_weakness") is not None else None,
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
                    "option_ids": [chr(ord("A") + index) for index, _ in enumerate(question.get("options") or [])],
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
                    question_id=str(question["id"]),
                    question_json=question,
                    answer_text=None,
                    feedback_json={},
                    is_correct=None,
                    created_at=now,
                )
                for question in persisted_questions
            ]
            target_weakness = state.get("target_weakness")
            if target_weakness is not None and target_weakness.status == "completed":
                target_weakness.status = "reviewing"
                target_weakness.next_review_at = now + timedelta(days=3)
                target_weakness.updated_at = now
            self.service.repository.replace_answers_for_session(session.id, placeholders)
            if job_context is not None:
                job_context.check_cancelled()
            self.service.repository.commit()
            self.service.repository.refresh(session)
            detail = session_to_api(session, self.service.repository.list_answers_for_session(session.id))
        except Exception as exc:
            self.service.repository.rollback()
            self._record_failure(state, "persist", 6, "保存审核通过的练习题", exc, started)
            raise
        self._record(state, "persist", 6, "completed", "保存审核通过的练习题", f"已保存 {len(detail.questions)} 道题。", {"artifact_id": str(session.id), "repair_count": int(state.get("repair_count") or 0)}, started)
        return {"session": session, "detail": detail}

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
            raw = self.service.model_service.chat_completion_for_task(
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
                "replace_distractors": item.get("question_type") != "short_answer",
            }
            for item in drafts
        ]
        learner_context = state.get("learner_context")
        personalization = learner_context.prompt_summary() if learner_context is not None else {}
        target_weakness = state.get("target_weakness")
        target_diagnosis = target_weakness.diagnosis_json if target_weakness is not None and isinstance(target_weakness.diagnosis_json, dict) else {}
        target_context = (
            {
                "title": safe_text(target_weakness.title, limit=120),
                "misconception": safe_text(target_diagnosis.get("misconception"), limit=300),
                "missing_concepts": safe_string_list(target_diagnosis.get("missing_concepts"), limit=6, item_limit=100),
                "recommended_action": safe_text(target_diagnosis.get("recommended_action"), limit=300),
            }
            if target_weakness is not None
            else None
        )
        instruction = "增强题干、干扰项和解析，但不得改变题目 ID、类型、知识点或规则答案。"
        try:
            messages = [
                    {"role": "system", "content": "你是 AssessmentGraph 出题 Agent。依据课程证据生成各不相同、可回答且干扰项合理的题目，只输出 JSON。" + china_first_content_policy.prompt_instruction()},
                    {
                        "role": "user",
                        "content": (
                            f"协议={ASSESSMENT_PROMPT_VERSION}，内嵌审核协议={ASSESSMENT_EMBEDDED_REVIEW_PROMPT_VERSION}。"
                            f"{instruction} 可信课程画像提示={personalization}。"
                            f"针对性复习目标={json.dumps(target_context, ensure_ascii=False, separators=(',', ':')) if target_context else '无'}。"
                            f"题目蓝图={json.dumps(prompt_rows, ensure_ascii=False, separators=(',', ':'))}。"
                            f"近期同知识点题目摘要={json.dumps(state.get('historical_question_summaries', []), ensure_ascii=False, separators=(',', ':'))}。"
                            "选择题必须保留正确答案原文并生成四个互不重复的合理选项；不同题目不得复用题面。"
                            "蓝图中的非正确选项只是安全占位符，必须全部替换为与当前学科相关、表面合理但能被课程证据排除的真实误区；"
                            "禁止输出‘只复述’‘与课程证据无关’‘完整解释’‘适用于所有情境’等审核式元话语。"
                            "简答题题干必须原样点名蓝图中的 required_scope_term，不得改成‘一个维度’‘某个概念’等泛指；"
                            "required_scope_term 在简答题题干中只出现一次，禁止形成‘解释 X 在 X 中的作用’式循环问法；"
                            "题干允许的答案范围必须与锁定的 correct_answer 和评分量规完全一致。"
                            "每题必须另外输出 cognitive_level、scenario_type、target_misconception、reasoning_pattern；"
                            "不得复用历史题目的知识关系、场景和目标误区组合，也不得只替换名词。"
                            "存在针对性复习目标时，每道题必须围绕其错因或缺失概念验证是否真正掌握，不得改成泛化知识回忆。"
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
                        revision_guidance.append(
                            "仅重写风险码冒号后题号对应的简答题题干；只保留一次 required_scope_term、作答角度与任务要求，"
                            "不得包含 correct_answer 中除 required_scope_term 外连续 12 个以上字符"
                        )
                    elif risk.startswith("short_answer_scope_ambiguous"):
                        revision_guidance.append("在简答题题干中原样点名 required_scope_term，禁止使用泛指代词")
                    elif risk.startswith("short_answer_circular_scope"):
                        revision_guidance.append("让 required_scope_term 只出现一次，改为询问其含义、条件、关系或具体应用")
                    elif risk.startswith("placeholder_distractor"):
                        revision_guidance.append("将审核式占位干扰项替换为当前学科中表面合理、但可由课程证据排除的具体误区")
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
                            "风险码冒号后的 qN 是失败题号；只允许改写这些题目的失败字段，其他题目必须逐字保留。"
                            "只返回失败题目和 quality_review，不要重复输出其他已通过题目；"
                            "不得改变题目 ID、类型、知识点、规则答案和课程引用。"
                        ),
                    }
                )
            raw = self.service.model_service.chat_completion_for_task(
                state["user"],
                messages,
                ModelTaskProfile(
                    task_type="practice_revision" if revision_risks else "practice_generation",
                    reasoning="disabled",
                    output_mode="json_object",
                    creativity="creative",
                    timeout_seconds=PRACTICE_REVISION_TIMEOUT_SECONDS if revision_risks else OPTIONAL_GENERATION_TIMEOUT_SECONDS,
                    max_attempts=1,
                ),
            )
        except Exception:
            return None
        payload = parse_json_object(raw)
        if payload is None or not isinstance(payload.get("questions"), list):
            return None
        by_id = {str(item.get("id")): item for item in payload["questions"] if isinstance(item, dict)}
        all_ids = {str(item["id"]) for item in drafts}
        failed_ids = {
            part
            for risk in (revision_risks or [])
            for part in risk.split(":")[1:]
            if part in all_ids
        }
        allowed_response_id_sets = {frozenset(all_ids)}
        if revision_risks and failed_ids:
            allowed_response_id_sets.add(frozenset(failed_ids))
        if frozenset(by_id) not in allowed_response_id_sets:
            return None
        previous_by_id = {
            str(item.get("id")): item
            for item in (revision_questions or [])
            if isinstance(item, dict) and str(item.get("id")) in all_ids
        }
        enhanced: list[dict[str, Any]] = []
        for draft in drafts:
            model_item = by_id.get(str(draft["id"])) or previous_by_id.get(str(draft["id"]))
            if model_item is None:
                return None
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
            placeholder_markers = ("只复述", "课程证据无关", "完整解释", "适用于所有情境", "忽略其适用范围")
            if any(any(marker in value for marker in placeholder_markers) for value in options):
                risks.append("placeholder_distractor")
            raw_prompt = safe_text(question.get("prompt"), limit=800)
            prompt = "".join(raw_prompt.casefold().split())
            if re.search(r"[：:]\s*[‘’“”\"']{2}\s*[。；;]?", raw_prompt):
                risks.append(f"empty_required_scope:{question_id}")
            required_scope = "".join(safe_text(draft.get("required_scope_term"), limit=80).casefold().split())
            if question.get("question_type") == "short_answer" and required_scope and required_scope not in prompt:
                risks.append(f"short_answer_scope_ambiguous:{question_id}")
            if question.get("question_type") == "short_answer" and required_scope and prompt.count(required_scope) > 1:
                risks.append(f"short_answer_circular_scope:{question_id}")
            expected_short_answer = "".join(safe_text(draft.get("correct_answer"), limit=800).casefold().split())
            if (
                question.get("question_type") == "short_answer"
                and len(expected_short_answer) >= max(24, len(required_scope) + 8)
                and expected_short_answer in prompt
            ):
                risks.append(f"short_answer_answer_leakage:{question_id}")
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

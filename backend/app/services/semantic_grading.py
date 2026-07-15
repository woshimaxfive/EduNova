from __future__ import annotations

import json
import logging
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from backend.app.agents.learning_review import contains_sensitive_text, parse_json_object, safe_text
from backend.app.models import User
from backend.app.services.content_locale import china_first_content_policy


logger = logging.getLogger(__name__)


class GradingModelService(Protocol):
    def chat_completion(self, user: User, messages: list[dict[str, str]]) -> str: ...


class ShortAnswerGrade(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: str = Field(min_length=1, max_length=80)
    score: int = Field(ge=0, le=100)
    is_correct: bool | None = None
    matched_concepts: list[str] = Field(default_factory=list, max_length=8)
    missing_concepts: list[str] = Field(default_factory=list, max_length=8)
    misconception: str = Field(default="", max_length=300)
    feedback: str = Field(min_length=1, max_length=500)
    evidence_refs: list[str] = Field(default_factory=list, max_length=6)
    confidence: float = Field(ge=0, le=1)


class ShortAnswerGradeBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    grades: list[ShortAnswerGrade]


class SemanticShortAnswerGrader:
    prompt_version = "short-answer-grading-v1"

    def __init__(self, model_service: GradingModelService | None) -> None:
        self.model_service = model_service
        self.failure_reason: str | None = None

    def grade(
        self,
        *,
        user: User,
        items: list[dict[str, Any]],
    ) -> dict[str, dict[str, Any]] | None:
        self.failure_reason = None
        if self.model_service is None or not items:
            self.failure_reason = "model_unavailable" if self.model_service is None else "empty_batch"
            return None
        safe_items = [self._safe_item(item) for item in items]
        try:
            raw = self.model_service.chat_completion(
                user,
                [
                    {
                        "role": "system",
                        "content": (
                            "你是 EduNova 简答题评分器。依据题目、参考答案、明确量规和课程证据进行语义评分，"
                            "不能用关键词出现次数代替理解判断。只输出 JSON，不得修改题目、课程证据或客观题结果。"
                            + china_first_content_policy.prompt_instruction()
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"协议={self.prompt_version}。待评分题={json.dumps(safe_items, ensure_ascii=False)}。"
                            "逐题返回 grades；score 为 0-100，is_correct 通常以 60 分为界；"
                            "matched_concepts、missing_concepts、misconception、feedback 必须基于当前题；"
                            "evidence_refs 只能从该题 allowed_evidence_refs 中选择。"
                            "结构：{\"grades\":[{\"question_id\":\"q1\",\"score\":0,"
                            "\"is_correct\":false,\"matched_concepts\":[],\"missing_concepts\":[],"
                            "\"misconception\":\"\",\"feedback\":\"\",\"evidence_refs\":[],\"confidence\":0.0}]}。"
                        ),
                    },
                ],
            )
        except Exception:
            self.failure_reason = "provider_error"
            logger.warning("semantic_short_answer_grading_failed reason=%s", self.failure_reason)
            return None
        payload = parse_json_object(raw)
        if payload is None:
            self.failure_reason = "invalid_json"
            logger.warning("semantic_short_answer_grading_failed reason=%s", self.failure_reason)
            return None
        try:
            batch = ShortAnswerGradeBatch.model_validate(payload)
        except ValueError as exc:
            errors = getattr(exc, "errors", lambda: [])()
            error_codes = sorted(
                {
                    f"{'.'.join(str(part) for part in error.get('loc') or ())}:{error.get('type') or 'validation_error'}"
                    for error in errors
                }
            )
            self.failure_reason = "schema_invalid:" + ",".join(error_codes[:4])
            logger.warning("semantic_short_answer_grading_failed reason=%s", self.failure_reason)
            return None
        expected = {str(item["question_id"]): item for item in safe_items}
        if len(batch.grades) != len(expected):
            self.failure_reason = "grade_count_mismatch"
            logger.warning("semantic_short_answer_grading_failed reason=%s", self.failure_reason)
            return None
        result: dict[str, dict[str, Any]] = {}
        for grade in batch.grades:
            if grade.question_id not in expected or grade.question_id in result:
                self.failure_reason = "question_id_mismatch"
                logger.warning("semantic_short_answer_grading_failed reason=%s", self.failure_reason)
                return None
            allowed_refs = set(expected[grade.question_id]["allowed_evidence_refs"])
            if any(ref not in allowed_refs for ref in grade.evidence_refs):
                self.failure_reason = "invalid_evidence_ref"
                logger.warning("semantic_short_answer_grading_failed reason=%s", self.failure_reason)
                return None
            if any(len(value) > 120 for value in [*grade.matched_concepts, *grade.missing_concepts]):
                self.failure_reason = "concept_too_long"
                logger.warning("semantic_short_answer_grading_failed reason=%s", self.failure_reason)
                return None
            value = grade.model_dump()
            if grade.is_correct != (grade.score >= 60):
                logger.info("semantic_short_answer_correctness_normalized question_id=%s", grade.question_id)
            value["is_correct"] = grade.score >= 60
            if contains_sensitive_text(value):
                self.failure_reason = "sensitive_output"
                logger.warning("semantic_short_answer_grading_failed reason=%s", self.failure_reason)
                return None
            result[grade.question_id] = value
        if set(result) != set(expected):
            self.failure_reason = "question_id_set_mismatch"
            logger.warning("semantic_short_answer_grading_failed reason=%s", self.failure_reason)
            return None
        return result

    @staticmethod
    def _safe_item(item: dict[str, Any]) -> dict[str, Any]:
        return {
            "question_id": safe_text(item.get("question_id"), limit=80),
            "question": safe_text(item.get("question"), limit=800),
            "knowledge_point": safe_text(item.get("knowledge_point"), limit=120),
            "student_answer": safe_text(item.get("student_answer"), limit=2000),
            "reference_answer": safe_text(item.get("reference_answer"), limit=1000),
            "course_evidence": safe_text(item.get("course_evidence"), limit=1200),
            "rubric": safe_text(item.get("rubric"), limit=1000),
            "allowed_evidence_refs": [safe_text(value, limit=80) for value in item.get("allowed_evidence_refs", [])][:6],
        }

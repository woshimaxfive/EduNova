from __future__ import annotations

from typing import Any, TypedDict

from backend.app.models import PracticeAnswer, PracticeSession, User, WeaknessReviewItem
from backend.app.schemas.practice import PracticeSessionDetail, SubmitPracticeAnswerItem
from backend.app.services.practice import EvaluatedAnswer


ASSESSMENT_PROMPT_VERSION = "assessment-v3.3"
ASSESSMENT_REVIEW_PROMPT_VERSION = "assessment-review-v3.1"
ASSESSMENT_EMBEDDED_REVIEW_PROMPT_VERSION = "assessment-review-v3.2-embedded"
DIAGNOSIS_PROMPT_VERSION = "diagnosis-v3.1"
OPTIONAL_GENERATION_TIMEOUT_SECONDS = 40.0
PRACTICE_REVISION_TIMEOUT_SECONDS = 5.0


class AssessmentState(TypedDict, total=False):
    trace_id: str
    job_context: Any
    operation: str
    user: User
    user_id: int
    course_id: int
    session_id: int
    knowledge_point_ids: list[int]
    weakness_item_id: int | None
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
    target_weakness: WeaknessReviewItem | None
    historical_question_summaries: list[dict[str, Any]]
    deterministic_questions: list[dict[str, Any]]
    questions: list[dict[str, Any]]
    session: PracticeSession
    answer_rows: list[PracticeAnswer]
    evaluated: list[EvaluatedAnswer]
    score: int | None
    diagnoses: dict[str, dict[str, Any]]
    touched_weaknesses: dict[str, WeaknessReviewItem]
    target_update: dict[str, Any]
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

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from backend.app.models import PracticeAnswer, PracticeSession


PracticeDifficulty = Literal["easy", "medium", "hard", "adaptive"]
PracticeQuestionType = Literal["single_choice", "multiple_choice", "short_answer"]


class CreatePracticeSessionRequest(BaseModel):
    course_id: int
    knowledge_point_ids: list[int] = Field(default_factory=list)
    question_count: int = Field(default=5, ge=1, le=12)
    difficulty: PracticeDifficulty = "medium"


class SubmitPracticeAnswerItem(BaseModel):
    question_id: str
    answer_text: str = Field(max_length=2000)

    @field_validator("answer_text")
    @classmethod
    def normalize_answer(cls, value: str) -> str:
        return " ".join(value.split())[:2000]


class SubmitPracticeAnswersRequest(BaseModel):
    answers: list[SubmitPracticeAnswerItem] = Field(min_length=1)


class SavePracticeDraftRequest(BaseModel):
    answers: list[SubmitPracticeAnswerItem] = Field(default_factory=list)


class PracticeQuestion(BaseModel):
    id: str
    question_type: PracticeQuestionType
    knowledge_point_id: str | None
    knowledge_point_title: str
    prompt: str
    options: list[str]
    correct_answer: str | list[str] | None
    keywords: list[str]
    explanation: str
    difficulty: str
    citation_refs: list[str] = Field(default_factory=list)
    generation_mode: str = "deterministic_source"
    prompt_version: str = "legacy"
    quality: dict[str, Any] = Field(default_factory=dict)


class PracticeFeedback(BaseModel):
    score: int | None
    grading_status: Literal["deterministic", "model", "ungraded"]
    message: str
    matched_concepts: list[str] = Field(default_factory=list)
    missing_concepts: list[str] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0, le=1)
    matched_keywords: list[str]
    missing_keywords: list[str]
    explanation: str
    diagnosis: "PracticeDiagnosis | None" = None


class PracticeEvidenceRef(BaseModel):
    type: Literal["practice_answer"] = "practice_answer"
    id: str


class PracticeDiagnosis(BaseModel):
    misconception: str
    missing_concepts: list[str]
    recommended_action: str
    confidence: float = Field(ge=0, le=1)
    evidence_ref: PracticeEvidenceRef


class PracticeClosureUpdate(BaseModel):
    weaknesses_added: int = 0
    weaknesses_updated: int = 0
    path_update_status: Literal["not_started", "replanned", "unchanged", "failed"] = "not_started"
    path_agent_trace_id: str | None = None
    recommended_resource_ids: list[str] = Field(default_factory=list)


class PracticeAnswerResponse(BaseModel):
    question_id: str
    answer_text: str | None
    is_correct: bool | None
    feedback: PracticeFeedback


class PracticeSessionDetail(BaseModel):
    id: str
    course_id: str
    title: str
    status: str
    agent_trace_id: str | None = None
    score: int | None
    grading_status: Literal["complete", "partial", "ungraded"] = "ungraded"
    requested_difficulty: PracticeDifficulty = "medium"
    effective_difficulty: Literal["easy", "medium", "hard"] = "medium"
    draft_saved_at: str | None = None
    questions: list[PracticeQuestion]
    answers: list[PracticeAnswerResponse]
    closure_update: PracticeClosureUpdate | None = None
    created_at: str
    updated_at: str


class PracticeSessionSummary(BaseModel):
    id: str
    course_id: str
    title: str
    status: str
    score: int | None
    grading_status: Literal["complete", "partial", "ungraded"] = "ungraded"
    effective_difficulty: Literal["easy", "medium", "hard"] = "medium"
    created_at: str
    updated_at: str


def iso_timestamp(value: datetime | None) -> str | None:
    if value is None:
        return None
    timestamp = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    timestamp = timestamp.astimezone(UTC).replace(microsecond=0)
    return timestamp.isoformat().replace("+00:00", "Z")


def session_to_api(session: PracticeSession, answers: list[PracticeAnswer]) -> PracticeSessionDetail:
    questions = [
        PracticeQuestion(**public_question(item, reveal_answer=session.status == "completed"))
        for item in (session_questions(session, answers) or [])
    ]
    answer_items = [answer_to_api(answer) for answer in answers if answer.answer_text is not None or answer.is_correct is not None]
    assessment = session.assessment_json if isinstance(getattr(session, "assessment_json", None), dict) else {}
    requested_difficulty = str(assessment.get("requested_difficulty") or assessment.get("difficulty") or "medium")
    if requested_difficulty not in {"easy", "medium", "hard", "adaptive"}:
        requested_difficulty = "medium"
    effective_difficulty = str(assessment.get("effective_difficulty") or ("medium" if requested_difficulty == "adaptive" else requested_difficulty))
    if effective_difficulty not in {"easy", "medium", "hard"}:
        effective_difficulty = "medium"
    return PracticeSessionDetail(
        id=str(session.id),
        course_id=str(session.course_id),
        title=session.title,
        status=session.status,
        agent_trace_id=getattr(session, "agent_trace_id", None),
        score=int(session.score) if session.score is not None else None,
        grading_status=_session_grading_status(session, answers),
        requested_difficulty=requested_difficulty,
        effective_difficulty=effective_difficulty,
        draft_saved_at=str(assessment.get("draft_saved_at")) if assessment.get("draft_saved_at") else None,
        questions=questions,
        answers=answer_items,
        closure_update=_closure_update(getattr(session, "assessment_json", None)),
        created_at=iso_timestamp(session.created_at) or "",
        updated_at=iso_timestamp(session.updated_at) or "",
    )


def session_to_summary(session: PracticeSession) -> PracticeSessionSummary:
    assessment = session.assessment_json if isinstance(getattr(session, "assessment_json", None), dict) else {}
    effective_difficulty = str(assessment.get("effective_difficulty") or assessment.get("difficulty") or "medium")
    if effective_difficulty not in {"easy", "medium", "hard"}:
        effective_difficulty = "medium"
    return PracticeSessionSummary(
        id=str(session.id),
        course_id=str(session.course_id),
        title=session.title,
        status=session.status,
        score=int(session.score) if session.score is not None else None,
        grading_status=_summary_grading_status(session),
        effective_difficulty=effective_difficulty,
        created_at=iso_timestamp(session.created_at) or "",
        updated_at=iso_timestamp(session.updated_at) or "",
    )


def session_questions(session: PracticeSession, answers: list[PracticeAnswer]) -> list[dict]:
    metadata = getattr(session, "metadata_json", None)
    if isinstance(metadata, dict) and isinstance(metadata.get("questions"), list):
        return metadata["questions"]
    return [answer.question_json for answer in answers if isinstance(answer.question_json, dict)]


def public_question(question: dict, *, reveal_answer: bool = False) -> dict:
    return {**question, "correct_answer": question.get("correct_answer") if reveal_answer else None}


def answer_to_api(answer: PracticeAnswer) -> PracticeAnswerResponse:
    feedback = answer.feedback_json or {}
    return PracticeAnswerResponse(
        question_id=str((answer.question_json or {}).get("id") or ""),
        answer_text=answer.answer_text,
        is_correct=answer.is_correct,
        feedback=PracticeFeedback(
            score=int(feedback["score"]) if feedback.get("score") is not None else None,
            grading_status=str(feedback.get("grading_status") or ("deterministic" if feedback.get("score") is not None else "ungraded")),
            message=str(feedback.get("message") or ""),
            matched_concepts=[str(item) for item in feedback.get("matched_concepts") or []],
            missing_concepts=[str(item) for item in feedback.get("missing_concepts") or []],
            confidence=float(feedback["confidence"]) if feedback.get("confidence") is not None else None,
            matched_keywords=[str(item) for item in feedback.get("matched_keywords") or []],
            missing_keywords=[str(item) for item in feedback.get("missing_keywords") or []],
            explanation=str(feedback.get("explanation") or ""),
            diagnosis=_diagnosis(feedback.get("diagnosis")),
        ),
    )


def _session_grading_status(session: PracticeSession, answers: list[PracticeAnswer]) -> str:
    assessment = session.assessment_json if isinstance(session.assessment_json, dict) else {}
    stored = str(assessment.get("grading_status") or "")
    if stored in {"complete", "partial", "ungraded"}:
        return stored
    submitted = [answer for answer in answers if answer.answer_text is not None]
    graded = sum(1 for answer in submitted if (answer.feedback_json or {}).get("score") is not None)
    if submitted and graded == len(submitted):
        return "complete"
    return "partial" if graded else "ungraded"


def _summary_grading_status(session: PracticeSession) -> str:
    assessment = session.assessment_json if isinstance(session.assessment_json, dict) else {}
    stored = str(assessment.get("grading_status") or "")
    if stored in {"complete", "partial", "ungraded"}:
        return stored
    return "complete" if session.score is not None else "ungraded"


def _diagnosis(value: object) -> PracticeDiagnosis | None:
    if not isinstance(value, dict):
        return None
    try:
        return PracticeDiagnosis(**value)
    except (TypeError, ValueError):
        return None


def _closure_update(value: object) -> PracticeClosureUpdate | None:
    if not isinstance(value, dict) or not value:
        return None
    try:
        return PracticeClosureUpdate(**value)
    except (TypeError, ValueError):
        return None

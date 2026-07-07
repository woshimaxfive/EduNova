from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from backend.app.models import PracticeAnswer, PracticeSession


PracticeDifficulty = Literal["easy", "medium", "hard"]
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


class PracticeFeedback(BaseModel):
    score: int
    message: str
    matched_keywords: list[str]
    missing_keywords: list[str]
    explanation: str


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
    questions: list[PracticeQuestion]
    answers: list[PracticeAnswerResponse]
    created_at: str
    updated_at: str


def iso_timestamp(value: datetime | None) -> str | None:
    if value is None:
        return None
    timestamp = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    timestamp = timestamp.astimezone(UTC).replace(microsecond=0)
    return timestamp.isoformat().replace("+00:00", "Z")


def session_to_api(session: PracticeSession, answers: list[PracticeAnswer]) -> PracticeSessionDetail:
    questions = [PracticeQuestion(**public_question(item)) for item in (session_questions(session, answers) or [])]
    answer_items = [answer_to_api(answer) for answer in answers if answer.answer_text is not None or answer.is_correct is not None]
    return PracticeSessionDetail(
        id=str(session.id),
        course_id=str(session.course_id),
        title=session.title,
        status=session.status,
        agent_trace_id=getattr(session, "agent_trace_id", None),
        score=int(session.score) if session.score is not None else None,
        questions=questions,
        answers=answer_items,
        created_at=iso_timestamp(session.created_at) or "",
        updated_at=iso_timestamp(session.updated_at) or "",
    )


def session_questions(session: PracticeSession, answers: list[PracticeAnswer]) -> list[dict]:
    metadata = getattr(session, "metadata_json", None)
    if isinstance(metadata, dict) and isinstance(metadata.get("questions"), list):
        return metadata["questions"]
    return [answer.question_json for answer in answers if isinstance(answer.question_json, dict)]


def public_question(question: dict) -> dict:
    return {**question, "correct_answer": None}


def answer_to_api(answer: PracticeAnswer) -> PracticeAnswerResponse:
    feedback = answer.feedback_json or {}
    return PracticeAnswerResponse(
        question_id=str((answer.question_json or {}).get("id") or ""),
        answer_text=answer.answer_text,
        is_correct=answer.is_correct,
        feedback=PracticeFeedback(
            score=int(feedback.get("score") or 0),
            message=str(feedback.get("message") or ""),
            matched_keywords=[str(item) for item in feedback.get("matched_keywords") or []],
            missing_keywords=[str(item) for item in feedback.get("missing_keywords") or []],
            explanation=str(feedback.get("explanation") or ""),
        ),
    )

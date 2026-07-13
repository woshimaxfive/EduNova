from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from backend.app.models import ProfileEvent, StudentProfile


ProfileDimension = Literal[
    "major_background",
    "knowledge_foundation",
    "learning_goal",
    "cognitive_style",
    "learning_preference",
    "weak_points",
    "learning_pace",
    "motivation_interest",
]


PROFILE_DIMENSIONS: list[ProfileDimension] = [
    "major_background",
    "knowledge_foundation",
    "learning_goal",
    "cognitive_style",
    "learning_preference",
    "weak_points",
    "learning_pace",
    "motivation_interest",
]


def empty_profile_json() -> dict[str, Any]:
    return {
        "major_background": "",
        "knowledge_foundation": "",
        "learning_goal": "",
        "cognitive_style": "",
        "learning_preference": "",
        "weak_points": [],
        "learning_pace": "",
        "motivation_interest": "",
    }


class ProfileChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)

    @field_validator("message")
    @classmethod
    def normalize_message(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("画像回答不能为空。")
        return normalized


class StudentProfileResponse(BaseModel):
    id: str | None
    version: int
    has_profile: bool
    profile_json: dict[str, Any]
    confidence_score: float
    dimension_confidence: dict[str, float] = Field(default_factory=dict)
    evidence_summary: dict[str, int | str | None] = Field(default_factory=dict)
    updated_reason: str | None
    updated_at: str | None
    next_question: str
    next_question_dimension: ProfileDimension | None = None


class ProfileEventResponse(BaseModel):
    id: str
    dimension: str
    change_summary: str
    evidence_json: dict[str, Any]
    agent_trace_id: str | None = None
    source_type: str = "legacy"
    source_ref_type: str | None = None
    source_ref_id: str | None = None
    status: str = "applied"
    confidence_score: float | None = None
    created_at: str


class ProfileChatResponse(BaseModel):
    reply: str
    agent_trace_id: str | None = None
    profile: StudentProfileResponse
    event: ProfileEventResponse


def _iso_timestamp(value: datetime | None) -> str | None:
    if value is None:
        return None
    timestamp = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    timestamp = timestamp.astimezone(UTC).replace(microsecond=0)
    return timestamp.isoformat().replace("+00:00", "Z")


def normalize_profile_json(value: dict[str, Any] | None) -> dict[str, Any]:
    result = empty_profile_json()
    if value:
        for key in PROFILE_DIMENSIONS:
            if key == "weak_points":
                raw_weak_points = value.get(key)
                if isinstance(raw_weak_points, list):
                    result[key] = [str(item) for item in raw_weak_points if str(item).strip()]
                continue
            result[key] = str(value.get(key) or "")
    return result


def profile_to_api(
    profile: StudentProfile | None,
    version: int,
    next_question: str,
    *,
    next_question_dimension: ProfileDimension | None = None,
    evidence_summary: dict[str, int | str | None] | None = None,
) -> StudentProfileResponse:
    if profile is None:
        return StudentProfileResponse(
            id=None,
            version=0,
            has_profile=False,
            profile_json=empty_profile_json(),
            confidence_score=0,
            dimension_confidence={},
            evidence_summary=evidence_summary or {},
            updated_reason=None,
            updated_at=None,
            next_question=next_question,
            next_question_dimension=next_question_dimension,
        )

    return StudentProfileResponse(
        id=str(profile.id),
        version=version,
        has_profile=True,
        profile_json=normalize_profile_json(profile.profile_json),
        confidence_score=float(profile.confidence_score or 0),
        dimension_confidence={
            key: float(value)
            for key, value in (getattr(profile, "dimension_confidence_json", None) or {}).items()
            if key in PROFILE_DIMENSIONS and isinstance(value, (int, float))
        },
        evidence_summary=evidence_summary or {},
        updated_reason=profile.updated_reason,
        updated_at=_iso_timestamp(profile.updated_at),
        next_question=next_question,
        next_question_dimension=next_question_dimension,
    )


def event_to_api(event: ProfileEvent) -> ProfileEventResponse:
    return ProfileEventResponse(
        id=str(event.id),
        dimension=event.dimension,
        change_summary=event.change_summary,
        evidence_json=event.evidence_json or {},
        agent_trace_id=getattr(event, "agent_trace_id", None),
        source_type=str(getattr(event, "source_type", None) or "legacy"),
        source_ref_type=getattr(event, "source_ref_type", None),
        source_ref_id=str(event.source_ref_id) if getattr(event, "source_ref_id", None) is not None else None,
        status=str(getattr(event, "status", None) or "applied"),
        confidence_score=float(event.confidence_score) if getattr(event, "confidence_score", None) is not None else None,
        created_at=_iso_timestamp(event.created_at) or "",
    )

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from backend.app.models import ChatMessage, ChatSession


TutorSessionScope = Literal["home", "course"]
TutorSessionMode = Literal["chat", "socratic", "direct"]


class CreateTutorSessionRequest(BaseModel):
    scope: TutorSessionScope = "home"
    course_id: int | None = None
    mode: TutorSessionMode = "chat"
    title: str = Field(min_length=1, max_length=255)

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        return value.strip()


class SendTutorMessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    use_web_search: bool = False
    deep_thinking: bool = False
    selected_material_ids: list[int] = Field(default_factory=list)

    @field_validator("message")
    @classmethod
    def normalize_message(cls, value: str) -> str:
        return value.strip()

    @field_validator("selected_material_ids")
    @classmethod
    def normalize_selected_material_ids(cls, value: list[int]) -> list[int]:
        return list(dict.fromkeys(item for item in value if item > 0))[:10]


class TutorSessionSummary(BaseModel):
    id: str
    scope: TutorSessionScope
    course_id: str | None
    title: str
    mode: TutorSessionMode
    archived_from_home: bool
    created_at: str
    updated_at: str


class TutorMessage(BaseModel):
    id: str
    session_id: str
    role: Literal["user", "assistant"]
    content: str
    citation_json: list
    trace_id: str | None
    created_at: str


class TutorSessionDetail(BaseModel):
    session: TutorSessionSummary
    messages: list[TutorMessage]


def _iso_timestamp(value: datetime | None) -> str:
    timestamp = value or datetime.now(UTC)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=UTC)
    timestamp = timestamp.astimezone(UTC).replace(microsecond=0)
    return timestamp.isoformat().replace("+00:00", "Z")


def session_to_summary(session: ChatSession) -> TutorSessionSummary:
    return TutorSessionSummary(
        id=str(session.id),
        scope=session.scope,
        course_id=str(session.course_id) if session.course_id is not None else None,
        title=session.title,
        mode=session.mode,
        archived_from_home=session.archived_from_home,
        created_at=_iso_timestamp(session.created_at),
        updated_at=_iso_timestamp(session.updated_at),
    )


def message_to_api(message: ChatMessage) -> TutorMessage:
    return TutorMessage(
        id=str(message.id),
        session_id=str(message.session_id),
        role=message.role,
        content=message.content,
        citation_json=message.citation_json or [],
        trace_id=message.trace_id,
        created_at=_iso_timestamp(message.created_at),
    )


def session_detail_to_api(session: ChatSession, messages: list[ChatMessage]) -> TutorSessionDetail:
    return TutorSessionDetail(
        session=session_to_summary(session),
        messages=[message_to_api(message) for message in messages],
    )

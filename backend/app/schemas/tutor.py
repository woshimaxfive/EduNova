from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from backend.app.models import ChatMessage, ChatSession


TutorSessionScope = Literal["home", "course"]
TutorSessionMode = Literal["chat", "socratic", "direct"]


class CreateTutorSessionRequest(BaseModel):
    scope: TutorSessionScope = "home"
    course_id: int | None = None
    mode: TutorSessionMode = "chat"
    title: str = Field(min_length=1, max_length=255)
    selected_material_ids: list[int] = Field(default_factory=list)

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        return value.strip()

    @field_validator("selected_material_ids")
    @classmethod
    def normalize_material_ids(cls, value: list[int]) -> list[int]:
        normalized = list(dict.fromkeys(item for item in value if item > 0))
        if len(normalized) > 10:
            raise ValueError("单个会话最多选择 10 份参考资料。")
        return normalized


class UpdateTutorSessionRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    selected_material_ids: list[int] | None = None

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @field_validator("selected_material_ids")
    @classmethod
    def normalize_material_ids(cls, value: list[int] | None) -> list[int] | None:
        if value is None:
            return None
        normalized = list(dict.fromkeys(item for item in value if item > 0))
        if len(normalized) > 10:
            raise ValueError("单个会话最多选择 10 份参考资料。")
        return normalized

    @model_validator(mode="after")
    def require_update(self):
        if self.title is None and self.selected_material_ids is None:
            raise ValueError("至少提供会话名称或参考资料。")
        return self


class DeleteTutorSessionResponse(BaseModel):
    session_id: str
    deleted: bool


class SendTutorMessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    use_web_search: bool = False
    deep_thinking: bool = False
    selected_material_ids: list[int] | None = None

    @field_validator("message")
    @classmethod
    def normalize_message(cls, value: str) -> str:
        return value.strip()

    @field_validator("selected_material_ids")
    @classmethod
    def normalize_selected_material_ids(cls, value: list[int] | None) -> list[int] | None:
        if value is None:
            return None
        normalized = list(dict.fromkeys(item for item in value if item > 0))
        if len(normalized) > 10:
            raise ValueError("单个会话最多选择 10 份参考资料。")
        return normalized


class TutorSessionSummary(BaseModel):
    id: str
    scope: TutorSessionScope
    course_id: str | None
    title: str
    mode: TutorSessionMode
    archived_from_home: bool
    selected_material_ids: list[int]
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


class TutorSessionHistoryItem(TutorSessionSummary):
    match_snippet: str | None = None


class TutorSessionHistoryPage(BaseModel):
    items: list[TutorSessionHistoryItem]
    page: int
    page_size: int
    total: int
    has_more: bool


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
        selected_material_ids=[int(item) for item in (session.selected_material_ids or []) if str(item).isdigit()][:10],
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

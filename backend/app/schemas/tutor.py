from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from backend.app.models import ChatMessage, ChatMessageAttachment, ChatSession


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
    message: str = Field(default="", max_length=8000)
    attachment_ids: list[int] = Field(default_factory=list)
    use_web_search: bool = Field(
        default=False,
        json_schema_extra={"deprecated": True},
        description="兼容旧客户端；true 强制联网，false 或缺省由系统自动判断。",
    )
    deep_thinking: bool = Field(
        default=False,
        json_schema_extra={"deprecated": True},
        description="兼容旧客户端；true 强制深度推理，false 或缺省由系统自动判断。",
    )
    selected_material_ids: list[int] | None = None
    resource_request: bool = False

    @field_validator("message")
    @classmethod
    def normalize_message(cls, value: str) -> str:
        return value.strip()

    @field_validator("attachment_ids")
    @classmethod
    def normalize_attachment_ids(cls, value: list[int]) -> list[int]:
        normalized = list(dict.fromkeys(item for item in value if item > 0))
        if len(normalized) > 3:
            raise ValueError("每条消息最多上传 3 张图片。")
        return normalized

    @model_validator(mode="after")
    def require_message_or_attachment(self):
        if not self.message and not self.attachment_ids:
            raise ValueError("消息和图片不能同时为空。")
        return self

    @field_validator("selected_material_ids")
    @classmethod
    def normalize_selected_material_ids(cls, value: list[int] | None) -> list[int] | None:
        if value is None:
            return None
        normalized = list(dict.fromkeys(item for item in value if item > 0))
        if len(normalized) > 10:
            raise ValueError("单个会话最多选择 10 份参考资料。")
        return normalized


class CreateTutorResourceJobRequest(BaseModel):
    course_id: int = Field(gt=0)
    knowledge_point_id: int | None = Field(default=None, gt=0, json_schema_extra={"deprecated": True})
    resource_types: list[Literal["doc", "mindmap", "quiz", "code", "slide", "animation", "video"]] = Field(
        default_factory=list,
        max_length=3,
        json_schema_extra={"deprecated": True},
        description="兼容旧客户端；服务端优先使用对应回答中已持久化的模型提案。",
    )
    learning_goal: str = Field(default="", max_length=500, json_schema_extra={"deprecated": True})
    difficulty: Literal["easy", "medium", "hard"] = Field(default="medium", json_schema_extra={"deprecated": True})


class AttachTutorMaterialRequest(BaseModel):
    material_id: int = Field(gt=0)


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


class TutorImageAttachment(BaseModel):
    id: str
    message_id: str | None
    material_id: str | None
    filename: str
    mime_type: str
    size_bytes: int
    width: int
    height: int
    status: Literal["pending", "bound", "deleted"]
    content_url: str | None
    created_at: str


class TutorGeneratedResource(BaseModel):
    id: str
    title: str
    resource_type: str
    course_id: str | None


class TutorResourceJob(BaseModel):
    job_id: str
    status: str
    label: str
    error_message: str | None = None
    resources: list[TutorGeneratedResource] = Field(default_factory=list)


class TutorResourceProposal(BaseModel):
    action: Literal["none", "suggest", "generate"] = "none"
    response_mode: Literal["answer", "action", "answer_and_action"] = "answer"
    resource_types: list[Literal["doc", "mindmap", "quiz", "code", "slide", "animation", "video"]] = Field(default_factory=list)
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    topic: str = ""
    learning_goal: str = ""
    reason_summary: str = ""
    confidence: float = Field(default=0, ge=0, le=1)


class TutorMessage(BaseModel):
    id: str
    session_id: str
    role: Literal["user", "assistant"]
    content: str
    citation_json: list
    trace_id: str | None
    created_at: str
    attachments: list[TutorImageAttachment] = Field(default_factory=list)
    resource_jobs: list[TutorResourceJob] = Field(default_factory=list)
    resource_proposal: TutorResourceProposal | None = None


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


def attachment_to_api(attachment: ChatMessageAttachment) -> TutorImageAttachment:
    return TutorImageAttachment(
        id=str(attachment.id),
        message_id=str(attachment.message_id) if attachment.message_id is not None else None,
        material_id=str(attachment.material_id) if getattr(attachment, "material_id", None) is not None else None,
        filename=attachment.original_filename,
        mime_type=attachment.mime_type,
        size_bytes=attachment.size_bytes,
        width=attachment.width,
        height=attachment.height,
        status=attachment.status,
        content_url=(
            f"/api/v1/tutor/attachments/{attachment.id}/content"
            if attachment.status != "deleted" and attachment.storage_key
            else None
        ),
        created_at=_iso_timestamp(attachment.created_at),
    )


def message_to_api(message: ChatMessage, attachments: list[ChatMessageAttachment] | None = None, resource_jobs: list[TutorResourceJob] | None = None) -> TutorMessage:
    stored_proposal = getattr(message, "resource_proposal_json", {})
    raw_proposal = stored_proposal if isinstance(stored_proposal, dict) else {}
    proposal = TutorResourceProposal.model_validate(raw_proposal) if raw_proposal.get("action") in {"suggest", "generate"} else None
    return TutorMessage(
        id=str(message.id),
        session_id=str(message.session_id),
        role=message.role,
        content=message.content,
        citation_json=message.citation_json or [],
        trace_id=message.trace_id,
        created_at=_iso_timestamp(message.created_at),
        attachments=[attachment_to_api(item) for item in (attachments or [])],
        resource_jobs=resource_jobs or [],
        resource_proposal=proposal,
    )


def session_detail_to_api(
    session: ChatSession,
    messages: list[ChatMessage],
    attachment_map: dict[int, list[ChatMessageAttachment]] | None = None,
    resource_job_map: dict[int, list[TutorResourceJob]] | None = None,
) -> TutorSessionDetail:
    return TutorSessionDetail(
        session=session_to_summary(session),
        messages=[message_to_api(message, (attachment_map or {}).get(message.id, []), (resource_job_map or {}).get(message.id, [])) for message in messages],
    )

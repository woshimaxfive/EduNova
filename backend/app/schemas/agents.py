from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel

from backend.app.models import AgentRunLog


SAFE_AGENT_METADATA_KEYS = {
    "citation_count",
    "confidence",
    "error_code",
    "knowledge_point_id",
    "resource_count",
    "review_result",
    "source_count",
}

SENSITIVE_TEXT_MARKERS = (
    "系统提示词",
    "system prompt",
    "模型输入",
    "model input",
    "资料原文",
    "source text",
    "raw prompt",
    "api key",
    "sk-",
)


class AgentTraceStep(BaseModel):
    id: str
    agent_name: str
    step_index: int
    status: str
    input_summary: str | None
    output_summary: str | None
    duration_ms: int | None
    metadata: dict[str, Any]
    created_at: str


class AgentTraceResponse(BaseModel):
    trace_id: str
    course_id: str | None
    status: str
    steps: list[AgentTraceStep]


def iso_timestamp(value: datetime | None) -> str:
    if value is None:
        return ""
    timestamp = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    timestamp = timestamp.astimezone(UTC).replace(microsecond=0)
    return timestamp.isoformat().replace("+00:00", "Z")


def safe_agent_summary(value: str | None, fallback: str) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return ""
    lowered = normalized.lower()
    if any(marker in lowered or marker in normalized for marker in SENSITIVE_TEXT_MARKERS):
        return fallback
    return normalized[:500]


def safe_agent_metadata(value: dict[str, Any] | None) -> dict[str, Any]:
    if not value:
        return {}
    return {key: value[key] for key in SAFE_AGENT_METADATA_KEYS if key in value}


def agent_log_to_api(log: AgentRunLog) -> AgentTraceStep:
    return AgentTraceStep(
        id=str(log.id),
        agent_name=log.agent_name,
        step_index=log.step_index,
        status=log.status,
        input_summary=safe_agent_summary(log.input_summary, "已隐藏敏感输入摘要"),
        output_summary=safe_agent_summary(log.output_summary, "已隐藏敏感输出摘要"),
        duration_ms=log.duration_ms,
        metadata=safe_agent_metadata(log.metadata_json),
        created_at=iso_timestamp(log.created_at),
    )

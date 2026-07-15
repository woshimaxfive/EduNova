from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel

from backend.app.models import AgentRunLog


SAFE_AGENT_METADATA_KEYS = {
    "artifact_id",
    "artifact_type",
    "applied_count",
    "citation_count",
    "course_citation_count",
    "web_citation_count",
    "confidence",
    "context_message_count",
    "context_summary_used",
    "error_code",
    "generation_mode",
    "reasoning_mode",
    "embedding_status",
    "embedding_call_count",
    "embedding_dimension",
    "embedding_provider",
    "extracted_dimension_count",
    "extraction_mode",
    "retrieval_mode",
    "material_count",
    "evidence_count",
    "comparison_id",
    "trigger",
    "source_practice_session_id",
    "operation",
    "practice_count",
    "parse_status",
    "weakness_count",
    "path_update_status",
    "preserved_task_count",
    "candidate_count",
    "rerank_call_count",
    "rerank_status",
    "retrieval_fallback",
    "trend_direction",
    "web_result_count",
    "search_required",
    "tool_reason_codes",
    "tool_reason_summary",
    "external_only",
    "use_web_search",
    "deep_thinking",
    "repair_count",
    "knowledge_point_id",
    "retrieval_query_mode",
    "resource_count",
    "resource_type",
    "worker_count",
    "model_used",
    "model_call_count",
    "model_retry_count",
    "model_latency_ms",
    "model_outcome",
    "model_error_category",
    "profile_applied_version",
    "profile_completeness",
    "trusted_dimension_count",
    "advisory_dimension_count",
    "profile_context_used",
    "course_context_hash",
    "course_weakness_count",
    "mastery_average",
    "scored_dimension_count",
    "source_factor",
    "review_factor",
    "review_mode",
    "failed_resource_types",
    "review_status",
    "review_result",
    "risk_flags",
    "safety_summary",
    "source_count",
    "warning_count",
    "workflow",
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
    workflow: str | None
    artifact_type: str | None
    artifact_id: str | None
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

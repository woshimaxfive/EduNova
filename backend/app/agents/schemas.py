from __future__ import annotations

from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    trace_id: str
    workflow: str
    user_id: int
    course_id: int | None
    knowledge_point_id: int | None
    artifact_type: str | None
    artifact_id: str | None
    intent: str
    profile: dict[str, Any]
    profile_summary: dict[str, Any]
    retrieved_chunks: list[dict[str, Any]]
    citations: list[dict[str, Any]]
    diagnosis: dict[str, Any]
    generated_resources: list[dict[str, Any]]
    review_result: dict[str, Any]
    warnings: list[str]
    errors: list[str]
    node_results: list[str]
    artifact_refs: dict[str, Any]

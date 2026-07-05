from __future__ import annotations

from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    trace_id: str
    user_id: int
    course_id: int | None
    knowledge_point_id: int | None
    intent: str
    profile: dict[str, Any]
    retrieved_chunks: list[dict[str, Any]]
    diagnosis: dict[str, Any]
    generated_resources: list[dict[str, Any]]
    review_result: dict[str, Any]
    errors: list[str]

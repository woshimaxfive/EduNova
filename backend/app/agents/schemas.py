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
    learner_context: Any
    learner_context_metadata: dict[str, Any]
    retrieved_chunks: list[dict[str, Any]]
    citations: list[dict[str, Any]]
    diagnosis: dict[str, Any]
    generated_resources: list[dict[str, Any]]
    review_result: dict[str, Any]
    warnings: list[str]
    errors: list[str]
    node_results: list[str]
    artifact_refs: dict[str, Any]
    user: Any
    session: Any
    course: Any
    knowledge_point: Any
    resource_types: list[str]
    learning_goal: str
    difficulty: str
    context_points: list[Any]
    contexts: list[Any]
    resource_citations: list[Any]
    drafts: dict[str, Any]
    enhanced_markdown: dict[str, str]
    model_failed: bool
    resource_payloads: list[dict[str, Any]]
    resource_objects: list[Any]
    quality_scores: dict[str, Any]
    generation_warnings: int
    message_text: str
    stored_message_text: str
    attachment_ids: list[int]
    vision_decision: dict[str, Any] | None
    conversation_context: Any
    retrieval_query: str
    context_metadata: dict[str, Any]
    citation_json: list[dict[str, Any]]
    assistant_reply: str
    used_model: bool
    tokens: Any
    pending_traces: list[Any]
    use_web_search: bool
    deep_thinking: bool
    search_required: bool
    reasoning_mode: str
    tool_reason_codes: list[str]
    tool_reason_summary: str
    semantic_decision_mode: str
    semantic_decision_confidence: float
    semantic_warning: str | None
    resource_action: str
    resource_types: list[str]
    resource_difficulty: str
    resource_learning_goal: str
    resource_reason_summary: str
    response_mode: str
    semantic_search_query: str
    standalone_query: str
    uses_history: bool
    referenced_turn_ids: list[str]
    source_scope: str
    profile_signal_updates: dict[str, Any]
    profile_signal_confidence: dict[str, float]
    course_related: bool
    course_citation_count: int
    web_citation_count: int
    selected_material_ids: list[int]
    streaming: bool
    requires_fresh_info: bool
    retrieval_mode: str
    embedding_status: str
    plan_summary: str
    repair_count: int
    needs_repair: bool
    detail: Any

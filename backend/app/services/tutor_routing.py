from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.app.agents.tool_policy import ToolDecision


@dataclass(frozen=True)
class TutorRouteProjection:
    updates: dict[str, Any]
    metadata: dict[str, Any]
    summary: str


def project_visual_route(
    *,
    visual: dict[str, Any],
    message_text: str,
    force_search: bool,
    force_deep: bool,
    intent: str,
    summary: str,
    warnings: list[str],
    attachment_count: int,
) -> TutorRouteProjection:
    search_required = bool(visual.get("search_required")) or force_search
    reasoning_mode = "deep" if force_deep else str(visual.get("reasoning_mode") or "auto")
    standalone_query = str(visual.get("standalone_query") or message_text)
    confidence = float(visual.get("confidence") or 0)
    provider = str(visual.get("provider") or "unknown")
    updates = {
        "intent": intent,
        "search_required": search_required,
        "reasoning_mode": reasoning_mode,
        "source_scope": "mainland_preferred",
        "tool_reason_codes": ["vision_understanding"],
        "tool_reason_summary": summary,
        "semantic_search_query": standalone_query,
        "semantic_decision_mode": "vision_model",
        "semantic_decision_confidence": confidence,
        "semantic_warning": None,
        "resource_action": "none",
        "resource_types": [],
        "response_mode": "answer",
        "retrieval_query": standalone_query,
        "standalone_query": standalone_query,
        "uses_history": False,
        "referenced_turn_ids": [],
        "warnings": warnings,
    }
    metadata = {
        "search_required": search_required,
        "reasoning_mode": reasoning_mode,
        "semantic_decision_mode": "vision_model",
        "semantic_decision_confidence": confidence,
        "semantic_intent": intent,
        "vision_image_count": attachment_count,
        "vision_provider": provider,
        "vision_confidence": confidence,
    }
    return TutorRouteProjection(updates=updates, metadata=metadata, summary=summary)


def project_semantic_route(
    *,
    decision: ToolDecision,
    intent: str,
    message_text: str,
    fallback_retrieval_query: str,
    history_message: str,
    history_visual: dict[str, Any] | None,
    warnings: list[str],
) -> TutorRouteProjection:
    search_required = decision.search_required or bool(history_visual and history_visual.get("search_required"))
    reasoning_mode = (
        "deep"
        if decision.reasoning_mode == "deep" or bool(history_visual and history_visual.get("reasoning_mode") == "deep")
        else "auto"
    )
    standalone_query = (
        str(history_visual.get("standalone_query") or history_message)
        if history_visual
        else decision.standalone_query
    )
    if decision.warning and decision.warning not in warnings:
        warnings.append(decision.warning)
    retrieval_query = standalone_query if history_visual else (
        decision.standalone_query
        if decision.uses_history
        else message_text if decision.decision_mode in {"model", "model_forced"} else fallback_retrieval_query
    )
    updates = {
        "intent": intent,
        "search_required": search_required,
        "reasoning_mode": reasoning_mode,
        "source_scope": decision.source_scope,
        "tool_reason_codes": list(decision.reason_codes),
        "tool_reason_summary": decision.reason_summary,
        "semantic_search_query": standalone_query if history_visual else decision.search_query,
        "semantic_decision_mode": decision.decision_mode,
        "semantic_decision_confidence": decision.confidence,
        "semantic_warning": decision.warning,
        "resource_action": decision.resource_action,
        "resource_types": list(decision.resource_types),
        "resource_difficulty": decision.resource_difficulty,
        "resource_topic": decision.resource_topic,
        "resource_learning_goal": decision.resource_learning_goal,
        "resource_reason_summary": decision.resource_reason_summary,
        "response_mode": decision.response_mode,
        "retrieval_query": retrieval_query,
        "standalone_query": standalone_query,
        "message_text": history_message,
        "vision_decision": history_visual,
        "uses_history": decision.uses_history,
        "referenced_turn_ids": list(decision.referenced_turn_ids),
        "warnings": warnings,
    }
    metadata = {
        "search_required": search_required,
        "reasoning_mode": reasoning_mode,
        "tool_reason_codes": list(decision.reason_codes),
        "tool_reason_summary": decision.reason_summary,
        "semantic_decision_mode": decision.decision_mode,
        "semantic_decision_confidence": decision.confidence,
        "source_scope": decision.source_scope,
        "semantic_intent": intent,
        "reused_history_image": bool(history_visual),
        "vision_image_count": int(history_visual.get("image_count", 0)) if history_visual else 0,
        "vision_provider": str(history_visual.get("provider") or "unknown") if history_visual else None,
        "vision_confidence": float(history_visual.get("confidence") or 0) if history_visual else None,
    }
    return TutorRouteProjection(updates=updates, metadata=metadata, summary=decision.reason_summary)

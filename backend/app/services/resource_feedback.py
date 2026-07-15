from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Any


RESOURCE_TYPES = ("doc", "mindmap", "quiz", "code", "slide", "animation", "video")
DEFAULT_BUNDLE_TYPES = ("doc", "mindmap", "quiz")


def aggregate_resource_interactions(
    rows: Iterable[tuple[int, str, str, str | None, datetime | None, int]],
) -> dict[str, dict[str, int]]:
    """Aggregate one learning state and the latest feedback per unique resource."""
    states: dict[int, dict[str, Any]] = {}
    for resource_id, resource_type, event_type, feedback, created_at, interaction_id in rows:
        state = states.setdefault(
            int(resource_id),
            {
                "resource_type": str(resource_type),
                "opened": False,
                "started": False,
                "completed": False,
                "latest_feedback": None,
                "latest_feedback_order": None,
            },
        )
        event_name = str(event_type)
        if event_name in {"opened", "started", "completed"}:
            state[event_name] = True
        if event_name == "feedback" and feedback:
            order = (created_at.timestamp() if created_at is not None else float("-inf"), int(interaction_id))
            if state["latest_feedback_order"] is None or order > state["latest_feedback_order"]:
                state["latest_feedback"] = str(feedback)
                state["latest_feedback_order"] = order

    summary: dict[str, dict[str, int]] = {}
    for state in states.values():
        bucket = summary.setdefault(str(state["resource_type"]), {})
        for event_name in ("opened", "started", "completed"):
            if state[event_name]:
                bucket[event_name] = bucket.get(event_name, 0) + 1
        feedback = state["latest_feedback"]
        if feedback:
            bucket[feedback] = bucket.get(feedback, 0) + 1
    return summary


def rank_resource_types(
    resource_types: Iterable[str],
    summary: dict[str, dict[str, int]] | None,
) -> list[str]:
    unique = [item for item in dict.fromkeys(resource_types) if item in RESOURCE_TYPES]
    feedback = summary or {}

    def score(resource_type: str) -> int:
        counts = feedback.get(resource_type, {})
        negative = counts.get("not_helpful", 0) if counts.get("not_helpful", 0) >= 2 else 0
        return counts.get("helpful", 0) * 3 + counts.get("completed", 0) * 2 + counts.get("opened", 0) - negative * 3

    original_order = {resource_type: index for index, resource_type in enumerate(unique)}
    return sorted(unique, key=lambda resource_type: (-score(resource_type), original_order[resource_type]))


def deterministic_bundle_types(summary: dict[str, dict[str, int]] | None) -> tuple[str, ...]:
    return tuple(rank_resource_types(DEFAULT_BUNDLE_TYPES, summary))


def feedback_adjustment(resource_type: str, summary: dict[str, dict[str, int]] | None) -> str | None:
    counts = (summary or {}).get(resource_type, {})
    if counts.get("too_hard", 0) > 0:
        return "scaffold"
    if counts.get("too_easy", 0) > 0:
        return "challenge"
    if counts.get("not_helpful", 0) >= 2:
        return "alternative"
    if counts.get("helpful", 0) > 0 or counts.get("completed", 0) > 0:
        return "preferred"
    return None

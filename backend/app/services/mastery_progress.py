from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any


def latest_practice_score(answers: Iterable[Any]) -> int | None:
    """Return the latest graded attempt score for one knowledge point."""

    grouped: dict[int, list[int]] = {}
    recency: dict[int, tuple[float, int]] = {}
    for answer in answers:
        feedback = getattr(answer, "feedback_json", None) or {}
        if getattr(answer, "answer_text", None) is None or feedback.get("score") is None:
            continue
        try:
            session_id = int(getattr(answer, "session_id"))
            score = int(feedback["score"])
        except (TypeError, ValueError, KeyError):
            continue
        grouped.setdefault(session_id, []).append(max(0, min(100, score)))
        created_at = getattr(answer, "created_at", None)
        try:
            timestamp = created_at.timestamp() if created_at is not None else float("-inf")
        except (AttributeError, OSError, ValueError):
            timestamp = float("-inf")
        recency[session_id] = max(recency.get(session_id, (float("-inf"), session_id)), (timestamp, session_id))
    if not grouped:
        return None
    latest_session_id = max(grouped, key=lambda item: recency.get(item, (float("-inf"), item)))
    scores = grouped[latest_session_id]
    return round(sum(scores) / len(scores))


def is_review_due(item: Any, now: datetime | None = None) -> bool:
    if getattr(item, "status", None) != "completed":
        return False
    next_review_at = getattr(item, "next_review_at", None)
    if next_review_at is None:
        return False
    current = now or datetime.now(UTC)
    if next_review_at.tzinfo is None:
        next_review_at = next_review_at.replace(tzinfo=UTC)
    return next_review_at <= current

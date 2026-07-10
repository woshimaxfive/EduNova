from __future__ import annotations

import json
from typing import Any


SENSITIVE_MARKERS = (
    "系统提示词",
    "system prompt",
    "模型输入",
    "model input",
    "api key",
    "sk-",
    "资料原文",
    "source text",
)


def parse_json_object(value: str) -> dict[str, Any] | None:
    cleaned = value.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    try:
        parsed = json.loads(cleaned.strip())
    except (TypeError, ValueError):
        return None
    return parsed if isinstance(parsed, dict) else None


def safe_text(value: object, *, limit: int = 240) -> str:
    return " ".join(str(value or "").split())[:limit]


def safe_string_list(value: object, *, limit: int = 8, item_limit: int = 120) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        cleaned = safe_text(item, limit=item_limit)
        if cleaned and cleaned not in result:
            result.append(cleaned)
        if len(result) >= limit:
            break
    return result


def contains_sensitive_text(value: object) -> bool:
    lowered = str(value or "").casefold()
    return any(marker.casefold() in lowered for marker in SENSITIVE_MARKERS)


def clamp_confidence(value: object, default: float = 0.5) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = default
    return max(0.0, min(1.0, parsed))


def review_contract(value: dict[str, Any] | None, *, default_summary: str) -> dict[str, Any] | None:
    if not value:
        return None
    status = safe_text(value.get("review_status"), limit=24)
    if status not in {"passed", "revise", "warning"}:
        return None
    return {
        "review_status": status,
        "confidence": clamp_confidence(value.get("confidence")),
        "risk_flags": safe_string_list(value.get("risk_flags"), limit=8, item_limit=60),
        "safety_summary": safe_text(value.get("safety_summary"), limit=240) or default_summary,
    }

"""Numeric-only provider usage, separate from model inputs and business state."""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from decimal import Decimal, InvalidOperation
from typing import Any


TOKEN_FIELDS = (
    "input_tokens", "output_tokens", "reasoning_tokens", "cache_read_tokens",
    "cache_write_tokens", "uncached_input_tokens",
)
_capture: ContextVar[dict[str, Any] | None] = ContextVar("model_usage_capture", default=None)


def _get(value: Any, key: str) -> Any:
    return value.get(key) if isinstance(value, dict) else getattr(value, key, None)


def _count(*values: Any) -> int | None:
    return next((value for value in values if type(value) is int and 0 <= value <= 2**63 - 1), None)


def normalize_usage(usage: Any) -> dict[str, Any]:
    """Chat Completions totals include cached input; absent fields stay unknown."""
    prompt_details = _get(usage, "prompt_tokens_details")
    input_details = _get(usage, "input_tokens_details")
    output_details = _get(usage, "completion_tokens_details") or _get(usage, "output_tokens_details")
    total = _count(_get(usage, "prompt_tokens"), _get(usage, "input_tokens"))
    read = _count(_get(prompt_details, "cached_tokens"), _get(input_details, "cached_tokens"),
                  _get(usage, "prompt_cache_hit_tokens"), _get(usage, "cache_read_input_tokens"))
    write = _count(_get(prompt_details, "cache_write_tokens"), _get(input_details, "cache_write_tokens"),
                   _get(usage, "cache_creation_input_tokens"))
    miss = _count(_get(usage, "prompt_cache_miss_tokens"))
    fresh = None
    # Only explicit complete partitions justify a derived uncached count.
    if total is not None and read is not None:
        if write is not None and read + write <= total:
            fresh = total - read - write
        elif miss is not None and read + miss == total and write is None:
            fresh = miss
    result = {
        "input_tokens": total,
        "output_tokens": _count(_get(usage, "completion_tokens"), _get(usage, "output_tokens")),
        "reasoning_tokens": _count(_get(output_details, "reasoning_tokens")),
        "cache_read_tokens": read,
        "cache_write_tokens": write,
        "uncached_input_tokens": fresh,
    }
    result["usage_status"] = "reported" if any(value is not None for value in result.values()) else "unknown"
    return result


def report_usage(usage: Any) -> dict[str, Any]:
    normalized = normalize_usage(usage)
    target = _capture.get()
    if target is not None and normalized["usage_status"] == "reported":
        # Streaming reports are snapshots, not deltas: do not sum repeated frames.
        target.update(normalized)
    return normalized


@contextmanager
def capture_usage(values: dict[str, Any] | None = None):
    values = normalize_usage(None) if values is None else values
    token = _capture.set(values)
    try:
        yield values
    finally:
        _capture.reset(token)


def summarize_attempts(attempts: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {"attempts": attempts, "observed_attempt_count": len(attempts)}
    for field in TOKEN_FIELDS:
        values = [attempt.get(field) for attempt in attempts]
        known = [value for value in values if type(value) is int]
        result[field] = sum(known) if values and len(known) == len(values) else None
        result[f"known_{field}"] = sum(known) if known else None
    total, cached = result["input_tokens"], result["cache_read_tokens"]
    valid_partitions = all(
        type(attempt.get("input_tokens")) is int and type(attempt.get("cache_read_tokens")) is int
        and 0 <= attempt["cache_read_tokens"] <= attempt["input_tokens"]
        for attempt in attempts
    )
    result["cache_hit_ratio"] = cached / total if total and cached is not None and valid_partitions else None
    result["estimated_cost"] = None
    result["cost_status"] = "pricing_unavailable"
    return result


def estimate_cost(summary: dict[str, Any], pricing: dict[str, Any] | None) -> dict[str, Any]:
    """Explicit deployment pricing only; never infer a reseller's price from its model name."""
    if not pricing:
        return {"estimated_cost": None, "cost_status": "pricing_unavailable"}
    fields = ("uncached_input_tokens", "cache_read_tokens", "cache_write_tokens", "output_tokens")
    if any(summary.get(key) is None for key in fields):
        return {"estimated_cost": None, "cost_status": "usage_incomplete"}
    currency = pricing.get("currency")
    if currency not in {"CNY", "USD"}:
        return {"estimated_cost": None, "cost_status": "pricing_invalid"}
    try:
        rates = [Decimal(str(pricing[key])) for key in fields]
        if any(not rate.is_finite() or rate < 0 for rate in rates):
            raise ValueError("invalid rate")
        total = sum(Decimal(summary[key]) * rate for key, rate in zip(fields, rates)) / Decimal(1_000_000)
    except (KeyError, ValueError, InvalidOperation):
        return {"estimated_cost": None, "cost_status": "pricing_invalid"}
    return {"estimated_cost": str(total), "cost_status": "estimated", "currency": currency,
            "pricing_per_million": {key: str(rate) for key, rate in zip(fields, rates)}}

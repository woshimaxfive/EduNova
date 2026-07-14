from __future__ import annotations

import json
from typing import Any, TypeVar

from json_repair import repair_json
from pydantic import BaseModel, ValidationError


SchemaT = TypeVar("SchemaT", bound=BaseModel)


def parse_json_object(value: str, schema: type[SchemaT] | None = None) -> dict[str, Any] | None:
    """Strict JSON, one deterministic repair, then optional Pydantic validation."""
    cleaned = str(value or "").strip()
    if not cleaned:
        return None
    if cleaned.startswith("```"):
        first_newline = cleaned.find("\n")
        cleaned = cleaned[first_newline + 1 :] if first_newline >= 0 else cleaned.removeprefix("```json").removeprefix("```")
        cleaned = cleaned.removesuffix("```").strip()

    try:
        parsed: Any = json.loads(cleaned)
    except (TypeError, ValueError, json.JSONDecodeError):
        try:
            parsed = repair_json(cleaned, return_objects=True, skip_json_loads=True)
        except Exception:
            return None
    if not isinstance(parsed, dict):
        return None
    if schema is None:
        return parsed
    try:
        return schema.model_validate(parsed).model_dump(mode="json")
    except ValidationError:
        return None

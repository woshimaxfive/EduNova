from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class PersonalizationFreshnessResponse(BaseModel):
    status: Literal["current", "stale", "legacy"]
    profile_applied_version: int | None
    current_profile_applied_version: int
    reason: str

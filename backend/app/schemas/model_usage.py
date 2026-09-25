from datetime import datetime

from pydantic import BaseModel, Field


class UsageTotals(BaseModel):
    input_tokens: int | None = None
    output_tokens: int | None = None
    cache_read_tokens: int | None = None
    cache_write_tokens: int | None = None
    known_input_tokens: int | None = None
    known_output_tokens: int | None = None
    cache_hit_ratio: float | None = None


class UsageCall(BaseModel):
    id: str
    started_at: datetime
    model_name: str
    purpose: str
    status: str
    retry_count: int
    usage: UsageTotals
    estimated_cost: str | None = None
    currency: str | None = None


class ModelUsageReport(BaseModel):
    days: int
    since: datetime
    until: datetime
    retention_days: int
    limit: int
    truncated: bool
    call_count: int
    failed_count: int
    retry_count: int
    observed_attempt_count: int
    legacy_call_count: int
    totals: UsageTotals
    cost_subtotals: dict[str, str] = Field(default_factory=dict)
    priced_call_count: int
    recent: list[UsageCall]

"""Bounded, current-user-only reporting of numeric model telemetry."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

from sqlalchemy import or_, select

from backend.app.models import ModelCallRun
from backend.app.providers.model_usage import summarize_attempts
from backend.app.schemas.model_usage import ModelUsageReport, UsageCall, UsageTotals


REPORT_LIMIT = 1000
MAIN_MODEL_OPERATIONS = ("chat", "stream", "structured", "vision")


def _price(usage: dict) -> tuple[str, Decimal] | None:
    if usage.get("cost_status") != "estimated" or usage.get("currency") not in {"CNY", "USD"}:
        return None
    try:
        value = Decimal(str(usage.get("estimated_cost")))
    except InvalidOperation:
        return None
    return (usage["currency"], value) if value.is_finite() and value >= 0 else None


def build_usage_report(rows, *, days: int, now: datetime, retention_days: int) -> ModelUsageReport:
    selected = rows[:REPORT_LIMIT]
    attempts, recent = [], []
    costs: dict[str, Decimal] = {}
    observed = legacy = priced = 0
    for row in selected:
        usage = row.usage_json or {}
        if row.usage_json is None:
            legacy += 1
            # Legacy rows must not make a partial sample appear fully reported.
            attempts.append({})
        else:
            reported = usage.get("attempts", [])
            observed += len(reported)
            attempts.extend(reported)
        price = _price(usage)
        if price is not None:
            currency, amount = price
            costs[currency] = costs.get(currency, Decimal(0)) + amount
            priced += 1
        if len(recent) < 20:
            recent.append(UsageCall(
                id=str(row.id), started_at=row.started_at, model_name=row.model_name,
                purpose=row.purpose, status=row.status, retry_count=row.retry_count,
                usage=UsageTotals.model_validate(usage),
                estimated_cost=str(price[1]) if price else None,
                currency=price[0] if price else None,
            ))
    return ModelUsageReport(
        days=days, since=now - timedelta(days=days), until=now, retention_days=retention_days,
        limit=REPORT_LIMIT, truncated=len(rows) > REPORT_LIMIT,
        call_count=len(selected), failed_count=sum(row.status == "failed" for row in selected),
        retry_count=sum(row.retry_count for row in selected), observed_attempt_count=observed,
        legacy_call_count=legacy, totals=UsageTotals.model_validate(summarize_attempts(attempts)),
        cost_subtotals={currency: str(amount) for currency, amount in sorted(costs.items())},
        priced_call_count=priced, recent=recent,
    )


def get_usage_report(db, user_id: int, days: int, retention_days: int) -> ModelUsageReport:
    now = datetime.now(timezone.utc)
    rows = list(db.scalars(select(ModelCallRun).where(
        ModelCallRun.user_id == user_id,
        # Filter before LIMIT and aggregation so auxiliary calls cannot skew totals
        # or displace main-model history. Keep the underlying audit log intact.
        or_(ModelCallRun.operation.in_(MAIN_MODEL_OPERATIONS), ModelCallRun.operation.startswith("chat:")),
        ModelCallRun.started_at >= now - timedelta(days=days),
        ModelCallRun.started_at <= now,
    ).order_by(ModelCallRun.started_at.desc(), ModelCallRun.id.desc()).limit(REPORT_LIMIT + 1)))
    return build_usage_report(rows, days=days, now=now, retention_days=retention_days)

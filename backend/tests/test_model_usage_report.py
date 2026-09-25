from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient

from backend.app.api.v1.deps import get_current_user
from backend.app.db.session import get_db_session
from backend.app.main import create_app
from backend.app.providers.model_usage import normalize_usage, summarize_attempts
from backend.app.services.model_usage_report import build_usage_report


NOW = datetime(2026, 9, 25, tzinfo=timezone.utc)


def row(usage=None, **changes):
    return SimpleNamespace(**{
        **dict(id=1, started_at=NOW, model_name="fixture", purpose="chat", status="completed",
               retry_count=0, usage_json=usage), **changes,
    })


def report(rows):
    return build_usage_report(rows, days=7, now=NOW, retention_days=30)


def usage(count=100, cached=80):
    return summarize_attempts([normalize_usage({
        "prompt_tokens": count, "completion_tokens": 0, "prompt_cache_hit_tokens": cached,
    })])


def test_weighted_usage_and_failed_attempts_are_included():
    result = report([row(usage()), row(usage(300, 0), status="failed", retry_count=1)])
    assert result.totals.input_tokens == 400
    assert result.totals.output_tokens == 0
    assert result.totals.cache_hit_ratio == 0.2
    assert result.observed_attempt_count == 2
    assert result.failed_count == result.retry_count == 1


def test_legacy_and_pre_call_failure_are_distinct_and_partial_costs_keep_currencies():
    result = report([
        row({**usage(), "estimated_cost": "0.01", "currency": "USD", "cost_status": "estimated"}),
        row({**usage(), "estimated_cost": "0.02", "currency": "CNY", "cost_status": "estimated"}),
        row(None), row(summarize_attempts([]), status="failed"),
    ])
    assert result.totals.input_tokens is None
    assert result.totals.known_input_tokens == 200
    assert result.totals.cache_hit_ratio is None
    assert result.observed_attempt_count == 2
    assert result.legacy_call_count == 1
    assert result.cost_subtotals == {"USD": "0.01", "CNY": "0.02"}
    assert result.priced_call_count == 2


def test_empty_unknown_zero_invalid_price_and_bounded_report():
    assert report([]).totals.input_tokens is None
    zero = report([row({**usage(0, 0), "estimated_cost": "0", "currency": "USD", "cost_status": "estimated"})])
    assert zero.totals.input_tokens == 0
    assert zero.totals.cache_hit_ratio is None
    assert zero.cost_subtotals == {"USD": "0"}
    result = report([row({**usage(), "estimated_cost": "NaN", "currency": "USD", "cost_status": "estimated"})] * 1001)
    assert result.truncated and result.call_count == 1000 and len(result.recent) == 20
    assert result.cost_subtotals == {}


def test_api_requires_auth_bounds_window_and_filters_current_user_in_sql():
    statements = []
    class Db:
        def scalars(self, statement):
            statements.append(statement)
            return []
    app = create_app()
    app.dependency_overrides[get_db_session] = lambda: Db()
    client = TestClient(app)
    assert client.get("/api/v1/settings/model/usage").status_code == 401
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=17)
    for days in ("0", "31", "bad"):
        assert client.get(f"/api/v1/settings/model/usage?days={days}").status_code == 422
    for days in (1, 7, 30):
        response = client.get(f"/api/v1/settings/model/usage?days={days}&user_id=999")
        assert response.status_code == 200
        assert response.json()["data"]["days"] == days
        compiled = statements[-1].compile()
        assert compiled.params["user_id_1"] == 17
        assert "model_call_runs.started_at >=" in str(compiled)
        assert "model_call_runs.started_at <=" in str(compiled)
        assert 1001 in compiled.params.values()

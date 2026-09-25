"""Synthetic PostgreSQL usage persistence and migration check; no model calls."""
from importlib import import_module
from datetime import datetime, timezone
from uuid import uuid4

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import delete, select, text

from backend.app.core.config import get_settings
from backend.app.db.session import SessionLocal, engine
from backend.app.models import ModelCallRun, User
from backend.app.services.model_execution import ModelCallAuditRecorder, ModelExecutionContext
from backend.app.services.model_usage_report import get_usage_report


def main() -> None:
    migration = import_module("backend.migrations.versions.20260925_0038_model_usage")
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            connection.execute(text("CREATE TEMP TABLE model_call_runs (id bigint PRIMARY KEY)"))
            connection.execute(text("INSERT INTO model_call_runs VALUES (1)"))
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
                row = connection.execute(text("SELECT usage_json, session_id FROM model_call_runs")).one()
                assert row.usage_json is None and row.session_id is None
                migration.downgrade()
                migration.upgrade()
        finally:
            transaction.rollback()

    class NoCleanup:
        def allow_daily_cleanup(self):
            return False

    user_id = None
    with SessionLocal() as db:
        try:
            user = User(account=f"usage_{uuid4().hex[:12]}", hashed_password="synthetic-only", display_name="usage test", role="student", starter_mode="blank")
            db.add(user)
            db.commit()
            user_id = user.id
            context = ModelExecutionContext(session_id=321, usage_attempts=[
                {"input_tokens": 100, "output_tokens": 20, "cache_read_tokens": 60, "usage_status": "reported"},
                {"usage_status": "unknown"},
            ])
            ModelCallAuditRecorder(get_settings(), NoCleanup()).record(
                user_id=user_id, provider_source="system", model_config_id=None, model_name="synthetic",
                operation="chat:test", status="completed", error_category=None, attempt_count=2,
                latency_ms=10, context=context,
            )
            record = db.scalar(select(ModelCallRun).where(ModelCallRun.user_id == user_id))
            assert record is not None and record.session_id == 321
            assert record.usage_json["input_tokens"] is None
            assert record.usage_json["known_input_tokens"] == 100
            assert record.usage_json["cache_hit_ratio"] is None
            assert record.usage_json["estimated_cost"] is None
            # More auxiliary calls than the report limit must not hide main calls,
            # mark the report truncated, or contaminate totals and costs.
            common = dict(user_id=user_id, model_name="synthetic", provider_source="system",
                          purpose="generation", status="completed", retry_count=0,
                          started_at=datetime.now(timezone.utc), completed_at=datetime.now(timezone.utc))
            for operation in ("chat", "stream", "structured", "vision", "chat:generate"):
                db.add(ModelCallRun(**common, operation=operation, usage_json=record.usage_json))
            for index in range(1001):
                db.add(ModelCallRun(**{**common, "status": "failed", "retry_count": 9},
                                    operation=("embedding", "rerank", "web_search", "chatty")[index % 4],
                                    usage_json={"cost_status": "estimated", "currency": "USD", "estimated_cost": "99"}))
            db.commit()
            report = get_usage_report(db, user_id, 7, 30)
            assert report.call_count == len(report.recent) == 6
            assert report.truncated is False
            assert report.failed_count == 0 and report.retry_count == 1
            assert report.totals.known_input_tokens == 600
            assert report.cost_subtotals == {}
        finally:
            db.rollback()
            if user_id is not None:
                db.execute(delete(User).where(User.id == user_id))
                db.commit()
    print("Model usage migration, unknown semantics and audit persistence passed")


if __name__ == "__main__":
    main()

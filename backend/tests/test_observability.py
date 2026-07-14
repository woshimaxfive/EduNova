from fastapi import FastAPI
from opentelemetry import trace
from sqlalchemy import create_engine

from backend.app.core.config import Settings
from backend.app.core.observability import configure_observability, get_tracer


def test_observability_is_noop_without_otlp_endpoint() -> None:
    application = FastAPI()
    engine = create_engine("sqlite+pysqlite:///:memory:")
    configure_observability(application, engine, Settings(otel_exporter_otlp_endpoint=""))

    span = get_tracer("test").start_span("safe-test")
    try:
        assert span.is_recording() is False
        assert trace.get_current_span().get_span_context().is_valid is False
    finally:
        span.end()

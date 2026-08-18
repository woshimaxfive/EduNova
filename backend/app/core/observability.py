from __future__ import annotations

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from sqlalchemy import Engine

from backend.app.core.config import Settings


_dependencies_instrumented = False
_provider_configured = False


def configure_observability(application: FastAPI, engine: Engine, settings: Settings) -> None:
    """Enable safe standard spans; the empty endpoint remains a no-op export policy."""
    global _dependencies_instrumented, _provider_configured
    endpoint = settings.otel_exporter_otlp_endpoint.strip()
    if endpoint and not _provider_configured:
        provider = TracerProvider(
            resource=Resource.create(
                {
                    "service.name": settings.otel_service_name,
                    "deployment.environment.name": settings.app_env,
                }
            )
        )
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
        trace.set_tracer_provider(provider)
        _provider_configured = True

    FastAPIInstrumentor.instrument_app(application, excluded_urls="/api/health")
    if not _dependencies_instrumented:
        HTTPXClientInstrumentor().instrument()
        SQLAlchemyInstrumentor().instrument(engine=engine)
        RedisInstrumentor().instrument()
        _dependencies_instrumented = True


def get_tracer(name: str = "backend.app"):
    return trace.get_tracer(name)

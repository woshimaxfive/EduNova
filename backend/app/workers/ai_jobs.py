from __future__ import annotations

from backend.app.core.config import get_settings
from backend.app.core.observability import get_tracer
from backend.app.db.session import SessionLocal
from backend.app.services.ai_jobs import AiJobService, SqlAlchemyAiJobRepository


def run_ai_job(job_id: int) -> None:
    with get_tracer(__name__).start_as_current_span(
        "edunova.ai_job.execute",
        attributes={"edunova.job.id": job_id},
    ) as span:
        with SessionLocal() as db:
            service = AiJobService(SqlAlchemyAiJobRepository(db), settings=get_settings())
            result = service.run_job(job_id)
            span.set_attribute("edunova.job.status", result.status)

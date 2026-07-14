from __future__ import annotations

from backend.app.core.config import get_settings
from backend.app.core.observability import get_tracer
from backend.app.db.session import SessionLocal
from backend.app.services.exports import ExportService, SqlAlchemyExportRepository


def run_export_job(job_id: int) -> None:
    settings = get_settings()
    with get_tracer(__name__).start_as_current_span(
        "edunova.export_job.execute",
        attributes={"edunova.job.id": job_id},
    ) as span:
        with SessionLocal() as db:
            service = ExportService(SqlAlchemyExportRepository(db), settings=settings)
            result = service.run_export_job(job_id)
            span.set_attribute("edunova.job.status", result.status)

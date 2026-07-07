from __future__ import annotations

from backend.app.core.config import get_settings
from backend.app.db.session import SessionLocal
from backend.app.services.exports import ExportService, SqlAlchemyExportRepository


def run_export_job(job_id: int) -> None:
    settings = get_settings()
    with SessionLocal() as db:
        service = ExportService(SqlAlchemyExportRepository(db), settings=settings)
        service.run_export_job(job_id)

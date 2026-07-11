from __future__ import annotations

from backend.app.core.config import get_settings
from backend.app.db.session import SessionLocal
from backend.app.services.ai_jobs import AiJobService, SqlAlchemyAiJobRepository


def run_ai_job(job_id: int) -> None:
    with SessionLocal() as db:
        service = AiJobService(SqlAlchemyAiJobRepository(db), settings=get_settings())
        service.run_job(job_id)

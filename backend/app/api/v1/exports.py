from __future__ import annotations

from urllib.parse import quote

from fastapi import Depends
from fastapi.responses import Response

from backend.app.api.contracts import TypedAPIRouter as APIRouter
from backend.app.api.errors import ApiError, api_response
from backend.app.api.v1.deps import get_current_user
from backend.app.core.config import get_settings
from backend.app.db.session import get_db_session
from backend.app.models import User
from backend.app.schemas.exports import LearningDossierExportJobRequest, LearningDossierExportRequest
from backend.app.services.exports import (
    ExportNotFoundError,
    ExportService,
    ExportValidationError,
    RqExportJobQueue,
    SqlAlchemyExportRepository,
)


router = APIRouter(prefix="/exports", tags=["exports"])


def get_export_service(db=Depends(get_db_session)) -> ExportService:
    settings = get_settings()
    return ExportService(
        SqlAlchemyExportRepository(db),
        settings=settings,
        job_queue=RqExportJobQueue(settings.redis_url, settings.export_queue_name),
    )


@router.post("/learning-dossier")
def export_learning_dossier(
    payload: LearningDossierExportRequest,
    current_user: User = Depends(get_current_user),
    service: ExportService = Depends(get_export_service),
) -> dict:
    try:
        result = service.export_learning_dossier(current_user, payload.course_id)
    except ExportNotFoundError as exc:
        raise ApiError(404, "NOT_FOUND", str(exc)) from exc
    return api_response(result.model_dump())


@router.post("/learning-dossier/jobs")
def create_learning_dossier_export_job(
    payload: LearningDossierExportJobRequest,
    current_user: User = Depends(get_current_user),
    service: ExportService = Depends(get_export_service),
) -> dict:
    try:
        result = service.create_learning_dossier_job(current_user, payload.course_id, payload.format)
    except ExportNotFoundError as exc:
        raise ApiError(404, "NOT_FOUND", str(exc)) from exc
    except ExportValidationError as exc:
        raise ApiError(400, "VALIDATION_ERROR", str(exc)) from exc
    return api_response(result.model_dump())


@router.get("/{job_id}")
def get_export_job(
    job_id: int,
    current_user: User = Depends(get_current_user),
    service: ExportService = Depends(get_export_service),
) -> dict:
    try:
        result = service.get_export_job(current_user, job_id)
    except ExportNotFoundError as exc:
        raise ApiError(404, "NOT_FOUND", str(exc)) from exc
    return api_response(result.model_dump())


@router.get("/{job_id}/download")
def download_export_job(
    job_id: int,
    current_user: User = Depends(get_current_user),
    service: ExportService = Depends(get_export_service),
) -> Response:
    try:
        job, content = service.read_export_job_file(current_user, job_id)
    except ExportNotFoundError as exc:
        raise ApiError(404, "NOT_FOUND", str(exc)) from exc
    return Response(
        content=content,
        media_type=job.content_type or "application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(job.filename or 'edunova-learning-dossier')}"},
    )

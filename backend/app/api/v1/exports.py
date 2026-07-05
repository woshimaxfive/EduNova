from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.app.api.errors import ApiError, api_response
from backend.app.api.v1.deps import get_current_user
from backend.app.db.session import get_db_session
from backend.app.models import User
from backend.app.schemas.exports import LearningDossierExportRequest
from backend.app.services.exports import ExportNotFoundError, ExportService, SqlAlchemyExportRepository


router = APIRouter(prefix="/exports", tags=["exports"])


def get_export_service(db=Depends(get_db_session)) -> ExportService:
    return ExportService(SqlAlchemyExportRepository(db))


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

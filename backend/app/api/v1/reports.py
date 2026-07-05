from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status

from backend.app.api.errors import ApiError, api_response
from backend.app.api.v1.deps import get_current_user
from backend.app.db.session import get_db_session
from backend.app.models import User
from backend.app.schemas.reports import GenerateReportRequest
from backend.app.services.reports import ReportNotFoundError, ReportService, SqlAlchemyReportRepository


router = APIRouter(prefix="/reports", tags=["reports"])


def get_report_service(db=Depends(get_db_session)) -> ReportService:
    return ReportService(SqlAlchemyReportRepository(db))


@router.post("/generate")
def generate_report(
    payload: GenerateReportRequest,
    current_user: User = Depends(get_current_user),
    service: ReportService = Depends(get_report_service),
) -> dict:
    try:
        result = service.generate_report(current_user, payload.course_id, payload.practice_session_id)
    except ReportNotFoundError as exc:
        raise ApiError(status.HTTP_404_NOT_FOUND, "NOT_FOUND", str(exc)) from exc
    return api_response(result.model_dump())


@router.get("/latest")
def get_latest_report(
    course_id: int = Query(...),
    current_user: User = Depends(get_current_user),
    service: ReportService = Depends(get_report_service),
) -> dict:
    try:
        result = service.get_latest_report(current_user, course_id)
    except ReportNotFoundError as exc:
        raise ApiError(status.HTTP_404_NOT_FOUND, "NOT_FOUND", str(exc)) from exc
    return api_response(result.model_dump())

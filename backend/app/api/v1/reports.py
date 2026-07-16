from __future__ import annotations

from fastapi import Depends, Header, Query, status

from backend.app.api.contracts import TypedAPIRouter as APIRouter
from backend.app.agents.runtime import AgentTraceRecorder
from backend.app.api.errors import ApiError, api_response
from backend.app.api.v1.deps import get_current_user
from backend.app.api.v1.ai_jobs import get_ai_job_service
from backend.app.core.config import get_settings
from backend.app.db.session import get_db_session
from backend.app.models import User
from backend.app.providers.openai_compatible import OpenAICompatibleChatProvider
from backend.app.schemas.reports import GenerateReportRequest
from backend.app.services.model_settings import ModelSettingsService, SqlAlchemyModelSettingsRepository
from backend.app.services.ai_jobs import AiJobService
from backend.app.services.reports import ReportNotFoundError, ReportService, SqlAlchemyReportRepository


router = APIRouter(prefix="/reports", tags=["reports"])


def get_report_service(db=Depends(get_db_session)) -> ReportService:
    model_service = ModelSettingsService(
        repository=SqlAlchemyModelSettingsRepository(db),
        settings=get_settings(),
        provider=OpenAICompatibleChatProvider(),
    )
    return ReportService(
        SqlAlchemyReportRepository(db),
        model_service=model_service,
        trace_recorder=AgentTraceRecorder(),
    )


@router.post("/generate", deprecated=True)
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


@router.post("/generation-jobs", status_code=status.HTTP_202_ACCEPTED)
def create_report_generation_job(
    payload: GenerateReportRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    current_user: User = Depends(get_current_user),
    service: AiJobService = Depends(get_ai_job_service),
) -> dict:
    result = service.create_report_generation_job(
        current_user,
        course_id=payload.course_id,
        practice_session_id=payload.practice_session_id,
        idempotency_key=idempotency_key,
    )
    return api_response(result.model_dump(mode="json"))


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

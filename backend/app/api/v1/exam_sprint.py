from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from backend.app.agents.runtime import AgentTraceRecorder
from backend.app.api.errors import ApiError, api_response
from backend.app.api.v1.deps import get_current_user
from backend.app.core.config import get_settings
from backend.app.db.session import get_db_session
from backend.app.models import User
from backend.app.providers.openai_compatible import OpenAICompatibleChatProvider
from backend.app.schemas.exam_sprint import GenerateExamSprintPlanRequest
from backend.app.services.exam_sprint import (
    ExamSprintNotFoundError,
    ExamSprintService,
    ExamSprintValidationError,
    SqlAlchemyExamSprintRepository,
)
from backend.app.services.model_settings import ModelSettingsService, SqlAlchemyModelSettingsRepository


router = APIRouter(prefix="/exam-sprint", tags=["exam-sprint"])


def get_exam_sprint_service(db=Depends(get_db_session)) -> ExamSprintService:
    model_service = ModelSettingsService(
        repository=SqlAlchemyModelSettingsRepository(db),
        settings=get_settings(),
        provider=OpenAICompatibleChatProvider(),
    )
    return ExamSprintService(
        SqlAlchemyExamSprintRepository(db),
        model_service=model_service,
        trace_recorder=AgentTraceRecorder(),
    )


@router.post("/plans")
def generate_exam_sprint_plan(
    payload: GenerateExamSprintPlanRequest,
    current_user: User = Depends(get_current_user),
    service: ExamSprintService = Depends(get_exam_sprint_service),
) -> dict:
    try:
        result = service.generate_plan(
            current_user,
            course_id=payload.course_id,
            duration_days=payload.duration_days,
            material_ids=payload.material_ids,
            comparison_id=payload.comparison_id,
            goal=payload.goal,
        )
    except ExamSprintNotFoundError as exc:
        raise ApiError(404, "NOT_FOUND", str(exc)) from exc
    except ExamSprintValidationError as exc:
        raise ApiError(400, "VALIDATION_ERROR", str(exc)) from exc
    return api_response(result.model_dump())


@router.get("/plans/current")
def get_current_exam_sprint_plan(
    course_id: int = Query(...),
    current_user: User = Depends(get_current_user),
    service: ExamSprintService = Depends(get_exam_sprint_service),
) -> dict:
    try:
        result = service.get_current_plan(current_user, course_id)
    except ExamSprintNotFoundError as exc:
        raise ApiError(404, "NOT_FOUND", str(exc)) from exc
    return api_response(result.model_dump() if result is not None else None)


@router.get("/plans/{plan_id}")
def get_exam_sprint_plan(
    plan_id: int,
    current_user: User = Depends(get_current_user),
    service: ExamSprintService = Depends(get_exam_sprint_service),
) -> dict:
    try:
        result = service.get_plan(current_user, plan_id)
    except ExamSprintNotFoundError as exc:
        raise ApiError(404, "NOT_FOUND", str(exc)) from exc
    return api_response(result.model_dump())

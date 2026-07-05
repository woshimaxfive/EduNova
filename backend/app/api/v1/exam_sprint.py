from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.app.api.errors import ApiError, api_response
from backend.app.api.v1.deps import get_current_user
from backend.app.db.session import get_db_session
from backend.app.models import User
from backend.app.schemas.exam_sprint import GenerateExamSprintPlanRequest
from backend.app.services.exam_sprint import (
    ExamSprintNotFoundError,
    ExamSprintService,
    ExamSprintValidationError,
    SqlAlchemyExamSprintRepository,
)


router = APIRouter(prefix="/exam-sprint", tags=["exam-sprint"])


def get_exam_sprint_service(db=Depends(get_db_session)) -> ExamSprintService:
    return ExamSprintService(SqlAlchemyExamSprintRepository(db))


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
            goal=payload.goal,
        )
    except ExamSprintNotFoundError as exc:
        raise ApiError(404, "NOT_FOUND", str(exc)) from exc
    except ExamSprintValidationError as exc:
        raise ApiError(400, "VALIDATION_ERROR", str(exc)) from exc
    return api_response(result.model_dump())


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

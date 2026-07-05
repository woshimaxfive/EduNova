from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from backend.app.api.errors import ApiError, api_response
from backend.app.api.v1.deps import get_current_user
from backend.app.db.session import get_db_session
from backend.app.models import User
from backend.app.schemas.paths import GeneratePathRequest, UpdatePathTaskRequest
from backend.app.services.paths import PathNotFoundError, PathService, PathValidationError, SqlAlchemyPathRepository


router = APIRouter(prefix="/paths", tags=["paths"])


def get_path_service(db=Depends(get_db_session)) -> PathService:
    return PathService(SqlAlchemyPathRepository(db))


@router.post("/generate")
def generate_path(
    payload: GeneratePathRequest,
    current_user: User = Depends(get_current_user),
    service: PathService = Depends(get_path_service),
) -> dict:
    try:
        return api_response(
            service.generate_path(
                current_user,
                course_id=payload.course_id,
                duration_days=payload.duration_days,
                goal=payload.goal,
            ).model_dump()
        )
    except PathNotFoundError as exc:
        raise ApiError(404, "NOT_FOUND", str(exc)) from exc
    except PathValidationError as exc:
        raise ApiError(400, "VALIDATION_ERROR", str(exc)) from exc


@router.get("/current")
def get_current_path(
    course_id: int = Query(...),
    current_user: User = Depends(get_current_user),
    service: PathService = Depends(get_path_service),
) -> dict:
    try:
        return api_response(service.get_current_path(current_user, course_id).model_dump())
    except PathNotFoundError as exc:
        raise ApiError(404, "NOT_FOUND", str(exc)) from exc


@router.patch("/tasks/{task_id}")
def update_path_task(
    task_id: int,
    payload: UpdatePathTaskRequest,
    current_user: User = Depends(get_current_user),
    service: PathService = Depends(get_path_service),
) -> dict:
    try:
        return api_response(service.update_task_status(current_user, task_id, payload.status).model_dump())
    except PathNotFoundError as exc:
        raise ApiError(404, "NOT_FOUND", str(exc)) from exc
    except PathValidationError as exc:
        raise ApiError(400, "VALIDATION_ERROR", str(exc)) from exc

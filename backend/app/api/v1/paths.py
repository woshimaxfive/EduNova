from __future__ import annotations

from fastapi import Depends, Header, Query

from backend.app.api.contracts import TypedAPIRouter as APIRouter
from backend.app.agents.runtime import AgentTraceRecorder
from backend.app.api.errors import ApiError, api_response
from backend.app.api.v1.deps import get_current_user
from backend.app.api.v1.ai_jobs import get_ai_job_service
from backend.app.core.config import get_settings
from backend.app.db.session import get_db_session
from backend.app.models import User
from backend.app.providers.openai_compatible import OpenAICompatibleChatProvider
from backend.app.schemas.paths import GeneratePathRequest, UpdatePathTaskRequest
from backend.app.services.model_settings import ModelSettingsService, SqlAlchemyModelSettingsRepository
from backend.app.services.ai_jobs import AiJobService
from backend.app.services.paths import PathNotFoundError, PathService, PathValidationError, SqlAlchemyPathRepository


router = APIRouter(prefix="/paths", tags=["paths"])


def get_path_service(db=Depends(get_db_session)) -> PathService:
    model_service = ModelSettingsService(
        repository=SqlAlchemyModelSettingsRepository(db),
        settings=get_settings(),
        provider=OpenAICompatibleChatProvider(),
    )
    return PathService(
        SqlAlchemyPathRepository(db),
        model_service=model_service,
        trace_recorder=AgentTraceRecorder(),
    )


@router.post("/generate", deprecated=True)
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
            ).model_dump()
        )
    except PathNotFoundError as exc:
        raise ApiError(404, "NOT_FOUND", str(exc)) from exc
    except PathValidationError as exc:
        raise ApiError(400, "VALIDATION_ERROR", str(exc)) from exc


@router.post("/generation-jobs", status_code=202)
def create_path_generation_job(
    payload: GeneratePathRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    current_user: User = Depends(get_current_user),
    service: AiJobService = Depends(get_ai_job_service),
) -> dict:
    result = service.create_path_planning_job(
        current_user,
        course_id=payload.course_id,
        idempotency_key=idempotency_key,
    )
    return api_response(result.model_dump(mode="json"))


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

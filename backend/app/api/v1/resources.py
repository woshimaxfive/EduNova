from __future__ import annotations

from fastapi import Depends, Header, Query

from backend.app.api.contracts import TypedAPIRouter as APIRouter
from backend.app.api.errors import ApiError, api_response, make_trace_id
from backend.app.agents.runtime import AgentTraceRecorder
from backend.app.api.v1.deps import get_current_user
from backend.app.api.v1.ai_jobs import get_ai_job_service
from backend.app.core.config import get_settings
from backend.app.db.session import get_db_session
from backend.app.models import User
from backend.app.providers.openai_compatible import OpenAICompatibleChatProvider
from backend.app.schemas.exports import ResourceExportJobRequest
from backend.app.schemas.resources import GenerateResourcesRequest, ResourceInteractionRequest
from backend.app.services.exports import (
    ExportNotFoundError,
    ExportService,
    ExportValidationError,
    RqExportJobQueue,
    SqlAlchemyExportRepository,
)
from backend.app.services.model_settings import ModelSettingsService, SqlAlchemyModelSettingsRepository
from backend.app.services.code_verifier import HttpCodeVerifier
from backend.app.services.resources import (
    ResourceGenerationError,
    ResourceGenerationService,
    ResourceNotFoundError,
    ResourceValidationError,
    SqlAlchemyResourceRepository,
)
from backend.app.services.ai_jobs import AiJobService
from backend.app.services.resource_interactions import (
    ResourceInteractionNotFoundError,
    ResourceInteractionService,
    ResourceInteractionValidationError,
)


router = APIRouter(prefix="/resources", tags=["resources"])


def get_resource_generation_service(db=Depends(get_db_session)) -> ResourceGenerationService:
    settings = get_settings()
    model_settings_service = ModelSettingsService(
        repository=SqlAlchemyModelSettingsRepository(db),
        settings=settings,
        provider=OpenAICompatibleChatProvider(),
    )
    return ResourceGenerationService(
        repository=SqlAlchemyResourceRepository(db),
        model_settings_service=model_settings_service,
        trace_recorder=AgentTraceRecorder(),
        code_verifier=HttpCodeVerifier(settings.code_verifier_url, timeout_seconds=settings.code_verifier_timeout_seconds),
    )


def get_resource_export_service(db=Depends(get_db_session)) -> ExportService:
    settings = get_settings()
    return ExportService(
        SqlAlchemyExportRepository(db),
        settings=settings,
        job_queue=RqExportJobQueue(settings.redis_url, settings.export_queue_name),
    )


def get_resource_interaction_service(db=Depends(get_db_session)) -> ResourceInteractionService:
    return ResourceInteractionService(db)


@router.post("/generate")
def generate_resources(
    payload: GenerateResourcesRequest,
    current_user: User = Depends(get_current_user),
    service: ResourceGenerationService = Depends(get_resource_generation_service),
) -> dict:
    try:
        result = service.generate_resources(
            current_user,
            course_id=payload.course_id,
            knowledge_point_id=payload.knowledge_point_id,
            resource_types=payload.resource_types,
            learning_goal=payload.learning_goal,
            difficulty=payload.difficulty,
            generation_action=payload.generation_action,
            source_resource_id=payload.source_resource_id,
            path_task_id=payload.path_task_id,
        )
    except ResourceNotFoundError as exc:
        raise ApiError(404, "NOT_FOUND", str(exc)) from exc
    except ResourceGenerationError as exc:
        raise ApiError(503, "MODEL_GENERATION_FAILED", str(exc)) from exc
    except ResourceValidationError as exc:
        raise ApiError(400, "VALIDATION_ERROR", str(exc)) from exc

    return api_response(result.model_dump())


@router.post("/generation-jobs", status_code=202)
def create_resource_generation_job(
    payload: GenerateResourcesRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    current_user: User = Depends(get_current_user),
    service: AiJobService = Depends(get_ai_job_service),
) -> dict:
    result = service.create_resource_generation_job(
        current_user,
        course_id=payload.course_id,
        knowledge_point_id=payload.knowledge_point_id,
        resource_types=list(payload.resource_types),
        learning_goal=payload.learning_goal,
        difficulty=payload.difficulty,
        generation_action=payload.generation_action,
        source_resource_id=payload.source_resource_id,
        path_task_id=payload.path_task_id,
        idempotency_key=idempotency_key,
    )
    return api_response(result.model_dump(mode="json"))


@router.get("")
def list_resources(
    course_id: int | None = Query(default=None),
    resource_type: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    service: ResourceGenerationService = Depends(get_resource_generation_service),
) -> dict:
    try:
        result = service.list_resources(current_user, course_id=course_id, resource_type=resource_type)
    except ResourceNotFoundError as exc:
        raise ApiError(404, "NOT_FOUND", str(exc)) from exc
    except ResourceValidationError as exc:
        raise ApiError(400, "VALIDATION_ERROR", str(exc)) from exc
    return {
        **result.model_dump(),
        "trace_id": make_trace_id(),
    }


@router.get("/{resource_id}")
def get_resource(
    resource_id: int,
    current_user: User = Depends(get_current_user),
    service: ResourceGenerationService = Depends(get_resource_generation_service),
) -> dict:
    try:
        return api_response(service.get_resource(current_user, resource_id).model_dump())
    except ResourceNotFoundError as exc:
        raise ApiError(404, "NOT_FOUND", str(exc)) from exc


@router.get("/{resource_id}/quality")
def get_resource_quality(
    resource_id: int,
    current_user: User = Depends(get_current_user),
    service: ResourceGenerationService = Depends(get_resource_generation_service),
) -> dict:
    try:
        return api_response([score.model_dump() for score in service.get_resource_quality(current_user, resource_id)])
    except ResourceNotFoundError as exc:
        raise ApiError(404, "NOT_FOUND", str(exc)) from exc


@router.post("/{resource_id}/exports")
def create_resource_export_job(
    resource_id: int,
    payload: ResourceExportJobRequest,
    current_user: User = Depends(get_current_user),
    service: ExportService = Depends(get_resource_export_service),
) -> dict:
    try:
        result = service.create_resource_export_job(current_user, resource_id, payload.format)
    except ExportNotFoundError as exc:
        raise ApiError(404, "NOT_FOUND", str(exc)) from exc
    except ExportValidationError as exc:
        raise ApiError(400, "VALIDATION_ERROR", str(exc)) from exc
    return api_response(result.model_dump())


@router.get("/{resource_id}/exports")
def list_resource_export_jobs(
    resource_id: int,
    current_user: User = Depends(get_current_user),
    service: ExportService = Depends(get_resource_export_service),
) -> dict:
    try:
        jobs = service.list_resource_export_jobs(current_user, resource_id)
    except ExportNotFoundError as exc:
        raise ApiError(404, "NOT_FOUND", str(exc)) from exc
    return api_response([job.model_dump() for job in jobs])


@router.post("/{resource_id}/interactions")
def record_resource_interaction(
    resource_id: int,
    payload: ResourceInteractionRequest,
    current_user: User = Depends(get_current_user),
    service: ResourceInteractionService = Depends(get_resource_interaction_service),
) -> dict:
    try:
        return api_response(service.record(current_user, resource_id, payload).model_dump())
    except ResourceInteractionNotFoundError as exc:
        raise ApiError(404, "NOT_FOUND", str(exc)) from exc
    except ResourceInteractionValidationError as exc:
        raise ApiError(400, "VALIDATION_ERROR", str(exc)) from exc


@router.get("/{resource_id}/learning-state")
def get_resource_learning_state(
    resource_id: int,
    current_user: User = Depends(get_current_user),
    service: ResourceInteractionService = Depends(get_resource_interaction_service),
) -> dict:
    try:
        return api_response(service.state(current_user, resource_id).model_dump())
    except ResourceInteractionNotFoundError as exc:
        raise ApiError(404, "NOT_FOUND", str(exc)) from exc

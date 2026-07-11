from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Query

from backend.app.api.errors import ApiError, api_response, make_trace_id
from backend.app.agents.runtime import AgentTraceRecorder
from backend.app.api.v1.deps import get_current_user
from backend.app.api.v1.ai_jobs import get_ai_job_service, raise_ai_job_error
from backend.app.core.config import get_settings
from backend.app.db.session import get_db_session
from backend.app.models import User
from backend.app.providers.openai_compatible import OpenAICompatibleChatProvider
from backend.app.schemas.courses import CreateCourseFromMaterialsRequest
from backend.app.services.courses import (
    CourseGenerationError,
    CourseNotFoundError,
    CourseService,
    CourseWeaknessStateTransitionError,
    SqlAlchemyCourseRepository,
)
from backend.app.services.embeddings import EmbeddingService
from backend.app.services.model_settings import ModelSettingsService, SqlAlchemyModelSettingsRepository
from backend.app.services.material_retrieval import MaterialChunkingService
from backend.app.services.ai_jobs import AiJobService


router = APIRouter(prefix="/courses", tags=["courses"])


def get_course_service(db=Depends(get_db_session)) -> CourseService:
    model_settings_service = ModelSettingsService(
        repository=SqlAlchemyModelSettingsRepository(db),
        settings=get_settings(),
        provider=OpenAICompatibleChatProvider(),
    )
    return CourseService(
        SqlAlchemyCourseRepository(db),
        embedding_service=EmbeddingService(model_settings_service),
        model_service=model_settings_service,
        trace_recorder=AgentTraceRecorder(),
        chunking_service=MaterialChunkingService(),
    )


@router.get("")
def list_courses(
    source_type: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    service: CourseService = Depends(get_course_service),
) -> dict:
    result = service.list_courses(current_user, source_type=source_type)
    return {
        **result.model_dump(),
        "trace_id": make_trace_id(),
    }


@router.get("/{course_id}")
def get_course(
    course_id: int,
    current_user: User = Depends(get_current_user),
    service: CourseService = Depends(get_course_service),
) -> dict:
    try:
        return api_response(service.get_course(current_user, course_id).model_dump())
    except CourseNotFoundError as exc:
        raise ApiError(404, "NOT_FOUND", str(exc)) from exc


@router.get("/{course_id}/overview")
def get_course_overview(
    course_id: int,
    current_user: User = Depends(get_current_user),
    service: CourseService = Depends(get_course_service),
) -> dict:
    try:
        return api_response(service.get_overview(current_user, course_id).model_dump())
    except CourseNotFoundError as exc:
        raise ApiError(404, "NOT_FOUND", str(exc)) from exc


@router.get("/{course_id}/knowledge-points")
def get_course_knowledge_points(
    course_id: int,
    current_user: User = Depends(get_current_user),
    service: CourseService = Depends(get_course_service),
) -> dict:
    try:
        return api_response([point.model_dump() for point in service.get_knowledge_points(current_user, course_id)])
    except CourseNotFoundError as exc:
        raise ApiError(404, "NOT_FOUND", str(exc)) from exc


@router.get("/{course_id}/mastery-map")
def get_course_mastery_map(
    course_id: int,
    current_user: User = Depends(get_current_user),
    service: CourseService = Depends(get_course_service),
) -> dict:
    try:
        return api_response(service.get_mastery_map(current_user, course_id).model_dump())
    except CourseNotFoundError as exc:
        raise ApiError(404, "NOT_FOUND", str(exc)) from exc


@router.get("/{course_id}/learning-state")
def get_course_learning_state(
    course_id: int,
    current_user: User = Depends(get_current_user),
    service: CourseService = Depends(get_course_service),
) -> dict:
    try:
        return api_response(service.get_learning_state(current_user, course_id).model_dump())
    except CourseNotFoundError as exc:
        raise ApiError(404, "NOT_FOUND", str(exc)) from exc


def _update_weakness_review_item(
    course_id: int,
    item_id: int,
    action: str,
    current_user: User,
    service: CourseService,
) -> dict:
    try:
        return api_response(service.update_weakness_review_item(current_user, course_id, item_id, action).model_dump())
    except CourseNotFoundError as exc:
        raise ApiError(404, "NOT_FOUND", str(exc)) from exc
    except CourseWeaknessStateTransitionError as exc:
        raise ApiError(400, "VALIDATION_ERROR", str(exc)) from exc


@router.post("/{course_id}/weakness-review-items/{item_id}/confirm")
def confirm_weakness_review_item(
    course_id: int,
    item_id: int,
    current_user: User = Depends(get_current_user),
    service: CourseService = Depends(get_course_service),
) -> dict:
    return _update_weakness_review_item(course_id, item_id, "confirm", current_user, service)


@router.post("/{course_id}/weakness-review-items/{item_id}/start")
def start_weakness_review_item(
    course_id: int,
    item_id: int,
    current_user: User = Depends(get_current_user),
    service: CourseService = Depends(get_course_service),
) -> dict:
    return _update_weakness_review_item(course_id, item_id, "start", current_user, service)


@router.post("/{course_id}/weakness-review-items/{item_id}/complete")
def complete_weakness_review_item(
    course_id: int,
    item_id: int,
    current_user: User = Depends(get_current_user),
    service: CourseService = Depends(get_course_service),
) -> dict:
    return _update_weakness_review_item(course_id, item_id, "complete", current_user, service)


@router.post("/{course_id}/weakness-review-items/{item_id}/dismiss")
def dismiss_weakness_review_item(
    course_id: int,
    item_id: int,
    current_user: User = Depends(get_current_user),
    service: CourseService = Depends(get_course_service),
) -> dict:
    return _update_weakness_review_item(course_id, item_id, "dismiss", current_user, service)


@router.post("/from-materials")
def create_course_from_materials(
    payload: CreateCourseFromMaterialsRequest,
    current_user: User = Depends(get_current_user),
    service: CourseService = Depends(get_course_service),
) -> dict:
    try:
        result = service.create_course_from_materials(
            current_user,
            material_ids=payload.material_ids,
            course_title=payload.course_title,
        )
    except CourseGenerationError as exc:
        raise ApiError(400, "VALIDATION_ERROR", str(exc)) from exc

    return api_response(result.model_dump())


@router.post("/from-materials/jobs", status_code=202)
def create_course_from_materials_job(
    payload: CreateCourseFromMaterialsRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    current_user: User = Depends(get_current_user),
    service: AiJobService = Depends(get_ai_job_service),
) -> dict:
    try:
        result = service.create_course_builder_job(
            current_user,
            material_ids=payload.material_ids,
            course_title=payload.course_title,
            idempotency_key=idempotency_key,
        )
    except Exception as exc:
        raise_ai_job_error(exc)
        raise
    return api_response(result.model_dump(mode="json"))

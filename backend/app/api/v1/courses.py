from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from backend.app.api.errors import ApiError, api_response, make_trace_id
from backend.app.api.v1.deps import get_current_user
from backend.app.core.config import get_settings
from backend.app.db.session import get_db_session
from backend.app.models import User
from backend.app.providers.openai_compatible import OpenAICompatibleChatProvider
from backend.app.schemas.courses import CreateCourseFromMaterialsRequest
from backend.app.services.courses import (
    CourseGenerationError,
    CourseNotFoundError,
    CourseService,
    SqlAlchemyCourseRepository,
)
from backend.app.services.embeddings import EmbeddingService
from backend.app.services.model_settings import ModelSettingsService, SqlAlchemyModelSettingsRepository


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

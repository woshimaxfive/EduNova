from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status

from backend.app.api.errors import ApiError, api_response
from backend.app.api.v1.deps import get_current_user
from backend.app.core.config import get_settings
from backend.app.db.session import get_db_session
from backend.app.models import User
from backend.app.providers.openai_compatible import OpenAICompatibleChatProvider
from backend.app.schemas.tutor import CreateTutorSessionRequest, SendTutorMessageRequest
from backend.app.services.course_answers import CourseAnswerGenerationError, CourseAnswerService
from backend.app.services.model_settings import ModelSettingsService, SqlAlchemyModelSettingsRepository
from backend.app.services.rag import RagService, SqlAlchemyRagRepository
from backend.app.services.tutor import (
    EmptyMessageError,
    InvalidSessionScopeError,
    SessionNotFoundError,
    SqlAlchemyTutorSessionRepository,
    TutorSessionService,
)


router = APIRouter(prefix="/tutor", tags=["tutor"])


def get_tutor_session_service(db=Depends(get_db_session)) -> TutorSessionService:
    model_settings_service = ModelSettingsService(
        repository=SqlAlchemyModelSettingsRepository(db),
        settings=get_settings(),
        provider=OpenAICompatibleChatProvider(),
    )
    return TutorSessionService(
        SqlAlchemyTutorSessionRepository(db),
        course_citation_searcher=RagService(SqlAlchemyRagRepository(db)),
        course_answer_generator=CourseAnswerService(model_settings_service),
    )


@router.post("/sessions")
def create_session(
    payload: CreateTutorSessionRequest,
    current_user: User = Depends(get_current_user),
    service: TutorSessionService = Depends(get_tutor_session_service),
) -> dict:
    try:
        session = service.create_session(
            user=current_user,
            scope=payload.scope,
            course_id=payload.course_id,
            mode=payload.mode,
            title=payload.title,
        )
    except InvalidSessionScopeError as exc:
        raise ApiError(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="VALIDATION_ERROR",
            message=str(exc),
        ) from exc
    except SessionNotFoundError as exc:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="NOT_FOUND",
            message="课程不存在或无权访问。",
        ) from exc

    from backend.app.schemas.tutor import session_to_summary

    return api_response(session_to_summary(session).model_dump())


@router.get("/sessions")
def list_sessions(
    scope: str = Query(default="home"),
    course_id: int | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    service: TutorSessionService = Depends(get_tutor_session_service),
) -> dict:
    try:
        sessions = service.list_sessions(user=current_user, scope=scope, course_id=course_id)
    except InvalidSessionScopeError as exc:
        raise ApiError(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="VALIDATION_ERROR",
            message=str(exc),
        ) from exc
    except SessionNotFoundError as exc:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="NOT_FOUND",
            message="课程不存在或无权访问。",
        ) from exc

    return api_response([session.model_dump() for session in sessions])


@router.get("/sessions/{session_id}")
def get_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    service: TutorSessionService = Depends(get_tutor_session_service),
) -> dict:
    try:
        detail = service.get_session(user=current_user, session_id=session_id)
    except SessionNotFoundError as exc:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="NOT_FOUND",
            message="会话不存在或无权访问。",
        ) from exc
    except CourseAnswerGenerationError as exc:
        raise ApiError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="MODEL_PROVIDER_ERROR",
            message=str(exc),
        ) from exc

    return api_response(detail.model_dump())


@router.post("/sessions/{session_id}/messages")
def send_message(
    session_id: int,
    payload: SendTutorMessageRequest,
    current_user: User = Depends(get_current_user),
    service: TutorSessionService = Depends(get_tutor_session_service),
) -> dict:
    try:
        detail = service.append_message(user=current_user, session_id=session_id, content=payload.message)
    except EmptyMessageError as exc:
        raise ApiError(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="VALIDATION_ERROR",
            message=str(exc),
        ) from exc
    except SessionNotFoundError as exc:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="NOT_FOUND",
            message="会话不存在或无权访问。",
        ) from exc

    return api_response(detail.model_dump())

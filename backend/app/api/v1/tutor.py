from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import StreamingResponse

from backend.app.agents.runtime import AgentTraceRecorder
from backend.app.api.errors import ApiError, api_response
from backend.app.api.v1.deps import get_current_user
from backend.app.core.config import get_settings
from backend.app.db.session import get_db_session
from backend.app.models import User
from backend.app.providers.openai_compatible import OpenAICompatibleChatProvider
from backend.app.schemas.tutor import (
    CreateTutorSessionRequest,
    DeleteTutorSessionResponse,
    SendTutorMessageRequest,
    UpdateTutorSessionRequest,
)
from backend.app.services.course_answers import CourseAnswerGenerationError, CourseAnswerService
from backend.app.services.embeddings import EmbeddingService
from backend.app.services.model_settings import ModelSettingsService, SqlAlchemyModelSettingsRepository
from backend.app.services.material_retrieval import MaterialRetrievalService, SqlAlchemyMaterialRetrievalRepository
from backend.app.services.profiles import ProfileService, SqlAlchemyProfileRepository
from backend.app.services.rag import RagService, SqlAlchemyRagRepository
from backend.app.services.tutor import (
    EmptyMessageError,
    InvalidSessionScopeError,
    SessionNotFoundError,
    SqlAlchemyTutorSessionRepository,
    TutorSessionService,
)
from backend.app.services.web_search import WebSearchService


router = APIRouter(prefix="/tutor", tags=["tutor"])


def get_tutor_session_service(db=Depends(get_db_session)) -> TutorSessionService:
    model_settings_service = ModelSettingsService(
        repository=SqlAlchemyModelSettingsRepository(db),
        settings=get_settings(),
        provider=OpenAICompatibleChatProvider(),
    )
    return TutorSessionService(
        SqlAlchemyTutorSessionRepository(db),
        course_citation_searcher=RagService(
            SqlAlchemyRagRepository(db),
            embedding_service=EmbeddingService(model_settings_service),
        ),
        course_answer_generator=CourseAnswerService(model_settings_service),
        profile_event_recorder=ProfileService(
            SqlAlchemyProfileRepository(db),
            model_service=model_settings_service,
            trace_recorder=AgentTraceRecorder(),
        ),
        web_search_service=WebSearchService(get_settings()),
        material_citation_searcher=MaterialRetrievalService(
            SqlAlchemyMaterialRetrievalRepository(db),
            embedding_service=EmbeddingService(model_settings_service),
        ),
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


@router.patch("/sessions/{session_id}")
def rename_session(
    session_id: int,
    payload: UpdateTutorSessionRequest,
    current_user: User = Depends(get_current_user),
    service: TutorSessionService = Depends(get_tutor_session_service),
) -> dict:
    try:
        session = service.rename_session(user=current_user, session_id=session_id, title=payload.title)
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

    return api_response(session.model_dump())


@router.delete("/sessions/{session_id}")
def delete_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    service: TutorSessionService = Depends(get_tutor_session_service),
) -> dict:
    try:
        deleted = service.delete_session(user=current_user, session_id=session_id)
    except SessionNotFoundError as exc:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="NOT_FOUND",
            message="会话不存在或无权访问。",
        ) from exc

    return api_response(DeleteTutorSessionResponse(session_id=deleted.id, deleted=True).model_dump())


@router.post("/sessions/{session_id}/messages")
def send_message(
    session_id: int,
    payload: SendTutorMessageRequest,
    current_user: User = Depends(get_current_user),
    service: TutorSessionService = Depends(get_tutor_session_service),
) -> dict:
    try:
        detail = service.append_message(
            user=current_user,
            session_id=session_id,
            content=payload.message,
            use_web_search=payload.use_web_search,
            deep_thinking=payload.deep_thinking,
            selected_material_ids=payload.selected_material_ids,
        )
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
    except CourseAnswerGenerationError as exc:
        raise ApiError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="MODEL_PROVIDER_ERROR",
            message=str(exc),
        ) from exc

    return api_response(detail.model_dump())


@router.post("/sessions/{session_id}/messages/stream")
def stream_message(
    session_id: int,
    payload: SendTutorMessageRequest,
    current_user: User = Depends(get_current_user),
    service: TutorSessionService = Depends(get_tutor_session_service),
) -> StreamingResponse:
    try:
        events = service.stream_message(
            user=current_user,
            session_id=session_id,
            content=payload.message,
            use_web_search=payload.use_web_search,
            deep_thinking=payload.deep_thinking,
            selected_material_ids=payload.selected_material_ids,
        )
    except EmptyMessageError as exc:
        raise ApiError(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="VALIDATION_ERROR",
            message=str(exc),
        ) from exc
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
            message="会话不存在或无权访问。",
        ) from exc

    def encode_events():
        for event in events:
            event_name = str(event.get("event") or "message")
            data = event.get("data", {})
            yield f"event: {event_name}\n"
            yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        encode_events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )

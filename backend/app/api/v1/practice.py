from __future__ import annotations

from fastapi import Depends, Query, status

from backend.app.api.contracts import TypedAPIRouter as APIRouter
from backend.app.agents.runtime import AgentTraceRecorder
from backend.app.api.errors import ApiError, api_response
from backend.app.api.v1.deps import get_current_user
from backend.app.core.config import get_settings
from backend.app.db.session import get_db_session
from backend.app.models import User
from backend.app.providers.openai_compatible import OpenAICompatibleChatProvider
from backend.app.schemas.practice import CreatePracticeSessionRequest, SavePracticeDraftRequest, SubmitPracticeAnswersRequest
from backend.app.services.model_settings import ModelSettingsService, SqlAlchemyModelSettingsRepository
from backend.app.services.ai_jobs import AiJobService, RqAiJobQueue, SqlAlchemyAiJobRepository
from backend.app.services.profiles import ProfileService, SqlAlchemyProfileRepository
from backend.app.services.practice import PracticeNotFoundError, PracticeService, PracticeValidationError, SqlAlchemyPracticeRepository


router = APIRouter(prefix="/practice", tags=["practice"])


def get_practice_service(db=Depends(get_db_session)) -> PracticeService:
    model_service = ModelSettingsService(
        repository=SqlAlchemyModelSettingsRepository(db),
        settings=get_settings(),
        provider=OpenAICompatibleChatProvider(),
    )
    return PracticeService(
        SqlAlchemyPracticeRepository(db),
        model_service=model_service,
        trace_recorder=AgentTraceRecorder(),
        path_service=AiJobService(
            SqlAlchemyAiJobRepository(db),
            settings=get_settings(),
            queue=RqAiJobQueue(get_settings()),
        ),
        profile_service=ProfileService(
            SqlAlchemyProfileRepository(db),
            model_service=model_service,
            trace_recorder=AgentTraceRecorder(),
        ),
    )


@router.post("/sessions")
def create_practice_session(
    payload: CreatePracticeSessionRequest,
    current_user: User = Depends(get_current_user),
    service: PracticeService = Depends(get_practice_service),
) -> dict:
    try:
        result = service.create_session(
            current_user,
            course_id=payload.course_id,
            knowledge_point_ids=payload.knowledge_point_ids,
            question_count=payload.question_count,
            difficulty=payload.difficulty,
        )
    except PracticeNotFoundError as exc:
        raise ApiError(status.HTTP_404_NOT_FOUND, "NOT_FOUND", str(exc)) from exc
    except PracticeValidationError as exc:
        raise ApiError(status.HTTP_400_BAD_REQUEST, "VALIDATION_ERROR", str(exc)) from exc
    return api_response(result.model_dump())


@router.get("/sessions/latest")
def get_latest_practice_session(
    course_id: int,
    current_user: User = Depends(get_current_user),
    service: PracticeService = Depends(get_practice_service),
) -> dict:
    try:
        result = service.get_latest_session(current_user, course_id)
    except PracticeNotFoundError as exc:
        raise ApiError(status.HTTP_404_NOT_FOUND, "NOT_FOUND", str(exc)) from exc
    return api_response(result.model_dump() if result is not None else None)


@router.get("/sessions/recent")
def list_recent_completed_practice_sessions(
    course_id: int,
    limit: int = Query(default=5, ge=1, le=20),
    current_user: User = Depends(get_current_user),
    service: PracticeService = Depends(get_practice_service),
) -> dict:
    try:
        result = service.list_recent_completed_sessions(current_user, course_id, limit)
    except PracticeNotFoundError as exc:
        raise ApiError(status.HTTP_404_NOT_FOUND, "NOT_FOUND", str(exc)) from exc
    return api_response([item.model_dump() for item in result])


@router.get("/sessions/{session_id}")
def get_practice_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    service: PracticeService = Depends(get_practice_service),
) -> dict:
    try:
        result = service.get_session(current_user, session_id)
    except PracticeNotFoundError as exc:
        raise ApiError(status.HTTP_404_NOT_FOUND, "NOT_FOUND", str(exc)) from exc
    return api_response(result.model_dump())


@router.patch("/sessions/{session_id}/draft")
def save_practice_draft(
    session_id: int,
    payload: SavePracticeDraftRequest,
    current_user: User = Depends(get_current_user),
    service: PracticeService = Depends(get_practice_service),
) -> dict:
    try:
        result = service.save_draft(current_user, session_id, payload.answers)
    except PracticeNotFoundError as exc:
        raise ApiError(status.HTTP_404_NOT_FOUND, "NOT_FOUND", str(exc)) from exc
    except PracticeValidationError as exc:
        raise ApiError(status.HTTP_400_BAD_REQUEST, "VALIDATION_ERROR", str(exc)) from exc
    return api_response(result.model_dump())


@router.post("/sessions/{session_id}/answers")
def submit_practice_answers(
    session_id: int,
    payload: SubmitPracticeAnswersRequest,
    current_user: User = Depends(get_current_user),
    service: PracticeService = Depends(get_practice_service),
) -> dict:
    try:
        result = service.submit_answers(current_user, session_id, payload.answers)
    except PracticeNotFoundError as exc:
        raise ApiError(status.HTTP_404_NOT_FOUND, "NOT_FOUND", str(exc)) from exc
    except PracticeValidationError as exc:
        raise ApiError(status.HTTP_400_BAD_REQUEST, "VALIDATION_ERROR", str(exc)) from exc
    return api_response(result.model_dump())


@router.post("/sessions/{session_id}/regrade")
def regrade_practice_answers(
    session_id: int,
    current_user: User = Depends(get_current_user),
    service: PracticeService = Depends(get_practice_service),
) -> dict:
    try:
        result = service.regrade_answers(current_user, session_id)
    except PracticeNotFoundError as exc:
        raise ApiError(status.HTTP_404_NOT_FOUND, "NOT_FOUND", str(exc)) from exc
    return api_response(result.model_dump())

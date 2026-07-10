from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from backend.app.api.errors import api_response
from backend.app.agents.runtime import AgentTraceRecorder
from backend.app.core.config import get_settings
from backend.app.api.v1.deps import get_current_user
from backend.app.db.session import get_db_session
from backend.app.models import User
from backend.app.providers.openai_compatible import OpenAICompatibleChatProvider
from backend.app.schemas.profiles import ProfileChatRequest
from backend.app.services.profiles import ProfileService, SqlAlchemyProfileRepository
from backend.app.services.model_settings import ModelSettingsService, SqlAlchemyModelSettingsRepository


router = APIRouter(prefix="/profiles", tags=["profiles"])


def get_profile_service(db=Depends(get_db_session)) -> ProfileService:
    model_service = ModelSettingsService(
        repository=SqlAlchemyModelSettingsRepository(db),
        settings=get_settings(),
        provider=OpenAICompatibleChatProvider(),
    )
    return ProfileService(
        SqlAlchemyProfileRepository(db),
        model_service=model_service,
        trace_recorder=AgentTraceRecorder(),
    )


@router.get("/me")
def get_my_profile(
    current_user: User = Depends(get_current_user),
    service: ProfileService = Depends(get_profile_service),
) -> dict:
    return api_response(service.get_my_profile(current_user).model_dump())


@router.post("/chat")
def update_profile_by_chat(
    payload: ProfileChatRequest,
    current_user: User = Depends(get_current_user),
    service: ProfileService = Depends(get_profile_service),
) -> dict:
    return api_response(service.update_by_chat(current_user, payload.message).model_dump())


@router.get("/events")
def list_profile_events(
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    service: ProfileService = Depends(get_profile_service),
) -> dict:
    return api_response([event.model_dump() for event in service.list_events(current_user, limit=limit)])

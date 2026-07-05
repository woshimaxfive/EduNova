from __future__ import annotations

from fastapi import APIRouter, Depends, status

from backend.app.api.errors import ApiError, api_response
from backend.app.api.v1.deps import get_current_user
from backend.app.db.session import get_db_session
from backend.app.models import User
from backend.app.services.agents import (
    AgentTraceNotFoundError,
    AgentTraceService,
    SqlAlchemyAgentTraceRepository,
)


router = APIRouter(prefix="/agents", tags=["agents"])


def get_agent_trace_service(db=Depends(get_db_session)) -> AgentTraceService:
    return AgentTraceService(SqlAlchemyAgentTraceRepository(db))


@router.get("/traces/{trace_id}")
def get_agent_trace(
    trace_id: str,
    current_user: User = Depends(get_current_user),
    service: AgentTraceService = Depends(get_agent_trace_service),
) -> dict:
    try:
        trace = service.get_trace(current_user, trace_id)
    except AgentTraceNotFoundError as exc:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="NOT_FOUND",
            message="Agent 执行轨迹不存在。",
        ) from exc

    return api_response(trace.model_dump())

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse

from backend.app.api.errors import ApiError, api_response
from backend.app.api.v1.deps import get_current_user
from backend.app.core.config import get_settings
from backend.app.db.session import SessionLocal, get_db_session
from backend.app.models import User
from backend.app.services.ai_jobs import (
    AiJobConflictError,
    AiJobNotFoundError,
    AiJobService,
    AiJobValidationError,
    RqAiJobQueue,
    SqlAlchemyAiJobRepository,
)


router = APIRouter(prefix="/ai-jobs", tags=["ai-jobs"])


def get_ai_job_service(db=Depends(get_db_session)) -> AiJobService:
    settings = get_settings()
    return AiJobService(
        SqlAlchemyAiJobRepository(db),
        settings=settings,
        queue=RqAiJobQueue(settings),
    )


def raise_ai_job_error(exc: Exception) -> None:
    if isinstance(exc, AiJobNotFoundError):
        raise ApiError(404, "NOT_FOUND", str(exc)) from exc
    if isinstance(exc, AiJobValidationError):
        raise ApiError(400, "VALIDATION_ERROR", str(exc)) from exc
    if isinstance(exc, AiJobConflictError):
        raise ApiError(409, "CONFLICT", str(exc)) from exc
    raise exc


@router.get("")
def list_ai_jobs(
    status: str = Query(default="active"),
    limit: int = Query(default=20, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    service: AiJobService = Depends(get_ai_job_service),
) -> dict:
    return api_response(service.list_jobs(current_user, status_filter=status, limit=limit).model_dump(mode="json"))


@router.get("/{job_id}")
def get_ai_job(
    job_id: int,
    current_user: User = Depends(get_current_user),
    service: AiJobService = Depends(get_ai_job_service),
) -> dict:
    try:
        return api_response(service.get_job(current_user, job_id).model_dump(mode="json"))
    except Exception as exc:
        raise_ai_job_error(exc)
        raise


@router.post("/{job_id}/cancel")
def cancel_ai_job(
    job_id: int,
    current_user: User = Depends(get_current_user),
    service: AiJobService = Depends(get_ai_job_service),
) -> dict:
    try:
        return api_response(service.cancel_job(current_user, job_id).model_dump(mode="json"))
    except Exception as exc:
        raise_ai_job_error(exc)
        raise


@router.post("/{job_id}/retry", status_code=202)
def retry_ai_job(
    job_id: int,
    current_user: User = Depends(get_current_user),
    service: AiJobService = Depends(get_ai_job_service),
) -> dict:
    try:
        return api_response(service.retry_job(current_user, job_id).model_dump(mode="json"))
    except Exception as exc:
        raise_ai_job_error(exc)
        raise


@router.get("/{job_id}/events")
async def stream_ai_job_events(
    job_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    service: AiJobService = Depends(get_ai_job_service),
) -> StreamingResponse:
    try:
        service.get_job(current_user, job_id)
    except Exception as exc:
        raise_ai_job_error(exc)
        raise

    user_id = int(current_user.id)

    async def events():
        previous_payload = ""
        heartbeat_ticks = 0
        while not await request.is_disconnected():
            with SessionLocal() as db:
                stream_service = AiJobService(
                    SqlAlchemyAiJobRepository(db),
                    settings=get_settings(),
                    queue=RqAiJobQueue(get_settings()),
                )
                stream_user = db.get(User, user_id)
                if stream_user is None:
                    return
                try:
                    job = stream_service.get_job(stream_user, job_id)
                except AiJobNotFoundError:
                    return
            payload = json.dumps(job.model_dump(mode="json"), ensure_ascii=False, separators=(",", ":"))
            if payload != previous_payload:
                yield f"event: snapshot\ndata: {payload}\n\n"
                previous_payload = payload
            if job.status == "completed":
                yield f"event: done\ndata: {payload}\n\n"
                return
            if job.status == "failed":
                yield f"event: error\ndata: {payload}\n\n"
                return
            if job.status == "cancelled":
                yield f"event: cancelled\ndata: {payload}\n\n"
                return
            heartbeat_ticks += 1
            if heartbeat_ticks >= 15:
                heartbeat_ticks = 0
                yield ": heartbeat\n\n"
            await asyncio.sleep(1)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

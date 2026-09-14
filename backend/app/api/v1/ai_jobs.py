from __future__ import annotations

import asyncio
from fastapi import Depends, Header, Query, Request, Response
from sse_starlette import EventSourceResponse

from backend.app.api.contracts import TypedAPIRouter as APIRouter
from backend.app.api.errors import api_response
from backend.app.api.sse import event_source_response, sse_event
from backend.app.api.v1.deps import get_current_user
from backend.app.core.config import get_settings
from backend.app.db.session import SessionLocal, get_db_session
from backend.app.models import User
from backend.app.services.ai_jobs import AiJobNotFoundError, AiJobService, RqAiJobQueue, SqlAlchemyAiJobRepository
from backend.app.schemas.run_history import SnapshotOperationRequest, BranchRunRequest
from backend.app.services.run_history import RunHistoryService


router = APIRouter(prefix="/ai-jobs", tags=["ai-jobs"])


def get_ai_job_service(db=Depends(get_db_session)) -> AiJobService:
    settings = get_settings()
    return AiJobService(
        SqlAlchemyAiJobRepository(db),
        settings=settings,
        queue=RqAiJobQueue(settings),
    )


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
    return api_response(service.get_job(current_user, job_id).model_dump(mode="json"))


@router.post("/{job_id}/cancel")
def cancel_ai_job(
    job_id: int,
    current_user: User = Depends(get_current_user),
    service: AiJobService = Depends(get_ai_job_service),
) -> dict:
    return api_response(service.cancel_job(current_user, job_id).model_dump(mode="json"))


@router.post("/{job_id}/snapshot")
def capture_run_snapshot(job_id: int, current_user: User = Depends(get_current_user), service: AiJobService = Depends(get_ai_job_service)) -> dict:
    return api_response(RunHistoryService(service).capture(current_user, job_id).model_dump())


@router.get("/{job_id}/replay")
def replay_run_snapshot(job_id: int, current_user: User = Depends(get_current_user), service: AiJobService = Depends(get_ai_job_service)) -> dict:
    return api_response(RunHistoryService(service).replay(current_user, job_id).model_dump())


@router.post("/{job_id}/branch")
def branch_run_snapshot(job_id: int, payload: BranchRunRequest, current_user: User = Depends(get_current_user), service: AiJobService = Depends(get_ai_job_service)) -> dict:
    return api_response(RunHistoryService(service).branch(current_user, job_id, payload).model_dump())


@router.post("/{job_id}/reexecute", status_code=202)
def reexecute_run_snapshot(job_id: int, payload: SnapshotOperationRequest, idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=1, max_length=80),
                          current_user: User = Depends(get_current_user), service: AiJobService = Depends(get_ai_job_service)) -> dict:
    return api_response(RunHistoryService(service).reexecute(current_user, job_id, payload.expected_digest, idempotency_key).model_dump())


@router.post("/{job_id}/retry", status_code=202)
def retry_ai_job(
    job_id: int,
    current_user: User = Depends(get_current_user),
    service: AiJobService = Depends(get_ai_job_service),
) -> dict:
    return api_response(service.retry_job(current_user, job_id).model_dump(mode="json"))


@router.delete("/{job_id}", status_code=204)
def delete_ai_job(
    job_id: int,
    current_user: User = Depends(get_current_user),
    service: AiJobService = Depends(get_ai_job_service),
) -> Response:
    service.delete_job(current_user, job_id)
    return Response(status_code=204)


@router.get("/{job_id}/events")
async def stream_ai_job_events(
    job_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    service: AiJobService = Depends(get_ai_job_service),
) -> EventSourceResponse:
    service.get_job(current_user, job_id)

    user_id = int(current_user.id)

    async def events():
        previous_payload = ""
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
            data = job.model_dump(mode="json")
            payload = job.model_dump_json()
            if payload != previous_payload:
                yield sse_event("snapshot", data)
                previous_payload = payload
            if job.status == "completed":
                yield sse_event("done", data)
                return
            if job.status == "failed":
                yield sse_event("error", data)
                return
            if job.status == "cancelled":
                yield sse_event("cancelled", data)
                return
            await asyncio.sleep(1)

    return event_source_response(events())

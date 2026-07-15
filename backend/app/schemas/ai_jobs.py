from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from backend.app.models import AiJob


AiJobWorkflow = Literal["course_builder", "resource_generation", "embedding_reindex", "material_ingestion", "path_planning"]
AiJobStatus = Literal["queued", "running", "cancelling", "cancelled", "completed", "failed"]


class AiJobStep(BaseModel):
    name: str
    label: str
    status: str
    progress_percent: int = Field(ge=0, le=100)
    resource_type: str | None = None
    updated_at: str


class AiJobResponse(BaseModel):
    job_id: str
    workflow: AiJobWorkflow
    status: AiJobStatus
    course_id: str | None
    retry_of_job_id: str | None
    progress_percent: int = Field(ge=0, le=100)
    stage: str
    label: str
    steps: list[AiJobStep]
    agent_trace_id: str
    request: dict[str, Any]
    result: dict[str, Any]
    warnings: list[str]
    error_code: str | None
    error_message: str | None
    attempt_count: int
    can_cancel: bool
    can_retry: bool
    created_at: str
    updated_at: str
    started_at: str | None
    completed_at: str | None


class AiJobListResponse(BaseModel):
    data: list[AiJobResponse]
    total: int


def iso_timestamp(value: datetime | None) -> str | None:
    if value is None:
        return None
    timestamp = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return timestamp.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def ai_job_to_api(job: AiJob, *, max_retries: int = 3) -> AiJobResponse:
    progress = dict(job.progress_json or {})
    steps = progress.get("steps") if isinstance(progress.get("steps"), list) else []
    result = dict(job.result_json or {})
    return AiJobResponse(
        job_id=str(job.id),
        workflow=job.workflow,
        status=job.status,
        course_id=str(job.course_id) if job.course_id is not None else None,
        retry_of_job_id=str(job.retry_of_job_id) if job.retry_of_job_id is not None else None,
        progress_percent=max(0, min(100, int(job.progress_percent or 0))),
        stage=job.stage,
        label=job.label,
        steps=[AiJobStep(**item) for item in steps if isinstance(item, dict)],
        agent_trace_id=job.agent_trace_id,
        request=dict(job.request_json or {}),
        result=result,
        warnings=[str(item) for item in result.get("warnings", []) if str(item).strip()],
        error_code=job.error_code,
        error_message=job.error_message,
        attempt_count=int(job.attempt_count or 0),
        can_cancel=job.status in {"queued", "running", "cancelling"},
        can_retry=job.status in {"failed", "cancelled"} and int(job.attempt_count or 0) < max_retries,
        created_at=iso_timestamp(job.created_at) or "",
        updated_at=iso_timestamp(job.updated_at) or "",
        started_at=iso_timestamp(job.started_at),
        completed_at=iso_timestamp(job.completed_at),
    )

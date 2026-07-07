from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from backend.app.models import GeneratedResource, LearningPath, LearningTask


PathTaskStatus = Literal["todo", "doing", "completed"]
PathTaskType = Literal["review", "learn", "resource"]


class GeneratePathRequest(BaseModel):
    course_id: int
    duration_days: Literal[3, 7, 14] = 7
    goal: str = Field(default="", max_length=500)

    @field_validator("goal")
    @classmethod
    def normalize_goal(cls, value: str) -> str:
        return " ".join(value.split())[:500]


class UpdatePathTaskRequest(BaseModel):
    status: PathTaskStatus


class PathResourceBrief(BaseModel):
    id: str
    title: str
    resource_type: str


class LearningPathTaskResponse(BaseModel):
    id: str
    path_id: str
    course_id: str
    knowledge_point_id: str | None
    title: str
    task_type: str
    reason: str | None
    recommended_resource_ids: list[str]
    recommended_resources: list[PathResourceBrief]
    status: str
    due_at: str | None
    next_review_at: str | None
    created_at: str
    updated_at: str


class LearningPathResponse(BaseModel):
    id: str
    course_id: str
    title: str
    goal: str | None
    status: str
    agent_trace_id: str | None = None
    plan_json: dict
    created_at: str
    updated_at: str


class PathEvidenceSummary(BaseModel):
    knowledge_point_count: int
    confirmed_or_reviewing_weakness_count: int
    pending_weakness_count: int
    resource_count: int
    basis: list[str]


class LearningPathDetail(BaseModel):
    course_id: str
    status: str
    message: str
    agent_trace_id: str | None = None
    path: LearningPathResponse | None
    tasks: list[LearningPathTaskResponse]
    evidence_summary: PathEvidenceSummary


def iso_timestamp(value: datetime | None) -> str | None:
    if value is None:
        return None
    timestamp = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    timestamp = timestamp.astimezone(UTC).replace(microsecond=0)
    return timestamp.isoformat().replace("+00:00", "Z")


def resource_brief(resource: GeneratedResource) -> PathResourceBrief:
    return PathResourceBrief(
        id=str(resource.id),
        title=resource.title,
        resource_type=resource.resource_type,
    )


def path_to_api(path: LearningPath) -> LearningPathResponse:
    return LearningPathResponse(
        id=str(path.id),
        course_id=str(path.course_id),
        title=path.title,
        goal=path.goal,
        status=path.status,
        agent_trace_id=getattr(path, "agent_trace_id", None),
        plan_json=path.plan_json or {},
        created_at=iso_timestamp(path.created_at) or "",
        updated_at=iso_timestamp(path.updated_at) or "",
    )


def task_to_api(task: LearningTask, resources_by_id: dict[int, GeneratedResource]) -> LearningPathTaskResponse:
    resource_ids = [int(item) for item in (task.recommended_resource_ids or []) if str(item).isdigit()]
    return LearningPathTaskResponse(
        id=str(task.id),
        path_id=str(task.path_id),
        course_id=str(task.course_id),
        knowledge_point_id=str(task.knowledge_point_id) if task.knowledge_point_id is not None else None,
        title=task.title,
        task_type=task.task_type,
        reason=task.reason,
        recommended_resource_ids=[str(resource_id) for resource_id in resource_ids],
        recommended_resources=[resource_brief(resources_by_id[resource_id]) for resource_id in resource_ids if resource_id in resources_by_id],
        status=task.status,
        due_at=iso_timestamp(task.due_at),
        next_review_at=iso_timestamp(task.next_review_at),
        created_at=iso_timestamp(task.created_at) or "",
        updated_at=iso_timestamp(task.updated_at) or "",
    )

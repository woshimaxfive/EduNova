from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

from backend.app.models import GeneratedResource, LearningPath, LearningTask
from backend.app.schemas.personalization import PersonalizationFreshnessResponse


PathTaskStatus = Literal["todo", "doing", "completed"]
PathTaskType = Literal["review", "learn", "resource"]


class GeneratePathRequest(BaseModel):
    course_id: int


class UpdatePathTaskRequest(BaseModel):
    status: PathTaskStatus


class PathResourceBrief(BaseModel):
    id: str
    title: str
    resource_type: str


class LearningBundleItem(BaseModel):
    resource_type: str
    role: str
    resource_id: str | None = None
    status: str = "recommended"
    learning_status: Literal["not_started", "in_progress", "completed"] = "not_started"


class LearningBundle(BaseModel):
    strategy: str = ""
    teaching_strategy: str = "safe_default"
    learning_problem: str = ""
    example_direction: str = ""
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    used_profile_factor_codes: list[str] = Field(default_factory=list)
    generation_mode: str = "legacy"
    rationale: str = ""
    items: list[LearningBundleItem] = Field(default_factory=list)
    ready_count: int = 0
    completed_count: int = 0


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
    learning_bundle: LearningBundle
    status: str
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
    personalization: PersonalizationFreshnessResponse | None = None
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


def path_to_api(
    path: LearningPath,
    personalization: PersonalizationFreshnessResponse | None = None,
) -> LearningPathResponse:
    return LearningPathResponse(
        id=str(path.id),
        course_id=str(path.course_id),
        title=path.title,
        goal=path.goal,
        status=path.status,
        agent_trace_id=getattr(path, "agent_trace_id", None),
        plan_json=path.plan_json or {},
        personalization=personalization,
        created_at=iso_timestamp(path.created_at) or "",
        updated_at=iso_timestamp(path.updated_at) or "",
    )


def task_to_api(
    task: LearningTask,
    resources_by_id: dict[int, GeneratedResource],
    learning_states: dict[int, Literal["not_started", "in_progress", "completed"]] | None = None,
) -> LearningPathTaskResponse:
    resource_ids = [int(item) for item in (task.recommended_resource_ids or []) if str(item).isdigit()]
    raw_bundle = task.learning_bundle_json or {}
    states = learning_states or {}
    bundle_items = []
    used_bundle_resource_ids: set[int] = set()
    for item in raw_bundle.get("items", []) if isinstance(raw_bundle.get("items"), list) else []:
        if not isinstance(item, dict):
            continue
        resource_type = str(item.get("resource_type") or "doc")
        raw_resource_id = item.get("resource_id")
        resource = resources_by_id.get(int(raw_resource_id)) if str(raw_resource_id).isdigit() else None
        if resource is None or resource.status != "completed" or resource.resource_type != resource_type:
            resource = next(
                (
                    resources_by_id[resource_id]
                    for resource_id in resource_ids
                    if resource_id not in used_bundle_resource_ids
                    and resource_id in resources_by_id
                    and resources_by_id[resource_id].status == "completed"
                    and resources_by_id[resource_id].resource_type == resource_type
                ),
                None,
            )
        resource_id = resource.id if resource is not None and resource.status == "completed" else None
        if resource_id is not None:
            used_bundle_resource_ids.add(resource_id)
        bundle_items.append(LearningBundleItem(
            resource_type=resource_type,
            role=str(item.get("role") or "辅助当前学习目标"),
            resource_id=str(resource_id) if resource_id is not None else None,
            status="available" if resource_id is not None else str(item.get("status") or "recommended"),
            learning_status=states.get(int(resource_id), "not_started") if str(resource_id).isdigit() else "not_started",
        ))
    ready_count = sum(1 for item in bundle_items if item.resource_id is not None)
    completed_count = sum(1 for item in bundle_items if item.learning_status == "completed")
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
        learning_bundle=LearningBundle(
            strategy=str(raw_bundle.get("strategy") or ""),
            teaching_strategy=str(raw_bundle.get("teaching_strategy") or "safe_default"),
            learning_problem=str(raw_bundle.get("learning_problem") or ""),
            example_direction=str(raw_bundle.get("example_direction") or ""),
            difficulty=(
                str(raw_bundle.get("difficulty"))
                if str(raw_bundle.get("difficulty")) in {"easy", "medium", "hard"}
                else "medium"
            ),
            used_profile_factor_codes=[
                str(item) for item in raw_bundle.get("used_profile_factor_codes", []) if str(item).strip()
            ],
            generation_mode=str(raw_bundle.get("generation_mode") or "legacy"),
            rationale=str(raw_bundle.get("rationale") or ""),
            items=bundle_items,
            ready_count=ready_count,
            completed_count=completed_count,
        ),
        status=task.status,
        created_at=iso_timestamp(task.created_at) or "",
        updated_at=iso_timestamp(task.updated_at) or "",
    )

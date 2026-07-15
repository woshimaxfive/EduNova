from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from backend.app.models import GeneratedResource, ResourceQualityScore
from backend.app.schemas.personalization import PersonalizationFreshnessResponse


ResourceType = Literal["doc", "mindmap", "quiz", "code", "slide", "animation", "video"]
ResourceDifficulty = Literal["easy", "medium", "hard"]
ResourceGenerationAction = Literal["new", "alternative", "refine"]


class GenerateResourcesRequest(BaseModel):
    course_id: int
    knowledge_point_id: int | None = None
    resource_types: list[ResourceType] = Field(min_length=1)
    learning_goal: str = Field(default="", max_length=500)
    difficulty: ResourceDifficulty = "medium"
    generation_action: ResourceGenerationAction = "new"
    source_resource_id: int | None = None
    path_task_id: int | None = None

    @field_validator("learning_goal")
    @classmethod
    def normalize_learning_goal(cls, value: str) -> str:
        return " ".join(value.split())[:500]

    @model_validator(mode="after")
    def validate_generation_action(self) -> GenerateResourcesRequest:
        if self.generation_action == "new" and self.source_resource_id is not None:
            raise ValueError("新建资源不能指定来源版本。")
        if self.generation_action in {"alternative", "refine"} and self.source_resource_id is None:
            raise ValueError("重新生成必须指定来源资源。")
        return self


class GeneratedResourceResponse(BaseModel):
    id: str
    course_id: str | None
    knowledge_point_id: str | None
    resource_type: str
    title: str
    content_json: dict[str, Any]
    citation_json: list[dict[str, Any]]
    status: str
    review_status: str
    confidence_score: float | None
    agent_trace_id: str | None
    version_family_id: str | None = None
    revision_of_resource_id: str | None = None
    version_number: int | None = None
    generation_action: ResourceGenerationAction = "new"
    intent_summary: dict[str, Any] | None = None
    personalization_summary: dict[str, Any] | None = None
    quality_dimensions: dict[str, Any] | None = None
    personalization: PersonalizationFreshnessResponse | None = None
    created_at: str
    updated_at: str


class ResourceQualityScoreResponse(BaseModel):
    id: str
    resource_id: str
    score_name: str
    score_value: float
    rationale: str | None
    created_at: str


class GenerateResourcesResult(BaseModel):
    agent_trace_id: str
    resources: list[GeneratedResourceResponse]
    quality_scores: dict[str, list[ResourceQualityScoreResponse]]
    warnings: list[str] = Field(default_factory=list)
    failed_resource_types: list[str] = Field(default_factory=list)


class ResourceListResponse(BaseModel):
    data: list[GeneratedResourceResponse]
    page: int
    page_size: int
    total: int


ResourceInteractionType = Literal["opened", "started", "progress", "completed", "feedback"]
ResourceFeedback = Literal["helpful", "too_easy", "too_hard", "not_helpful"]


class ResourceInteractionRequest(BaseModel):
    event_id: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    event_type: ResourceInteractionType
    path_task_id: int | None = None
    progress_percent: int | None = Field(default=None, ge=0, le=100)
    feedback: ResourceFeedback | None = None

    @model_validator(mode="after")
    def validate_event_payload(self) -> ResourceInteractionRequest:
        if self.event_type == "progress" and self.progress_percent is None:
            raise ValueError("进度事件必须提供 progress_percent。")
        if self.event_type == "feedback" and self.feedback is None:
            raise ValueError("反馈事件必须提供 feedback。")
        if self.event_type != "feedback" and self.feedback is not None:
            raise ValueError("只有反馈事件可以提供 feedback。")
        return self


class ResourceLearningStateResponse(BaseModel):
    resource_id: str
    path_task_id: str | None = None
    opened: bool = False
    started: bool = False
    completed: bool = False
    progress_percent: int = 0
    feedback: ResourceFeedback | None = None
    event_count: int = 0
    updated_at: str | None = None


def iso_timestamp(value: datetime | None) -> str:
    if value is None:
        return ""
    timestamp = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    timestamp = timestamp.astimezone(UTC).replace(microsecond=0)
    return timestamp.isoformat().replace("+00:00", "Z")


def decimal_to_float(value: Decimal | None) -> float | None:
    if value is None:
        return None
    return float(value)


def generated_resource_to_api(
    resource: GeneratedResource,
    personalization: PersonalizationFreshnessResponse | None = None,
) -> GeneratedResourceResponse:
    content_json = resource.content_json or {}
    metadata = content_json.get("metadata")
    agent_trace_id = getattr(resource, "agent_trace_id", None)
    if isinstance(metadata, dict):
        raw_trace_id = metadata.get("agent_trace_id")
        agent_trace_id = str(agent_trace_id or raw_trace_id) if agent_trace_id or raw_trace_id else None
    intent = content_json.get("intent") if isinstance(content_json.get("intent"), dict) else None
    personalization_summary = content_json.get("personalization_summary")
    if not isinstance(personalization_summary, dict):
        personalization_summary = None
    quality = content_json.get("quality") if isinstance(content_json.get("quality"), dict) else {}
    quality_dimensions = quality.get("dimensions") if isinstance(quality.get("dimensions"), dict) else None
    return GeneratedResourceResponse(
        id=str(resource.id),
        course_id=str(resource.course_id) if resource.course_id is not None else None,
        knowledge_point_id=str(resource.knowledge_point_id) if resource.knowledge_point_id is not None else None,
        resource_type=resource.resource_type,
        title=resource.title,
        content_json=content_json,
        citation_json=list(resource.citation_json or []),
        status=resource.status,
        review_status=resource.review_status,
        confidence_score=decimal_to_float(resource.confidence_score),
        agent_trace_id=agent_trace_id,
        version_family_id=resource.version_family_id,
        revision_of_resource_id=str(resource.revision_of_resource_id) if resource.revision_of_resource_id is not None else None,
        version_number=resource.version_number,
        generation_action=resource.generation_action if resource.generation_action in {"new", "alternative", "refine"} else "new",
        intent_summary=intent,
        personalization_summary=personalization_summary,
        quality_dimensions=quality_dimensions,
        personalization=personalization,
        created_at=iso_timestamp(resource.created_at),
        updated_at=iso_timestamp(resource.updated_at),
    )


def quality_score_to_api(score: ResourceQualityScore) -> ResourceQualityScoreResponse:
    return ResourceQualityScoreResponse(
        id=str(score.id),
        resource_id=str(score.resource_id),
        score_name=score.score_name,
        score_value=float(score.score_value),
        rationale=score.rationale,
        created_at=iso_timestamp(score.created_at),
    )

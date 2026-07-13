from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from backend.app.models import GeneratedResource, ResourceQualityScore
from backend.app.schemas.personalization import PersonalizationFreshnessResponse


ResourceType = Literal["doc", "mindmap", "quiz", "code", "slide", "animation"]
ResourceDifficulty = Literal["easy", "medium", "hard"]


class GenerateResourcesRequest(BaseModel):
    course_id: int
    knowledge_point_id: int | None = None
    resource_types: list[ResourceType] = Field(min_length=1)
    learning_goal: str = Field(default="", max_length=500)
    difficulty: ResourceDifficulty = "medium"

    @field_validator("learning_goal")
    @classmethod
    def normalize_learning_goal(cls, value: str) -> str:
        return " ".join(value.split())[:500]


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

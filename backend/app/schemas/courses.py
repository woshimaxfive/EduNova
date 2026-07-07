from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from backend.app.models import GeneratedResource, WeaknessReviewItem


class CreateCourseFromMaterialsRequest(BaseModel):
    material_ids: list[int] = Field(min_length=1)
    course_title: str = ""


class CourseSummary(BaseModel):
    id: str
    title: str
    description: str | None
    subject: str | None
    source_type: str
    status: str
    agent_trace_id: str | None = None
    progress_percent: int
    material_count: int
    knowledge_point_count: int
    chunk_count: int


class CourseKnowledgePoint(BaseModel):
    id: str
    title: str
    summary: str | None
    chapter: str | None
    order_index: int
    difficulty: str | None


class CourseOverview(BaseModel):
    course: CourseSummary
    materials: list[str]
    knowledge_points: list[CourseKnowledgePoint]
    chunk_count: int


class CreateCourseFromMaterialsResult(BaseModel):
    course: CourseSummary
    knowledge_points: list[CourseKnowledgePoint]


class CourseListResponse(BaseModel):
    data: list[CourseSummary]
    page: int
    page_size: int
    total: int


class CourseProfileOverlay(BaseModel):
    learning_goal: str
    knowledge_foundation: str
    weak_points: list[str]


class CourseWeaknessSummary(BaseModel):
    candidate_event_count: int
    pending_count: int
    confirmed_count: int
    reviewing_count: int
    completed_count: int
    dismissed_count: int
    latest_evidence_at: str | None


class CourseWeaknessReviewItem(BaseModel):
    id: str
    title: str
    status: str
    source_type: str
    course_id: str
    knowledge_point_id: str | None
    recommended_resource_ids: list[str]
    recommended_resources: list["CourseResourceBrief"]
    next_review_at: str | None
    created_at: str
    updated_at: str


class CourseResourceBrief(BaseModel):
    id: str
    title: str
    resource_type: str


class CoursePathSummary(BaseModel):
    status: str
    message: str
    path_id: str | None = None
    current_task_title: str | None = None
    task_count: int = 0
    completed_task_count: int = 0


class CourseMasterySummary(BaseModel):
    total_count: int
    weak_count: int
    learning_count: int
    mastered_count: int
    recommended_review_count: int
    not_started_count: int


class CourseMasteryPoint(BaseModel):
    id: str
    title: str
    chapter: str | None
    order_index: int
    status: str
    score: int
    prerequisite_ids: list[str]
    weakness_item_ids: list[str]
    recommended_resource_ids: list[str]


class CourseMasteryMap(BaseModel):
    course_id: str
    summary: CourseMasterySummary
    points: list[CourseMasteryPoint]


class CourseEvidenceSummary(BaseModel):
    candidate_event_count: int
    latest_trace_id: str | None
    latest_source_title: str | None
    latest_section_title: str | None


class CourseLearningState(BaseModel):
    course_id: str
    profile_overlay: CourseProfileOverlay
    weakness_summary: CourseWeaknessSummary
    weakness_review_queue: list[CourseWeaknessReviewItem]
    path_summary: CoursePathSummary
    mastery_summary: CourseMasterySummary
    evidence_summary: CourseEvidenceSummary


def iso_timestamp(value: datetime | None) -> str | None:
    if value is None:
        return None
    timestamp = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    timestamp = timestamp.astimezone(UTC).replace(microsecond=0)
    return timestamp.isoformat().replace("+00:00", "Z")


def resource_brief(resource: GeneratedResource) -> CourseResourceBrief:
    return CourseResourceBrief(
        id=str(resource.id),
        title=resource.title,
        resource_type=resource.resource_type,
    )


def weakness_item_to_api(
    item: WeaknessReviewItem,
    resources_by_id: dict[int, GeneratedResource] | None = None,
) -> CourseWeaknessReviewItem:
    resources_by_id = resources_by_id or {}
    resource_ids = [int(value) for value in (item.recommended_resource_ids or []) if str(value).isdigit()]
    return CourseWeaknessReviewItem(
        id=str(item.id),
        title=item.title,
        status=item.status,
        source_type=item.source_type,
        course_id=str(item.course_id),
        knowledge_point_id=str(item.knowledge_point_id) if item.knowledge_point_id is not None else None,
        recommended_resource_ids=[str(resource_id) for resource_id in resource_ids],
        recommended_resources=[resource_brief(resources_by_id[resource_id]) for resource_id in resource_ids if resource_id in resources_by_id],
        next_review_at=iso_timestamp(item.next_review_at),
        created_at=iso_timestamp(item.created_at) or "",
        updated_at=iso_timestamp(item.updated_at) or "",
    )

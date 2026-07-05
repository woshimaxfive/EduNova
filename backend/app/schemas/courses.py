from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from backend.app.models import WeaknessReviewItem


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
    next_review_at: str | None
    created_at: str
    updated_at: str


class CoursePlaceholderSummary(BaseModel):
    status: str
    message: str


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
    path_summary: CoursePlaceholderSummary
    mastery_summary: CoursePlaceholderSummary
    evidence_summary: CourseEvidenceSummary


def iso_timestamp(value: datetime | None) -> str | None:
    if value is None:
        return None
    timestamp = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    timestamp = timestamp.astimezone(UTC).replace(microsecond=0)
    return timestamp.isoformat().replace("+00:00", "Z")


def weakness_item_to_api(item: WeaknessReviewItem) -> CourseWeaknessReviewItem:
    return CourseWeaknessReviewItem(
        id=str(item.id),
        title=item.title,
        status=item.status,
        source_type=item.source_type,
        course_id=str(item.course_id),
        knowledge_point_id=str(item.knowledge_point_id) if item.knowledge_point_id is not None else None,
        next_review_at=iso_timestamp(item.next_review_at),
        created_at=iso_timestamp(item.created_at) or "",
        updated_at=iso_timestamp(item.updated_at) or "",
    )

from __future__ import annotations

from pydantic import BaseModel, Field


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

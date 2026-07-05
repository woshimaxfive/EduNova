from __future__ import annotations

from pydantic import BaseModel, Field


class MaterialUploadResult(BaseModel):
    id: str
    material_id: int
    course_id: int | None
    filename: str
    title: str
    type: str
    detail: str
    modified: str
    size: str
    parse_status: str


class MaterialListItem(BaseModel):
    id: str
    title: str
    type: str
    detail: str
    modified: str
    size: str
    category: str
    extension: str
    parse_status: str
    course_ids: list[str]


class MaterialDetail(MaterialListItem):
    filename: str
    content_type: str
    extracted_text_preview: str | None


class MaterialProgress(BaseModel):
    status: str
    progress_percent: int
    message: str


class AttachCourseMaterialsRequest(BaseModel):
    material_ids: list[int]


class AttachCourseMaterialsResult(BaseModel):
    course_id: str
    material_ids: list[str]
    attached_count: int


class CompareMaterialsRequest(BaseModel):
    course_id: int
    material_ids: list[int] = Field(min_length=2)


class MaterialComparisonSummary(BaseModel):
    compared_material_count: int
    comparable_material_count: int
    matched_concept_count: int
    citation_count: int
    message: str


class MaterialComparisonCitation(BaseModel):
    id: str
    material_id: str
    source_title: str
    section_title: str | None
    page_number: int | None
    excerpt: str
    confidence: str


class MaterialComparisonPoint(BaseModel):
    title: str
    material_ids: list[str]
    source_titles: list[str]
    reason: str
    confidence: str
    support_count: int
    knowledge_point_id: str | None = None


class MaterialComparisonResult(BaseModel):
    course_id: str
    material_ids: list[str]
    summary: MaterialComparisonSummary
    repeated_concepts: list[MaterialComparisonPoint]
    exam_likely_points: list[MaterialComparisonPoint]
    materials_only_points: list[MaterialComparisonPoint]
    questions_only_points: list[MaterialComparisonPoint]
    missing_review_points: list[MaterialComparisonPoint]
    priority_order: list[MaterialComparisonPoint]
    citations: list[MaterialComparisonCitation]

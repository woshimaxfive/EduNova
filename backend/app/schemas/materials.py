from __future__ import annotations

from pydantic import BaseModel, Field


class MaterialReviewResult(BaseModel):
    review_status: str
    confidence: float
    risk_flags: list[str] = Field(default_factory=list)
    safety_summary: str


class MaterialUploadResult(BaseModel):
    id: str
    material_id: int
    course_id: int | None
    agent_trace_id: str | None = None
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


class MaterialSectionSummary(BaseModel):
    section_title: str
    page_number: int | None
    chunk_count: int
    preview: str


class MaterialLinkedCourse(BaseModel):
    id: str
    title: str
    usage_type: str


class MaterialDetail(MaterialListItem):
    filename: str
    content_type: str
    extracted_text_preview: str | None
    chunk_count: int = 0
    section_count: int = 0
    page_count: int | None = None
    sections: list[MaterialSectionSummary] = Field(default_factory=list)
    linked_courses: list[MaterialLinkedCourse] = Field(default_factory=list)
    agent_trace_id: str | None = None


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
    id: str | None = None
    course_id: str
    material_ids: list[str]
    agent_trace_id: str | None = None
    generation_mode: str = "deterministic_source"
    review_mode: str = "rules_only"
    review_result: MaterialReviewResult | None = None
    warnings: list[str] = Field(default_factory=list)
    created_at: str | None = None
    summary: MaterialComparisonSummary
    repeated_concepts: list[MaterialComparisonPoint]
    exam_likely_points: list[MaterialComparisonPoint]
    materials_only_points: list[MaterialComparisonPoint]
    questions_only_points: list[MaterialComparisonPoint]
    missing_review_points: list[MaterialComparisonPoint]
    priority_order: list[MaterialComparisonPoint]
    citations: list[MaterialComparisonCitation]

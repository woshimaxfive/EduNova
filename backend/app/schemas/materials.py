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
    ingestion_job_id: str | None = None
    ingestion_status: str = "legacy"
    category: str = "document"
    quality_summary: dict = Field(default_factory=dict)


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
    ingestion_status: str = "legacy"
    outline_version: int = 0
    outline_confirmed: bool = False
    quality_summary: dict = Field(default_factory=dict)
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
    ingestion_status: str = "legacy"
    parser_version: str | None = None
    outline_version: int = 0
    outline_confirmed: bool = False
    quality_summary: dict = Field(default_factory=dict)


class MaterialOutlineSection(BaseModel):
    id: str
    title: str
    level: int = Field(ge=1, le=6)
    path: list[str] = Field(default_factory=list)
    start_page: int | None = None
    end_page: int | None = None
    confidence: float = Field(ge=0, le=1)
    included: bool = True
    chunk_indexes: list[int] = Field(default_factory=list)


class MaterialOutlineChunk(BaseModel):
    id: str
    chunk_index: int
    section_id: str
    section_path: list[str] = Field(default_factory=list)
    start_page: int | None = None
    end_page: int | None = None
    chunk_type: str = "body"
    content: str
    quality: dict = Field(default_factory=dict)


class MaterialOutlineResponse(BaseModel):
    material_id: str
    filename: str
    ingestion_status: str
    parser_version: str | None = None
    version: int
    confirmed: bool
    quality: dict = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    sections: list[MaterialOutlineSection] = Field(default_factory=list)
    chunks: list[MaterialOutlineChunk] = Field(default_factory=list)


class MaterialOutlineOperation(BaseModel):
    type: str
    section_id: str | None = None
    section_ids: list[str] = Field(default_factory=list)
    title: str | None = None
    included: bool | None = None
    chunk_index: int | None = None


class UpdateMaterialOutlineRequest(BaseModel):
    version: int = Field(ge=0)
    operations: list[MaterialOutlineOperation] = Field(min_length=1, max_length=50)


class ConfirmMaterialOutlineRequest(BaseModel):
    version: int = Field(ge=1)


class MaterialIngestionJobRequest(BaseModel):
    force: bool = False


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

from __future__ import annotations

from pydantic import BaseModel


class LearningDossierExportRequest(BaseModel):
    course_id: int


class LearningDossierExportJobRequest(BaseModel):
    course_id: int
    format: str = "markdown"


class ResourceExportJobRequest(BaseModel):
    format: str = "pptx"


class LearningDossierSourceSummary(BaseModel):
    has_report: bool
    report_id: str | None
    knowledge_point_count: int
    weakness_count: int
    path_task_count: int
    resource_count: int
    practice_answer_count: int


class LearningDossierExport(BaseModel):
    course_id: str
    agent_trace_id: str | None = None
    filename: str
    content_type: str
    markdown: str
    generated_at: str
    source_summary: LearningDossierSourceSummary


class ExportJobResponse(BaseModel):
    job_id: str
    status: str
    format: str
    export_type: str
    resource_id: str | None = None
    filename: str | None = None
    content_type: str | None = None
    agent_trace_id: str | None = None
    error_message: str | None = None
    created_at: str
    updated_at: str
    completed_at: str | None = None

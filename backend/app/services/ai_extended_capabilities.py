"""Wire-compatible contracts for the remaining existing AIJob runners."""
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Id = Annotated[int, Field(strict=True, gt=0)]
Count = Annotated[int, Field(strict=True, ge=0)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class CourseBuilderInput(StrictModel):
    material_ids: list[Id] = Field(min_length=1)
    course_title: str = Field(max_length=255)


class CourseBuilderOutput(StrictModel):
    course_id: Annotated[str, Field(pattern=r"^[1-9][0-9]*$")]
    knowledge_point_count: Count
    warnings: list[str]


class MaterialState(StrictModel):
    parse_status: str
    ingestion_status: str
    detail: str


class MaterialIngestionInput(StrictModel):
    material_id: Id
    force: bool = False
    previous_material_state: MaterialState | None = None


class MaterialIngestionOutput(StrictModel):
    material_id: str
    ingestion_status: str
    outline_version: Count
    section_count: Count
    chunk_count: Count
    quality: dict[str, Any]
    warnings: list[str]
    classification: dict[str, Any]


class PracticeGenerationInput(StrictModel):
    course_id: Id
    knowledge_point_ids: list[Id] = Field(min_length=1)
    question_count: int = Field(ge=1, le=10)
    difficulty: Literal["adaptive", "easy", "medium", "hard"]
    weakness_item_id: Id | None = None


class PracticeGenerationOutput(StrictModel):
    course_id: Id
    session_id: str
    question_count: Count
    agent_trace_id: str | None
    warnings: list[str]


class ReportGenerationInput(StrictModel):
    course_id: Id
    practice_session_id: Id | None = None


class ReportGenerationOutput(StrictModel):
    course_id: Id
    report_id: str
    agent_trace_id: str | None
    warnings: list[str]


class EmbeddingReindexInput(StrictModel):
    scope: Literal["all_user_chunks"]
    runtime_scope: Literal["system"] = "system"


class EmbeddingReindexOutput(StrictModel):
    embedded_chunk_count: Count
    embedding_dimension: int = Field(ge=1)
    embedding_provider: str | None = None
    embedding_model: str | None = None
    warnings: list[str]

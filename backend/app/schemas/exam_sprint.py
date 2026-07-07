from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from backend.app.models import GeneratedResource, LearningPath


ExamSprintDuration = Literal[3, 7, 14]


class GenerateExamSprintPlanRequest(BaseModel):
    course_id: int
    duration_days: ExamSprintDuration
    material_ids: list[int] = Field(default_factory=list)
    goal: str = Field(default="", max_length=500)

    @field_validator("material_ids")
    @classmethod
    def normalize_material_ids(cls, value: list[int]) -> list[int]:
        return [item for item in dict.fromkeys(value) if item > 0]

    @field_validator("goal")
    @classmethod
    def normalize_goal(cls, value: str) -> str:
        return " ".join(value.split())[:500]


class ExamSprintResourceBrief(BaseModel):
    id: str
    title: str
    resource_type: str
    knowledge_point_id: str | None


class ExamSprintPoint(BaseModel):
    knowledge_point_id: str | None
    title: str
    reason: str
    score: int
    recommended_resource_ids: list[str]
    recommended_resources: list[ExamSprintResourceBrief]


class ExamSprintDailyTask(BaseModel):
    id: str
    day_index: int
    title: str
    task_type: str
    status: str
    due_at: str | None
    knowledge_point_id: str | None
    reason: str | None
    recommended_resource_ids: list[str]
    recommended_resources: list[ExamSprintResourceBrief]


class ExamSprintQuestion(BaseModel):
    id: str
    knowledge_point_id: str | None
    title: str
    question_type: str
    prompt: str
    reason: str


class ExamSprintWarning(BaseModel):
    knowledge_point_id: str | None
    title: str
    warning: str


class ExamSprintEvidenceSummary(BaseModel):
    knowledge_point_count: int
    weakness_count: int
    practice_low_score_count: int
    resource_count: int
    report_suggestion_count: int
    material_filter_count: int
    basis: list[str]


class ExamSprintPlanResponse(BaseModel):
    id: str
    course_id: str
    agent_trace_id: str | None = None
    duration_days: int
    goal: str | None
    status: str
    high_frequency_points: list[ExamSprintPoint]
    weak_points: list[ExamSprintPoint]
    daily_tasks: list[ExamSprintDailyTask]
    must_do_questions: list[ExamSprintQuestion]
    easy_mistake_warnings: list[ExamSprintWarning]
    recommended_resources: list[ExamSprintResourceBrief]
    evidence_summary: ExamSprintEvidenceSummary
    created_at: str
    updated_at: str


def iso_timestamp(value: datetime | None) -> str | None:
    if value is None:
        return None
    timestamp = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    timestamp = timestamp.astimezone(UTC).replace(microsecond=0)
    return timestamp.isoformat().replace("+00:00", "Z")


def exam_sprint_resource_brief(resource: GeneratedResource) -> ExamSprintResourceBrief:
    return ExamSprintResourceBrief(
        id=str(resource.id),
        title=resource.title,
        resource_type=resource.resource_type,
        knowledge_point_id=str(resource.knowledge_point_id) if resource.knowledge_point_id is not None else None,
    )


def path_timestamps(path: LearningPath) -> tuple[str, str]:
    return iso_timestamp(path.created_at) or "", iso_timestamp(path.updated_at) or ""

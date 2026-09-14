from pydantic import BaseModel, Field


class TaskProgress(BaseModel):
    task_id: str
    path_id: str
    user_reported_completed: bool
    activity_completed: bool
    assessment_passed: bool
    mastered: bool
    mastery_score: int | None = None
    mastery_status: str = "not_started"
    required_activity_count: int = 0
    completed_activity_count: int = 0
    assessment_session_ids: list[str] = Field(default_factory=list)
    event_ids: list[str] = Field(default_factory=list)
    blocked_reasons: list[str] = Field(default_factory=list)
    next_step: str
    next_resource_id: str | None = None
    rule_version: str = "task-progress-v1"

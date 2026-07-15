from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


LearningNextActionStatus = Literal["ready", "waiting", "blocked"]


class LearningNextAction(BaseModel):
    kind: str
    status: LearningNextActionStatus
    label: str
    description: str
    course_id: str | None = None
    material_id: str | None = None
    knowledge_point_id: str | None = None
    path_task_id: str | None = None
    resource_id: str | None = None


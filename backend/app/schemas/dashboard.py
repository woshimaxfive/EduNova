from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from backend.app.schemas.auth import StarterMode


class ProfileSummary(BaseModel):
    display_name: str
    starter_mode: StarterMode
    has_profile: bool
    knowledge_foundation: str | None
    learning_goal: str | None


class DashboardConversation(BaseModel):
    id: str
    title: str
    meta: str
    scope: Literal["home"]
    updated_at: str


class DashboardCourse(BaseModel):
    id: str
    title: str
    source_type: str
    progress_label: str
    focus: str
    next: str


class MaterialLibrarySummary(BaseModel):
    material_count: int
    unassigned_count: int


class DashboardMaterial(BaseModel):
    id: str
    title: str
    type: str
    detail: str
    modified: str
    size: str


class DashboardResource(BaseModel):
    id: str
    title: str
    resource_type: str
    status: str
    course_id: str | None
    updated_at: str


class EvidenceSummary(BaseModel):
    citation_count: int
    latest_trace_id: str | None
    low_evidence_count: int


class EmptyState(BaseModel):
    kind: Literal["blank", "starter", "active"]
    title: str
    description: str
    action_label: str


class DashboardSummary(BaseModel):
    profile_summary: ProfileSummary
    recent_conversations: list[DashboardConversation]
    recent_courses: list[DashboardCourse]
    material_library_summary: MaterialLibrarySummary
    recent_materials: list[DashboardMaterial]
    recent_resources: list[DashboardResource]
    command_suggestions: list[str]
    evidence_summary: EvidenceSummary
    empty_state: EmptyState

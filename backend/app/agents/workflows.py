from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WorkflowSpec:
    name: str
    artifact_type: str
    steps: tuple[str, ...]
    review_required: bool = True


PROFILE_GRAPH = WorkflowSpec(
    name="profile",
    artifact_type="student_profile",
    steps=("collect_context", "extract", "evidence_gate", "review", "repair", "apply", "persist_event"),
)
COURSE_BUILDER_GRAPH = WorkflowSpec(
    name="course_builder",
    artifact_type="course",
    steps=("read_materials", "source_outline", "structure_course", "knowledge_points", "chunk", "embed", "review", "repair", "persist"),
)
MATERIAL_COMPARISON_GRAPH = WorkflowSpec(
    name="material_comparison",
    artifact_type="material_comparison",
    steps=("validate_scope", "collect_evidence", "deterministic_compare", "model_compare", "review", "repair", "persist"),
)
HOME_TUTOR_GRAPH = WorkflowSpec(
    name="home_tutor",
    artifact_type="chat_message",
    steps=("context", "route", "material_retriever", "web_search", "planner", "answer", "review", "repair", "persist"),
)
COURSE_TUTOR_GRAPH = WorkflowSpec(
    name="course_tutor",
    artifact_type="chat_message",
    steps=("profile", "retriever", "tutor", "weakness", "review", "next_action"),
)
RESOURCE_GENERATION_GRAPH = WorkflowSpec(
    name="resource_generation",
    artifact_type="generated_resource",
    steps=("profile", "retrieve", "diagnosis", "planner", "resource_worker", "aggregate", "review", "repair", "persist"),
)
PATH_PLANNING_GRAPH = WorkflowSpec(
    name="path_planning",
    artifact_type="learning_path",
    steps=("profile", "collect_evidence", "deterministic_rank", "model_plan", "review", "repair", "persist"),
)
ASSESSMENT_GRAPH = WorkflowSpec(
    name="assessment",
    artifact_type="practice_session",
    steps=(
        "context",
        "question_plan",
        "generate_questions",
        "load",
        "deterministic_score",
        "diagnose_errors",
        "sync_weaknesses",
        "review",
        "repair",
        "persist",
        "path_replan",
    ),
)
REPORT_GRAPH = WorkflowSpec(
    name="report",
    artifact_type="assessment_report",
    steps=("collect_practice", "collect_mastery", "aggregate_evidence", "generate_narrative", "review", "repair", "persist"),
)
WORKFLOW_SPECS = {
    spec.name: spec
    for spec in (
        PROFILE_GRAPH,
        COURSE_BUILDER_GRAPH,
        MATERIAL_COMPARISON_GRAPH,
        HOME_TUTOR_GRAPH,
        COURSE_TUTOR_GRAPH,
        RESOURCE_GENERATION_GRAPH,
        PATH_PLANNING_GRAPH,
        ASSESSMENT_GRAPH,
        REPORT_GRAPH,
    )
}


def workflow_steps(name: str) -> list[str]:
    return list(WORKFLOW_SPECS[name].steps)

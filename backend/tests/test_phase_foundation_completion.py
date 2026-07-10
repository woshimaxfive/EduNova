from pathlib import Path

from backend.app.db.base import Base
from backend.app.models import (
    AgentRunLog,
    AssessmentReport,
    ChatMessage,
    ChatSession,
    Course,
    CourseMaterial,
    GeneratedResource,
    LearningPath,
    LearningTask,
    Material,
    MaterialChunk,
    ModelSetting,
    PracticeAnswer,
    PracticeSession,
    ProfileEvent,
    ResourceQualityScore,
    StudentProfile,
    WeaknessReviewItem,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_phase_two_learning_closure_tables_are_registered() -> None:
    expected_tables = {
        "student_profiles",
        "profile_events",
        "learning_paths",
        "learning_tasks",
        "generated_resources",
        "resource_quality_scores",
        "agent_run_logs",
        "practice_sessions",
        "practice_answers",
        "assessment_reports",
        "weakness_review_queue",
        "chat_sessions",
        "chat_messages",
        "model_settings",
    }

    assert expected_tables <= set(Base.metadata.tables)
    assert StudentProfile.__tablename__ == "student_profiles"
    assert ProfileEvent.__tablename__ == "profile_events"
    assert LearningPath.__tablename__ == "learning_paths"
    assert LearningTask.__tablename__ == "learning_tasks"
    assert GeneratedResource.__tablename__ == "generated_resources"
    assert ResourceQualityScore.__tablename__ == "resource_quality_scores"
    assert AgentRunLog.__tablename__ == "agent_run_logs"
    assert PracticeSession.__tablename__ == "practice_sessions"
    assert PracticeAnswer.__tablename__ == "practice_answers"
    assert AssessmentReport.__tablename__ == "assessment_reports"
    assert WeaknessReviewItem.__tablename__ == "weakness_review_queue"
    assert ChatSession.__tablename__ == "chat_sessions"
    assert ChatMessage.__tablename__ == "chat_messages"
    assert ModelSetting.__tablename__ == "model_settings"
    assert MaterialChunk.__tablename__ == "material_chunks"


def test_material_chunks_migration_adds_vector_index_and_delete_cascade() -> None:
    migration_path = (
        REPO_ROOT
        / "backend"
        / "migrations"
        / "versions"
        / "20260710_0009_create_material_chunks.py"
    )

    migration_text = migration_path.read_text(encoding="utf-8")

    assert '"material_chunks"' in migration_text
    assert '"ix_material_chunks_embedding"' in migration_text
    assert 'Vector(dim=1536)' in migration_text
    assert 'ondelete="CASCADE"' in migration_text


def test_learning_artifacts_expose_nullable_agent_trace_columns() -> None:
    expected_columns = {
        Course: "courses",
        Material: "materials",
        CourseMaterial: "course_materials",
        GeneratedResource: "generated_resources",
        LearningPath: "learning_paths",
        PracticeSession: "practice_sessions",
        AssessmentReport: "assessment_reports",
    }

    for model, table_name in expected_columns.items():
        column = model.__table__.c.get("agent_trace_id")
        assert column is not None, f"{table_name} 缺少 agent_trace_id"
        assert column.nullable is True


def test_agent_trace_migration_adds_nullable_trace_columns_and_indexes() -> None:
    migration_path = (
        REPO_ROOT
        / "backend"
        / "migrations"
        / "versions"
        / "20260707_0007_add_learning_artifact_agent_trace_ids.py"
    )

    migration_text = migration_path.read_text(encoding="utf-8")

    for table_name in (
        "courses",
        "materials",
        "course_materials",
        "generated_resources",
        "learning_paths",
        "practice_sessions",
        "assessment_reports",
    ):
        assert f'"{table_name}"' in migration_text
        assert f'"ix_{table_name}_agent_trace_id"' in migration_text
    assert '"agent_trace_id"' in migration_text


def test_learning_closure_evidence_migration_adds_safe_references_and_defaults() -> None:
    migration_path = (
        REPO_ROOT
        / "backend"
        / "migrations"
        / "versions"
        / "20260710_0011_add_learning_closure_evidence.py"
    )

    migration_text = migration_path.read_text(encoding="utf-8")

    assert '"assessment_json"' in migration_text
    assert '"source_ref_type"' in migration_text
    assert '"source_ref_id"' in migration_text
    assert '"diagnosis_json"' in migration_text
    assert '"ix_weakness_review_queue_source_ref"' in migration_text
    assert "nullable=False" in migration_text
    assert "'{}'::jsonb" in migration_text

    assert PracticeSession.__table__.c.assessment_json.nullable is False
    assert WeaknessReviewItem.__table__.c.source_ref_type.nullable is True
    assert WeaknessReviewItem.__table__.c.source_ref_id.nullable is True
    assert WeaknessReviewItem.__table__.c.diagnosis_json.nullable is False


def test_phase_two_learning_closure_migration_creates_required_tables() -> None:
    migration_path = (
        REPO_ROOT
        / "backend"
        / "migrations"
        / "versions"
        / "20260701_0003_create_learning_closure_tables.py"
    )

    migration_text = migration_path.read_text(encoding="utf-8")

    for table_name in (
        "student_profiles",
        "profile_events",
        "learning_paths",
        "learning_tasks",
        "generated_resources",
        "resource_quality_scores",
        "agent_run_logs",
        "practice_sessions",
        "practice_answers",
        "assessment_reports",
        "weakness_review_queue",
        "chat_sessions",
        "chat_messages",
        "model_settings",
    ):
        assert f'"{table_name}"' in migration_text


def test_phase_one_compose_declares_frontend_and_nginx_services() -> None:
    compose_text = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert "frontend:" in compose_text
    assert "nginx:" in compose_text
    assert (REPO_ROOT / "docker" / "frontend.Dockerfile").exists()
    assert (REPO_ROOT / "docker" / "nginx.conf").exists()

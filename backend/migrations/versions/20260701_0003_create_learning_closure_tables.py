"""create learning closure tables

Revision ID: 20260701_0003
Revises: 20260701_0002
Create Date: 2026-07-01 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260701_0003"
down_revision: Union[str, Sequence[str], None] = "20260701_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def id_column() -> sa.Column:
    return sa.Column(
        "id",
        sa.BigInteger(),
        sa.Identity(always=False),
        nullable=False,
    )


def created_at_column() -> sa.Column:
    return sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        server_default=sa.text("now()"),
        nullable=False,
    )


def updated_at_column() -> sa.Column:
    return sa.Column(
        "updated_at",
        sa.DateTime(timezone=True),
        server_default=sa.text("now()"),
        nullable=False,
    )


def jsonb_column(name: str, nullable: bool = False) -> sa.Column:
    return sa.Column(name, postgresql.JSONB(astext_type=sa.Text()), nullable=nullable)


def upgrade() -> None:
    op.create_table(
        "student_profiles",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        jsonb_column("profile_json"),
        sa.Column("confidence_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("updated_reason", sa.Text(), nullable=True),
        id_column(),
        created_at_column(),
        updated_at_column(),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_student_profiles_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_student_profiles")),
        sa.UniqueConstraint("user_id", name="uq_student_profiles_user_id"),
    )
    op.create_index(
        op.f("ix_student_profiles_user_id"),
        "student_profiles",
        ["user_id"],
        unique=False,
    )

    op.create_table(
        "profile_events",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("profile_id", sa.BigInteger(), nullable=True),
        sa.Column("dimension", sa.String(length=80), nullable=False),
        sa.Column("change_summary", sa.Text(), nullable=False),
        jsonb_column("evidence_json"),
        id_column(),
        created_at_column(),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["student_profiles.id"],
            name=op.f("fk_profile_events_profile_id_student_profiles"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_profile_events_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_profile_events")),
    )
    op.create_index(
        "ix_profile_events_user_profile",
        "profile_events",
        ["user_id", "profile_id"],
        unique=False,
    )

    op.create_table(
        "learning_paths",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("course_id", sa.BigInteger(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("goal", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        jsonb_column("plan_json"),
        id_column(),
        created_at_column(),
        updated_at_column(),
        sa.ForeignKeyConstraint(
            ["course_id"],
            ["courses.id"],
            name=op.f("fk_learning_paths_course_id_courses"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_learning_paths_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_learning_paths")),
    )
    op.create_index(
        "ix_learning_paths_user_course_status",
        "learning_paths",
        ["user_id", "course_id", "status"],
        unique=False,
    )

    op.create_table(
        "learning_tasks",
        sa.Column("path_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("course_id", sa.BigInteger(), nullable=True),
        sa.Column("knowledge_point_id", sa.BigInteger(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("task_type", sa.String(length=80), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        jsonb_column("recommended_resource_ids"),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_review_at", sa.DateTime(timezone=True), nullable=True),
        id_column(),
        created_at_column(),
        updated_at_column(),
        sa.ForeignKeyConstraint(
            ["course_id"],
            ["courses.id"],
            name=op.f("fk_learning_tasks_course_id_courses"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["knowledge_point_id"],
            ["knowledge_points.id"],
            name=op.f("fk_learning_tasks_knowledge_point_id_knowledge_points"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["path_id"],
            ["learning_paths.id"],
            name=op.f("fk_learning_tasks_path_id_learning_paths"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_learning_tasks_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_learning_tasks")),
    )
    op.create_index(
        "ix_learning_tasks_path_status",
        "learning_tasks",
        ["path_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_learning_tasks_user_course_status",
        "learning_tasks",
        ["user_id", "course_id", "status"],
        unique=False,
    )

    op.create_table(
        "generated_resources",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("course_id", sa.BigInteger(), nullable=True),
        sa.Column("knowledge_point_id", sa.BigInteger(), nullable=True),
        sa.Column("resource_type", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        jsonb_column("content_json"),
        jsonb_column("citation_json"),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("review_status", sa.String(length=50), nullable=False),
        sa.Column("confidence_score", sa.Numeric(5, 2), nullable=True),
        id_column(),
        created_at_column(),
        updated_at_column(),
        sa.ForeignKeyConstraint(
            ["course_id"],
            ["courses.id"],
            name=op.f("fk_generated_resources_course_id_courses"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["knowledge_point_id"],
            ["knowledge_points.id"],
            name=op.f("fk_generated_resources_knowledge_point_id_knowledge_points"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_generated_resources_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_generated_resources")),
    )
    op.create_index(
        "ix_generated_resources_status",
        "generated_resources",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_generated_resources_user_course",
        "generated_resources",
        ["user_id", "course_id"],
        unique=False,
    )

    op.create_table(
        "resource_quality_scores",
        sa.Column("resource_id", sa.BigInteger(), nullable=False),
        sa.Column("score_name", sa.String(length=80), nullable=False),
        sa.Column("score_value", sa.Numeric(5, 2), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        id_column(),
        created_at_column(),
        sa.ForeignKeyConstraint(
            ["resource_id"],
            ["generated_resources.id"],
            name=op.f("fk_resource_quality_scores_resource_id_generated_resources"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_resource_quality_scores")),
    )
    op.create_index(
        "ix_resource_quality_scores_resource",
        "resource_quality_scores",
        ["resource_id"],
        unique=False,
    )

    op.create_table(
        "agent_run_logs",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("course_id", sa.BigInteger(), nullable=True),
        sa.Column("trace_id", sa.String(length=120), nullable=False),
        sa.Column("agent_name", sa.String(length=120), nullable=False),
        sa.Column("step_index", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("input_summary", sa.Text(), nullable=True),
        sa.Column("output_summary", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        jsonb_column("metadata_json"),
        id_column(),
        created_at_column(),
        sa.ForeignKeyConstraint(
            ["course_id"],
            ["courses.id"],
            name=op.f("fk_agent_run_logs_course_id_courses"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_agent_run_logs_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_run_logs")),
    )
    op.create_index(
        "ix_agent_run_logs_trace_id",
        "agent_run_logs",
        ["trace_id"],
        unique=False,
    )
    op.create_index(
        "ix_agent_run_logs_user_course",
        "agent_run_logs",
        ["user_id", "course_id"],
        unique=False,
    )

    op.create_table(
        "practice_sessions",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("course_id", sa.BigInteger(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("score", sa.Numeric(5, 2), nullable=True),
        id_column(),
        created_at_column(),
        updated_at_column(),
        sa.ForeignKeyConstraint(
            ["course_id"],
            ["courses.id"],
            name=op.f("fk_practice_sessions_course_id_courses"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_practice_sessions_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_practice_sessions")),
    )
    op.create_index(
        "ix_practice_sessions_user_course",
        "practice_sessions",
        ["user_id", "course_id"],
        unique=False,
    )

    op.create_table(
        "practice_answers",
        sa.Column("session_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        jsonb_column("question_json"),
        sa.Column("answer_text", sa.Text(), nullable=True),
        jsonb_column("feedback_json"),
        sa.Column("is_correct", sa.Boolean(), nullable=True),
        id_column(),
        created_at_column(),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["practice_sessions.id"],
            name=op.f("fk_practice_answers_session_id_practice_sessions"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_practice_answers_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_practice_answers")),
    )
    op.create_index(
        "ix_practice_answers_session",
        "practice_answers",
        ["session_id"],
        unique=False,
    )

    op.create_table(
        "assessment_reports",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("course_id", sa.BigInteger(), nullable=True),
        sa.Column("practice_session_id", sa.BigInteger(), nullable=True),
        jsonb_column("report_json"),
        sa.Column("score", sa.Numeric(5, 2), nullable=True),
        id_column(),
        created_at_column(),
        sa.ForeignKeyConstraint(
            ["course_id"],
            ["courses.id"],
            name=op.f("fk_assessment_reports_course_id_courses"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["practice_session_id"],
            ["practice_sessions.id"],
            name=op.f("fk_assessment_reports_practice_session_id_practice_sessions"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_assessment_reports_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assessment_reports")),
    )
    op.create_index(
        "ix_assessment_reports_user_course",
        "assessment_reports",
        ["user_id", "course_id"],
        unique=False,
    )

    op.create_table(
        "weakness_review_queue",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("course_id", sa.BigInteger(), nullable=True),
        sa.Column("knowledge_point_id", sa.BigInteger(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("source_type", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        jsonb_column("recommended_resource_ids"),
        sa.Column("next_review_at", sa.DateTime(timezone=True), nullable=True),
        id_column(),
        created_at_column(),
        updated_at_column(),
        sa.ForeignKeyConstraint(
            ["course_id"],
            ["courses.id"],
            name=op.f("fk_weakness_review_queue_course_id_courses"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["knowledge_point_id"],
            ["knowledge_points.id"],
            name=op.f("fk_weakness_review_queue_knowledge_point_id_knowledge_points"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_weakness_review_queue_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_weakness_review_queue")),
    )
    op.create_index(
        "ix_weakness_review_queue_user_course_status",
        "weakness_review_queue",
        ["user_id", "course_id", "status"],
        unique=False,
    )

    op.create_table(
        "chat_sessions",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("course_id", sa.BigInteger(), nullable=True),
        sa.Column("scope", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("mode", sa.String(length=50), nullable=False),
        sa.Column("archived_from_home", sa.Boolean(), nullable=False),
        id_column(),
        created_at_column(),
        updated_at_column(),
        sa.ForeignKeyConstraint(
            ["course_id"],
            ["courses.id"],
            name=op.f("fk_chat_sessions_course_id_courses"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_chat_sessions_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_chat_sessions")),
    )
    op.create_index(
        "ix_chat_sessions_user_scope_course",
        "chat_sessions",
        ["user_id", "scope", "course_id"],
        unique=False,
    )

    op.create_table(
        "chat_messages",
        sa.Column("session_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        jsonb_column("citation_json"),
        sa.Column("trace_id", sa.String(length=120), nullable=True),
        id_column(),
        created_at_column(),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["chat_sessions.id"],
            name=op.f("fk_chat_messages_session_id_chat_sessions"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_chat_messages_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_chat_messages")),
    )
    op.create_index(
        "ix_chat_messages_session_created",
        "chat_messages",
        ["session_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "model_settings",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("provider", sa.String(length=80), nullable=False),
        sa.Column("base_url", sa.Text(), nullable=True),
        sa.Column("api_key_ciphertext", sa.Text(), nullable=True),
        sa.Column("chat_model", sa.String(length=120), nullable=True),
        sa.Column("embedding_model", sa.String(length=120), nullable=True),
        jsonb_column("tool_flags_json"),
        id_column(),
        created_at_column(),
        updated_at_column(),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_model_settings_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_model_settings")),
        sa.UniqueConstraint("user_id", name="uq_model_settings_user_id"),
    )
    op.create_index(
        op.f("ix_model_settings_user_id"),
        "model_settings",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_model_settings_user_id"), table_name="model_settings")
    op.drop_table("model_settings")
    op.drop_index("ix_chat_messages_session_created", table_name="chat_messages")
    op.drop_table("chat_messages")
    op.drop_index("ix_chat_sessions_user_scope_course", table_name="chat_sessions")
    op.drop_table("chat_sessions")
    op.drop_index(
        "ix_weakness_review_queue_user_course_status",
        table_name="weakness_review_queue",
    )
    op.drop_table("weakness_review_queue")
    op.drop_index("ix_assessment_reports_user_course", table_name="assessment_reports")
    op.drop_table("assessment_reports")
    op.drop_index("ix_practice_answers_session", table_name="practice_answers")
    op.drop_table("practice_answers")
    op.drop_index("ix_practice_sessions_user_course", table_name="practice_sessions")
    op.drop_table("practice_sessions")
    op.drop_index("ix_agent_run_logs_user_course", table_name="agent_run_logs")
    op.drop_index("ix_agent_run_logs_trace_id", table_name="agent_run_logs")
    op.drop_table("agent_run_logs")
    op.drop_index(
        "ix_resource_quality_scores_resource",
        table_name="resource_quality_scores",
    )
    op.drop_table("resource_quality_scores")
    op.drop_index("ix_generated_resources_user_course", table_name="generated_resources")
    op.drop_index("ix_generated_resources_status", table_name="generated_resources")
    op.drop_table("generated_resources")
    op.drop_index("ix_learning_tasks_user_course_status", table_name="learning_tasks")
    op.drop_index("ix_learning_tasks_path_status", table_name="learning_tasks")
    op.drop_table("learning_tasks")
    op.drop_index("ix_learning_paths_user_course_status", table_name="learning_paths")
    op.drop_table("learning_paths")
    op.drop_index("ix_profile_events_user_profile", table_name="profile_events")
    op.drop_table("profile_events")
    op.drop_index(op.f("ix_student_profiles_user_id"), table_name="student_profiles")
    op.drop_table("student_profiles")

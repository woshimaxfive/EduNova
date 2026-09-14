from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector

from backend.app.db.base import Base
from backend.app.models.mixins import CreatedAtMixin, IdMixin, TimestampMixin


class StudentProfile(IdMixin, TimestampMixin, Base):
    __tablename__ = "student_profiles"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_student_profiles_user_id"),
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    profile_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    confidence_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=0,
    )
    updated_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    dimension_confidence_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class ProfileEvent(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "profile_events"
    __table_args__ = (
        Index("ix_profile_events_user_profile", "user_id", "profile_id"),
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    course_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    profile_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("student_profiles.id", ondelete="SET NULL"),
        nullable=True,
    )
    dimension: Mapped[str] = mapped_column(String(80), nullable=False)
    change_summary: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    agent_trace_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False, default="legacy")
    source_ref_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_ref_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="applied")
    confidence_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    proposal_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class LearningPath(IdMixin, TimestampMixin, Base):
    __tablename__ = "learning_paths"
    __table_args__ = (
        Index("ix_learning_paths_user_course_status", "user_id", "course_id", "status"),
        Index("ix_learning_paths_agent_trace_id", "agent_trace_id"),
        CheckConstraint("approval_status IN ('legacy', 'draft', 'approved')", name="ck_learning_paths_approval_status"),
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    course_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    goal: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="active")
    agent_trace_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    plan_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    approval_status: Mapped[str] = mapped_column(String(20), nullable=False, default="legacy", server_default="legacy")
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class LearningTask(IdMixin, TimestampMixin, Base):
    __tablename__ = "learning_tasks"
    __table_args__ = (
        Index("ix_learning_tasks_path_status", "path_id", "status"),
        Index("ix_learning_tasks_user_course_status", "user_id", "course_id", "status"),
    )

    path_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("learning_paths.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    course_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=True,
    )
    knowledge_point_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("knowledge_points.id", ondelete="SET NULL"),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    task_type: Mapped[str] = mapped_column(String(80), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommended_resource_ids: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )
    learning_bundle_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_review_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class GeneratedResource(IdMixin, TimestampMixin, Base):
    __tablename__ = "generated_resources"
    __table_args__ = (
        Index("ix_generated_resources_user_course", "user_id", "course_id"),
        Index("ix_generated_resources_status", "status"),
        Index("ix_generated_resources_agent_trace_id", "agent_trace_id"),
        Index("ix_generated_resources_user_version_family", "user_id", "version_family_id", "version_number"),
        Index("ix_generated_resources_revision_of", "revision_of_resource_id"),
        UniqueConstraint("version_family_id", "version_number", name="uq_generated_resources_version_family_number"),
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    course_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=True,
    )
    knowledge_point_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("knowledge_points.id", ondelete="SET NULL"),
        nullable=True,
    )
    resource_type: Mapped[str] = mapped_column(String(80), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    agent_trace_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    content_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    citation_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="draft")
    review_status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    confidence_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    version_family_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    revision_of_resource_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("generated_resources.id", ondelete="SET NULL"),
        nullable=True,
    )
    version_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    generation_action: Mapped[str] = mapped_column(String(20), nullable=False, default="new")


class ResourceInteraction(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "resource_interactions"
    __table_args__ = (
        UniqueConstraint("user_id", "event_id", name="uq_resource_interactions_user_event"),
        Index("ix_resource_interactions_user_resource", "user_id", "resource_id", "created_at"),
        Index("ix_resource_interactions_course_type", "course_id", "event_type"),
    )

    event_id: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    course_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("courses.id", ondelete="CASCADE"), nullable=True)
    resource_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("generated_resources.id", ondelete="CASCADE"), nullable=False
    )
    path_task_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("learning_tasks.id", ondelete="SET NULL"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    progress_percent: Mapped[int | None] = mapped_column(Integer, nullable=True)
    feedback: Mapped[str | None] = mapped_column(String(30), nullable=True)


class ResourceQualityScore(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "resource_quality_scores"
    __table_args__ = (
        Index("ix_resource_quality_scores_resource", "resource_id"),
    )

    resource_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("generated_resources.id", ondelete="CASCADE"),
        nullable=False,
    )
    score_name: Mapped[str] = mapped_column(String(80), nullable=False)
    score_value: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)


class AgentRunLog(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "agent_run_logs"
    __table_args__ = (
        Index("ix_agent_run_logs_trace_id", "trace_id"),
        Index("ix_agent_run_logs_user_course", "user_id", "course_id"),
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    course_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("courses.id", ondelete="SET NULL"),
        nullable=True,
    )
    trace_id: Mapped[str] = mapped_column(String(120), nullable=False)
    agent_name: Mapped[str] = mapped_column(String(120), nullable=False)
    step_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="queued")
    input_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class AiJob(IdMixin, TimestampMixin, Base):
    __tablename__ = "ai_jobs"
    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key", name="uq_ai_jobs_user_idempotency"),
        Index("ix_ai_jobs_user_status_updated", "user_id", "status", "updated_at"),
        Index("ix_ai_jobs_workflow_status", "workflow", "status"),
        Index("ix_ai_jobs_agent_trace_id", "agent_trace_id"),
        Index("ix_ai_jobs_retry_of", "retry_of_job_id"),
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    course_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("courses.id", ondelete="SET NULL"),
        nullable=True,
    )
    retry_of_job_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("ai_jobs.id", ondelete="SET NULL"),
        nullable=True,
    )
    workflow: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="queued")
    progress_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    stage: Mapped[str] = mapped_column(String(120), nullable=False, default="queued")
    label: Mapped[str] = mapped_column(String(255), nullable=False, default="任务已排队")
    agent_trace_id: Mapped[str] = mapped_column(String(120), nullable=False)
    queue_job_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    request_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    progress_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    result_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cancel_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ModelCallRun(IdMixin, Base):
    __tablename__ = "model_call_runs"
    __table_args__ = (
        Index("ix_model_call_runs_user_created", "user_id", "started_at"),
        Index("ix_model_call_runs_trace_node", "trace_id", "node_name"),
        Index("ix_model_call_runs_status_created", "status", "started_at"),
        Index("ix_model_call_runs_ai_job", "ai_job_id"),
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    ai_job_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("ai_jobs.id", ondelete="SET NULL"),
        nullable=True,
    )
    model_config_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("model_settings.id", ondelete="SET NULL"),
        nullable=True,
    )
    trace_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    workflow: Mapped[str | None] = mapped_column(String(80), nullable=True)
    node_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    purpose: Mapped[str] = mapped_column(String(80), nullable=False, default="generation")
    operation: Mapped[str] = mapped_column(String(30), nullable=False)
    provider_source: Mapped[str] = mapped_column(String(30), nullable=False)
    model_name: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    error_category: Mapped[str | None] = mapped_column(String(60), nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PracticeSession(IdMixin, TimestampMixin, Base):
    __tablename__ = "practice_sessions"
    __table_args__ = (
        Index("ix_practice_sessions_user_course", "user_id", "course_id"),
        Index("ix_practice_sessions_agent_trace_id", "agent_trace_id"),
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    course_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="draft")
    agent_trace_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    assessment_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class PracticeAnswer(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "practice_answers"
    __table_args__ = (
        Index("ix_practice_answers_session", "session_id"),
        UniqueConstraint("session_id", "question_id", name="uq_practice_answers_session_question"),
    )

    session_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("practice_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    question_id: Mapped[str] = mapped_column(String(80), nullable=False)
    question_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    answer_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    feedback_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    is_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)


class AssessmentReport(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "assessment_reports"
    __table_args__ = (
        Index("ix_assessment_reports_user_course", "user_id", "course_id"),
        Index("ix_assessment_reports_agent_trace_id", "agent_trace_id"),
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    course_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=True,
    )
    practice_session_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("practice_sessions.id", ondelete="SET NULL"),
        nullable=True,
    )
    agent_trace_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    report_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)


class ExportJob(IdMixin, TimestampMixin, Base):
    __tablename__ = "export_jobs"
    __table_args__ = (
        Index("ix_export_jobs_user_status", "user_id", "status"),
        Index("ix_export_jobs_agent_trace_id", "agent_trace_id"),
        Index("ix_export_jobs_resource_status", "resource_id", "status"),
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    course_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=True,
    )
    resource_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("generated_resources.id", ondelete="CASCADE"),
        nullable=True,
    )
    export_type: Mapped[str] = mapped_column(String(80), nullable=False, default="learning_dossier")
    export_format: Mapped[str] = mapped_column(String(40), nullable=False, default="markdown")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="queued")
    filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(160), nullable=True)
    file_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    agent_trace_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class WeaknessReviewItem(IdMixin, TimestampMixin, Base):
    __tablename__ = "weakness_review_queue"
    __table_args__ = (
        Index(
            "ix_weakness_review_queue_user_course_status",
            "user_id",
            "course_id",
            "status",
        ),
        Index(
            "ix_weakness_review_queue_source_ref",
            "user_id",
            "course_id",
            "source_ref_type",
            "source_ref_id",
        ),
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    course_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=True,
    )
    knowledge_point_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("knowledge_points.id", ondelete="SET NULL"),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(String(80), nullable=False)
    source_ref_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_ref_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    diagnosis_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    recommended_resource_ids: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )
    next_review_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ChatSession(IdMixin, TimestampMixin, Base):
    __tablename__ = "chat_sessions"
    __table_args__ = (
        Index("ix_chat_sessions_user_scope_course", "user_id", "scope", "course_id"),
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    course_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=True,
    )
    scope: Mapped[str] = mapped_column(String(50), nullable=False, default="home")
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    mode: Mapped[str] = mapped_column(String(50), nullable=False, default="chat")
    archived_from_home: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    selected_material_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)


class ChatMessage(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "chat_messages"
    __table_args__ = (
        Index("ix_chat_messages_session_created", "session_id", "created_at"),
    )

    session_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    citation_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    trace_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    # Durable links let generated resources remain visible on the originating answer after refresh.
    resource_job_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    resource_proposal_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class ChatMessageAttachment(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "chat_message_attachments"
    __table_args__ = (
        Index("ix_chat_message_attachments_session_status", "session_id", "status"),
        Index("ix_chat_message_attachments_message", "message_id"),
        Index("ix_chat_message_attachments_pending_expiry", "status", "expires_at"),
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    message_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("chat_messages.id", ondelete="CASCADE"),
        nullable=True,
    )
    material_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("materials.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    storage_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(80), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class UserPrivacySetting(IdMixin, TimestampMixin, Base):
    __tablename__ = "user_privacy_settings"
    __table_args__ = (UniqueConstraint("user_id", name="uq_user_privacy_settings_user_id"),)

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    conversation_memory_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ConversationMemoryEntry(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "conversation_memory_entries"
    __table_args__ = (
        UniqueConstraint("assistant_message_id", name="uq_conversation_memory_assistant_message"),
        Index("ix_conversation_memory_user_profile", "user_id", "embedding_profile_hash"),
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_message_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("chat_messages.id", ondelete="CASCADE"),
        nullable=False,
    )
    assistant_message_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("chat_messages.id", ondelete="CASCADE"),
        nullable=False,
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(), nullable=False)
    embedding_provider: Mapped[str] = mapped_column(String(80), nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(120), nullable=False)
    embedding_dimension: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding_profile_hash: Mapped[str] = mapped_column(String(64), nullable=False)


class ModelSetting(IdMixin, TimestampMixin, Base):
    __tablename__ = "model_settings"
    __table_args__ = (
        Index("ix_model_settings_user_default", "user_id", "is_default"),
        Index("ix_model_settings_user_generation_default", "user_id", "is_generation_default"),
        Index("ix_model_settings_user_embedding_default", "user_id", "is_embedding_default"),
        Index("ix_model_settings_user_rerank_default", "user_id", "is_rerank_default"),
        Index(
            "uq_model_settings_user_vision_default",
            "user_id",
            unique=True,
            postgresql_where=text("is_vision_default"),
        ),
        Index("ix_model_settings_user_updated", "user_id", "updated_at"),
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    display_name: Mapped[str] = mapped_column(String(120), nullable=False, default="默认模型配置")
    preset_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    provider: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
        default="openai-compatible",
    )
    base_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    api_key_ciphertext: Mapped[str | None] = mapped_column(Text, nullable=True)
    chat_model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    vision_app_id_ciphertext: Mapped[str | None] = mapped_column(Text, nullable=True)
    vision_api_key_ciphertext: Mapped[str | None] = mapped_column(Text, nullable=True)
    vision_api_secret_ciphertext: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding_provider: Mapped[str | None] = mapped_column(String(80), nullable=True)
    embedding_preset_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    embedding_base_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding_api_key_ciphertext: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding_app_id_ciphertext: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding_api_secret_ciphertext: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    embedding_dimension: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rerank_provider: Mapped[str | None] = mapped_column(String(80), nullable=True)
    rerank_preset_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    rerank_base_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    rerank_api_key_ciphertext: Mapped[str | None] = mapped_column(Text, nullable=True)
    rerank_model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    rerank_workspace_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_generation_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_embedding_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_rerank_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_vision_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_test_ok: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    last_test_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    connection_test_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    tool_flags_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

"""create durable ai jobs

Revision ID: 20260711_0014
Revises: 20260711_0013
Create Date: 2026-07-11 11:20:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260711_0014"
down_revision = "20260711_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_jobs",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("course_id", sa.BigInteger(), nullable=True),
        sa.Column("retry_of_job_id", sa.BigInteger(), nullable=True),
        sa.Column("workflow", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="queued"),
        sa.Column("progress_percent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("stage", sa.String(length=120), nullable=False, server_default="queued"),
        sa.Column("label", sa.String(length=255), nullable=False, server_default="任务已排队"),
        sa.Column("agent_trace_id", sa.String(length=120), nullable=False),
        sa.Column("queue_job_id", sa.String(length=160), nullable=True),
        sa.Column("idempotency_key", sa.String(length=120), nullable=False),
        sa.Column("request_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("progress_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("result_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cancel_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["retry_of_job_id"], ["ai_jobs.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("user_id", "idempotency_key", name="uq_ai_jobs_user_idempotency"),
    )
    op.create_index("ix_ai_jobs_user_status_updated", "ai_jobs", ["user_id", "status", "updated_at"])
    op.create_index("ix_ai_jobs_workflow_status", "ai_jobs", ["workflow", "status"])
    op.create_index("ix_ai_jobs_agent_trace_id", "ai_jobs", ["agent_trace_id"])
    op.create_index("ix_ai_jobs_retry_of", "ai_jobs", ["retry_of_job_id"])


def downgrade() -> None:
    op.drop_index("ix_ai_jobs_retry_of", table_name="ai_jobs")
    op.drop_index("ix_ai_jobs_agent_trace_id", table_name="ai_jobs")
    op.drop_index("ix_ai_jobs_workflow_status", table_name="ai_jobs")
    op.drop_index("ix_ai_jobs_user_status_updated", table_name="ai_jobs")
    op.drop_table("ai_jobs")

"""create privacy-safe model call audit records

Revision ID: 20260711_0015
Revises: 20260711_0014
Create Date: 2026-07-11 13:20:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260711_0015"
down_revision = "20260711_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "model_call_runs",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("ai_job_id", sa.BigInteger(), nullable=True),
        sa.Column("model_config_id", sa.BigInteger(), nullable=True),
        sa.Column("trace_id", sa.String(length=120), nullable=True),
        sa.Column("workflow", sa.String(length=80), nullable=True),
        sa.Column("node_name", sa.String(length=120), nullable=True),
        sa.Column("purpose", sa.String(length=80), nullable=False, server_default="generation"),
        sa.Column("operation", sa.String(length=30), nullable=False),
        sa.Column("provider_source", sa.String(length=30), nullable=False),
        sa.Column("model_name", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("error_category", sa.String(length=60), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ai_job_id"], ["ai_jobs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["model_config_id"], ["model_settings.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_model_call_runs_user_created", "model_call_runs", ["user_id", "started_at"])
    op.create_index("ix_model_call_runs_trace_node", "model_call_runs", ["trace_id", "node_name"])
    op.create_index("ix_model_call_runs_status_created", "model_call_runs", ["status", "started_at"])
    op.create_index("ix_model_call_runs_ai_job", "model_call_runs", ["ai_job_id"])


def downgrade() -> None:
    op.drop_index("ix_model_call_runs_ai_job", table_name="model_call_runs")
    op.drop_index("ix_model_call_runs_status_created", table_name="model_call_runs")
    op.drop_index("ix_model_call_runs_trace_node", table_name="model_call_runs")
    op.drop_index("ix_model_call_runs_user_created", table_name="model_call_runs")
    op.drop_table("model_call_runs")

"""add persisted material comparison runs

Revision ID: 20260711_0013
Revises: 20260710_0012
Create Date: 2026-07-11 09:30:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260711_0013"
down_revision = "20260710_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "material_comparison_runs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("course_id", sa.BigInteger(), nullable=False),
        sa.Column("material_ids_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("result_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("agent_trace_id", sa.String(length=120), nullable=False),
        sa.Column("generation_mode", sa.String(length=50), nullable=False, server_default="deterministic_source"),
        sa.Column("review_mode", sa.String(length=50), nullable=False, server_default="rules_only"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_material_comparison_runs_user_course_created",
        "material_comparison_runs",
        ["user_id", "course_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_material_comparison_runs_agent_trace_id",
        "material_comparison_runs",
        ["agent_trace_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_material_comparison_runs_agent_trace_id", table_name="material_comparison_runs")
    op.drop_index("ix_material_comparison_runs_user_course_created", table_name="material_comparison_runs")
    op.drop_table("material_comparison_runs")

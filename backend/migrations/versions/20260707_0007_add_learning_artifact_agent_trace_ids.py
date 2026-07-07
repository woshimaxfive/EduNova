"""add learning artifact agent trace ids

Revision ID: 20260707_0007
Revises: 20260704_0006
Create Date: 2026-07-07 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260707_0007"
down_revision = "20260704_0006"
branch_labels = None
depends_on = None


TRACE_TABLE_INDEXES = (
    ("courses", "ix_courses_agent_trace_id"),
    ("materials", "ix_materials_agent_trace_id"),
    ("course_materials", "ix_course_materials_agent_trace_id"),
    ("generated_resources", "ix_generated_resources_agent_trace_id"),
    ("learning_paths", "ix_learning_paths_agent_trace_id"),
    ("practice_sessions", "ix_practice_sessions_agent_trace_id"),
    ("assessment_reports", "ix_assessment_reports_agent_trace_id"),
)


def upgrade() -> None:
    for table_name, index_name in TRACE_TABLE_INDEXES:
        op.add_column(table_name, sa.Column("agent_trace_id", sa.String(length=120), nullable=True))
        op.create_index(
            index_name,
            table_name,
            ["agent_trace_id"],
            unique=False,
        )


def downgrade() -> None:
    for table_name, index_name in reversed(TRACE_TABLE_INDEXES):
        op.drop_index(index_name, table_name=table_name)
        op.drop_column(table_name, "agent_trace_id")

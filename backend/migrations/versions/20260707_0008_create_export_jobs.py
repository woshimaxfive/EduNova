"""create export jobs

Revision ID: 20260707_0008
Revises: 20260707_0007
Create Date: 2026-07-07 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260707_0008"
down_revision = "20260707_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "export_jobs",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("course_id", sa.BigInteger(), nullable=True),
        sa.Column("export_type", sa.String(length=80), nullable=False),
        sa.Column("export_format", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=True),
        sa.Column("content_type", sa.String(length=160), nullable=True),
        sa.Column("file_path", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("agent_trace_id", sa.String(length=120), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_export_jobs_user_status", "export_jobs", ["user_id", "status"], unique=False)
    op.create_index("ix_export_jobs_agent_trace_id", "export_jobs", ["agent_trace_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_export_jobs_agent_trace_id", table_name="export_jobs")
    op.drop_index("ix_export_jobs_user_status", table_name="export_jobs")
    op.drop_table("export_jobs")

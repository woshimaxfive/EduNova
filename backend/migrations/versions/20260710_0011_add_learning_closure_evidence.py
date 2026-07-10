"""add learning closure evidence

Revision ID: 20260710_0011
Revises: 20260710_0010
Create Date: 2026-07-10 18:30:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260710_0011"
down_revision = "20260710_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    empty_json = sa.text("'{}'::jsonb")
    op.add_column(
        "practice_sessions",
        sa.Column(
            "assessment_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=empty_json,
        ),
    )
    op.add_column(
        "weakness_review_queue",
        sa.Column("source_ref_type", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "weakness_review_queue",
        sa.Column("source_ref_id", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "weakness_review_queue",
        sa.Column(
            "diagnosis_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=empty_json,
        ),
    )
    op.create_index(
        "ix_weakness_review_queue_source_ref",
        "weakness_review_queue",
        ["user_id", "course_id", "source_ref_type", "source_ref_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_weakness_review_queue_source_ref", table_name="weakness_review_queue")
    op.drop_column("weakness_review_queue", "diagnosis_json")
    op.drop_column("weakness_review_queue", "source_ref_id")
    op.drop_column("weakness_review_queue", "source_ref_type")
    op.drop_column("practice_sessions", "assessment_json")

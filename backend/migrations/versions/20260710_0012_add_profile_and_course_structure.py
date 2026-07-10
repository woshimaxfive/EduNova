"""add profile evidence and course structure

Revision ID: 20260710_0012
Revises: 20260710_0011
Create Date: 2026-07-10 21:30:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260710_0012"
down_revision = "20260710_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    empty_json = sa.text("'{}'::jsonb")
    op.add_column(
        "student_profiles",
        sa.Column(
            "dimension_confidence_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=empty_json,
        ),
    )
    op.add_column(
        "courses",
        sa.Column(
            "structure_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=empty_json,
        ),
    )
    op.add_column("profile_events", sa.Column("agent_trace_id", sa.String(length=120), nullable=True))
    op.add_column(
        "profile_events",
        sa.Column("source_type", sa.String(length=50), nullable=False, server_default="legacy"),
    )
    op.add_column("profile_events", sa.Column("source_ref_type", sa.String(length=50), nullable=True))
    op.add_column("profile_events", sa.Column("source_ref_id", sa.BigInteger(), nullable=True))
    op.add_column(
        "profile_events",
        sa.Column("status", sa.String(length=30), nullable=False, server_default="applied"),
    )
    op.add_column("profile_events", sa.Column("confidence_score", sa.Numeric(5, 2), nullable=True))
    op.add_column(
        "profile_events",
        sa.Column(
            "proposal_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=empty_json,
        ),
    )
    op.add_column("profile_events", sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True))

    op.execute(
        """
        UPDATE profile_events
        SET source_type = COALESCE(evidence_json ->> 'source_type', 'legacy'),
            agent_trace_id = evidence_json ->> 'trace_id',
            status = CASE
                WHEN COALESCE(evidence_json ->> 'source_type', '') = 'course_question' THEN 'candidate'
                ELSE 'applied'
            END,
            applied_at = CASE
                WHEN COALESCE(evidence_json ->> 'source_type', '') = 'course_question' THEN NULL
                ELSE created_at
            END
        """
    )
    op.create_index("ix_profile_events_agent_trace_id", "profile_events", ["agent_trace_id"], unique=False)
    op.create_index(
        "ix_profile_events_user_status_created",
        "profile_events",
        ["user_id", "status", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_profile_events_user_source_ref",
        "profile_events",
        ["user_id", "source_ref_type", "source_ref_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_profile_events_user_source_ref", table_name="profile_events")
    op.drop_index("ix_profile_events_user_status_created", table_name="profile_events")
    op.drop_index("ix_profile_events_agent_trace_id", table_name="profile_events")
    op.drop_column("profile_events", "applied_at")
    op.drop_column("profile_events", "proposal_json")
    op.drop_column("profile_events", "confidence_score")
    op.drop_column("profile_events", "status")
    op.drop_column("profile_events", "source_ref_id")
    op.drop_column("profile_events", "source_ref_type")
    op.drop_column("profile_events", "source_type")
    op.drop_column("profile_events", "agent_trace_id")
    op.drop_column("courses", "structure_json")
    op.drop_column("student_profiles", "dimension_confidence_json")

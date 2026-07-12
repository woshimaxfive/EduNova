"""add persisted material context to chat sessions

Revision ID: 20260712_0016
Revises: 20260711_0015
Create Date: 2026-07-12 16:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260712_0016"
down_revision = "20260711_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "chat_sessions",
        sa.Column(
            "selected_material_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("chat_sessions", "selected_material_ids")

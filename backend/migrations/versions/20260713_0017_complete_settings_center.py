"""add complete settings center state

Revision ID: 20260713_0017
Revises: 20260712_0016
Create Date: 2026-07-13 10:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260713_0017"
down_revision = "20260712_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "model_settings",
        sa.Column(
            "connection_test_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "users",
        sa.Column("auth_version", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )


def downgrade() -> None:
    op.drop_column("users", "auth_version")
    op.drop_column("model_settings", "connection_test_json")

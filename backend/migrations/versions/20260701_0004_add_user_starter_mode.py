"""add user starter mode

Revision ID: 20260701_0004
Revises: 20260701_0003
Create Date: 2026-07-03 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260701_0004"
down_revision = "20260701_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "starter_mode",
            sa.String(length=50),
            nullable=False,
            server_default="blank",
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "starter_mode")

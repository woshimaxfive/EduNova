"""split chat and embedding defaults

Revision ID: 20260713_0018
Revises: 20260713_0017
Create Date: 2026-07-13 18:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260713_0018"
down_revision = "20260713_0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "model_settings",
        sa.Column(
            "is_embedding_default",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.create_index(
        "ix_model_settings_user_embedding_default",
        "model_settings",
        ["user_id", "is_embedding_default"],
        unique=False,
    )
    op.execute(
        """
        UPDATE model_settings
        SET is_embedding_default = true
        WHERE is_default = true
          AND embedding_model IS NOT NULL
          AND btrim(embedding_model) <> ''
        """
    )


def downgrade() -> None:
    op.drop_index("ix_model_settings_user_embedding_default", table_name="model_settings")
    op.drop_column("model_settings", "is_embedding_default")

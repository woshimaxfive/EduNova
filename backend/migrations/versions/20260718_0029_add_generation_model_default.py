"""Add a dedicated default for background generation tasks.

Revision ID: 20260718_0029
Revises: 20260716_0028
"""

from alembic import op
import sqlalchemy as sa


revision = "20260718_0029"
down_revision = "20260716_0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "model_settings",
        sa.Column("is_generation_default", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index(
        "ix_model_settings_user_generation_default",
        "model_settings",
        ["user_id", "is_generation_default"],
    )
    op.alter_column("model_settings", "is_generation_default", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_model_settings_user_generation_default", table_name="model_settings")
    op.drop_column("model_settings", "is_generation_default")

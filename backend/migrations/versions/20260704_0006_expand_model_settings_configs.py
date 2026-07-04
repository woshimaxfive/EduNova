"""expand model settings configs

Revision ID: 20260704_0006
Revises: 20260703_0005
Create Date: 2026-07-04 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260704_0006"
down_revision = "20260703_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("uq_model_settings_user_id", "model_settings", type_="unique")
    op.add_column(
        "model_settings",
        sa.Column("display_name", sa.String(length=120), server_default="默认模型配置", nullable=False),
    )
    op.add_column("model_settings", sa.Column("preset_id", sa.String(length=80), nullable=True))
    op.add_column(
        "model_settings",
        sa.Column("is_default", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column("model_settings", sa.Column("last_test_ok", sa.Boolean(), nullable=True))
    op.add_column("model_settings", sa.Column("last_test_message", sa.Text(), nullable=True))
    op.add_column("model_settings", sa.Column("last_tested_at", sa.DateTime(timezone=True), nullable=True))
    op.execute(
        """
        UPDATE model_settings
        SET
            display_name = COALESCE(NULLIF(chat_model, ''), '默认模型配置'),
            is_default = true
        """
    )
    op.create_index(
        "ix_model_settings_user_default",
        "model_settings",
        ["user_id", "is_default"],
        unique=False,
    )
    op.create_index(
        "ix_model_settings_user_updated",
        "model_settings",
        ["user_id", "updated_at"],
        unique=False,
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM model_settings
        WHERE id NOT IN (
            SELECT DISTINCT ON (user_id) id
            FROM model_settings
            ORDER BY user_id, is_default DESC, updated_at DESC NULLS LAST, id DESC
        )
        """
    )
    op.drop_index("ix_model_settings_user_updated", table_name="model_settings")
    op.drop_index("ix_model_settings_user_default", table_name="model_settings")
    op.drop_column("model_settings", "last_tested_at")
    op.drop_column("model_settings", "last_test_message")
    op.drop_column("model_settings", "last_test_ok")
    op.drop_column("model_settings", "is_default")
    op.drop_column("model_settings", "preset_id")
    op.drop_column("model_settings", "display_name")
    op.create_unique_constraint("uq_model_settings_user_id", "model_settings", ["user_id"])

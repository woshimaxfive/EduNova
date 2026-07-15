"""Add visual tutor defaults and chat image attachments.

Revision ID: 20260716_0026
Revises: 20260715_0025
"""

from alembic import op
import sqlalchemy as sa


revision = "20260716_0026"
down_revision = "20260715_0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "model_settings",
        sa.Column("is_vision_default", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index(
        "uq_model_settings_user_vision_default",
        "model_settings",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("is_vision_default"),
    )
    op.create_table(
        "chat_message_attachments",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("session_id", sa.BigInteger(), nullable=False),
        sa.Column("message_id", sa.BigInteger(), nullable=True),
        sa.Column("storage_key", sa.Text(), nullable=True),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=80), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["message_id"], ["chat_messages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["chat_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_chat_message_attachments_user_id", "chat_message_attachments", ["user_id"])
    op.create_index(
        "ix_chat_message_attachments_session_status",
        "chat_message_attachments",
        ["session_id", "status"],
    )
    op.create_index("ix_chat_message_attachments_message", "chat_message_attachments", ["message_id"])
    op.create_index(
        "ix_chat_message_attachments_pending_expiry",
        "chat_message_attachments",
        ["status", "expires_at"],
    )


def downgrade() -> None:
    op.drop_table("chat_message_attachments")
    op.drop_index("uq_model_settings_user_vision_default", table_name="model_settings")
    op.drop_column("model_settings", "is_vision_default")

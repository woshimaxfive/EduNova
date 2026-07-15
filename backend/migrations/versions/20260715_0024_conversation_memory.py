"""Add privacy-controlled cross-session conversation memory.

Revision ID: 20260715_0024
Revises: 20260714_0023
"""

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


revision = "20260715_0024"
down_revision = "20260714_0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_privacy_settings",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("conversation_memory_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_user_privacy_settings_user_id"),
    )
    op.create_index("ix_user_privacy_settings_user_id", "user_privacy_settings", ["user_id"])
    op.create_table(
        "conversation_memory_entries",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("session_id", sa.BigInteger(), nullable=False),
        sa.Column("user_message_id", sa.BigInteger(), nullable=False),
        sa.Column("assistant_message_id", sa.BigInteger(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(), nullable=False),
        sa.Column("embedding_provider", sa.String(length=80), nullable=False),
        sa.Column("embedding_model", sa.String(length=120), nullable=False),
        sa.Column("embedding_dimension", sa.Integer(), nullable=False),
        sa.Column("embedding_profile_hash", sa.String(length=64), nullable=False),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["assistant_message_id"], ["chat_messages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["chat_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_message_id"], ["chat_messages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("assistant_message_id", name="uq_conversation_memory_assistant_message"),
    )
    op.create_index("ix_conversation_memory_entries_user_id", "conversation_memory_entries", ["user_id"])
    op.create_index("ix_conversation_memory_entries_session_id", "conversation_memory_entries", ["session_id"])
    op.create_index(
        "ix_conversation_memory_user_profile",
        "conversation_memory_entries",
        ["user_id", "embedding_profile_hash"],
    )


def downgrade() -> None:
    op.drop_table("conversation_memory_entries")
    op.drop_table("user_privacy_settings")

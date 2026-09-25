"""Separate pause, derived indexes and durable user-directed memory deletion."""
from alembic import op
import sqlalchemy as sa

revision = "20260925_0039"
down_revision = "20260925_0038"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("user_privacy_settings", sa.Column("memory_revision", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("user_privacy_settings", sa.Column("memory_cleared_before", sa.DateTime(timezone=True), nullable=True))
    op.add_column("conversation_memory_entries", sa.Column("topic", sa.String(120), nullable=False, server_default="历史对话"))
    op.add_column("conversation_memory_entries", sa.Column("revision", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("conversation_memory_entries", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.alter_column("conversation_memory_entries", "embedding", nullable=True)
    op.create_table(
        "learning_memory_facts",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category", sa.String(30), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_learning_memory_facts_user_id", "learning_memory_facts", ["user_id"])
    op.create_table(
        "memory_suppressions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("assistant_message_id", sa.BigInteger(), sa.ForeignKey("chat_messages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "assistant_message_id", name="uq_memory_suppression_source"),
    )
    op.create_index("ix_memory_suppressions_user_id", "memory_suppressions", ["user_id"])


def downgrade() -> None:
    # Do not discard corrections, deletion markers or confirmed facts on downgrade.
    connection = op.get_bind()
    if connection.scalar(sa.text("SELECT EXISTS (SELECT 1 FROM learning_memory_facts UNION ALL SELECT 1 FROM memory_suppressions)")):
        raise RuntimeError("Controlled memory data exists; export and explicitly resolve it before downgrade")
    if connection.scalar(sa.text("SELECT EXISTS (SELECT 1 FROM user_privacy_settings WHERE memory_revision > 0)")):
        raise RuntimeError("Memory privacy decisions exist; downgrade would remove deletion protection")
    op.drop_table("memory_suppressions")
    op.drop_table("learning_memory_facts")
    op.alter_column("conversation_memory_entries", "embedding", nullable=False)
    for name in ("updated_at", "revision", "topic"):
        op.drop_column("conversation_memory_entries", name)
    op.drop_column("user_privacy_settings", "memory_cleared_before")
    op.drop_column("user_privacy_settings", "memory_revision")

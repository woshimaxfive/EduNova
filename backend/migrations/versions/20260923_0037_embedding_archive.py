"""Retain prior vectors before an explicit profile rebuild."""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision = "20260923_0037"
down_revision = "20260914_0036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chunk_embedding_archives",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("knowledge_chunk_id", sa.BigInteger(), sa.ForeignKey("knowledge_chunks.id", ondelete="CASCADE")),
        sa.Column("material_chunk_id", sa.BigInteger(), sa.ForeignKey("material_chunks.id", ondelete="CASCADE")),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("profile_hash", sa.String(64), nullable=False),
        sa.Column("provider", sa.String(80), nullable=False),
        sa.Column("model", sa.String(120), nullable=False),
        sa.Column("dimension", sa.Integer(), nullable=False),
        sa.Column("embedding", Vector(), nullable=False),
        sa.Column("embedded_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("(knowledge_chunk_id IS NULL) <> (material_chunk_id IS NULL)", name="ck_embedding_archive_one_chunk"),
        sa.CheckConstraint("dimension > 0 AND vector_dims(embedding) = dimension", name="ck_embedding_archive_dimension"),
        sa.UniqueConstraint("knowledge_chunk_id", "content_hash", "profile_hash", name="uq_embedding_archive_knowledge"),
        sa.UniqueConstraint("material_chunk_id", "content_hash", "profile_hash", name="uq_embedding_archive_material"),
    )


def downgrade() -> None:
    if op.get_bind().scalar(sa.text("SELECT EXISTS (SELECT 1 FROM chunk_embedding_archives)")):
        raise RuntimeError("已有历史向量，禁止降级丢弃；请备份并前向修复。")
    op.drop_table("chunk_embedding_archives")

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base
from backend.app.models.mixins import CreatedAtMixin, IdMixin


class ChunkEmbeddingArchive(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "chunk_embedding_archives"
    __table_args__ = (
        CheckConstraint(
            "(knowledge_chunk_id IS NULL) <> (material_chunk_id IS NULL)",
            name="ck_embedding_archive_one_chunk",
        ),
        CheckConstraint("dimension > 0 AND vector_dims(embedding) = dimension", name="ck_embedding_archive_dimension"),
        UniqueConstraint("knowledge_chunk_id", "content_hash", "profile_hash", name="uq_embedding_archive_knowledge"),
        UniqueConstraint("material_chunk_id", "content_hash", "profile_hash", name="uq_embedding_archive_material"),
    )
    knowledge_chunk_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("knowledge_chunks.id", ondelete="CASCADE"), nullable=True,
    )
    material_chunk_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("material_chunks.id", ondelete="CASCADE"), nullable=True,
    )
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    profile_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    provider: Mapped[str] = mapped_column(String(80), nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    dimension: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(), nullable=False)
    embedded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

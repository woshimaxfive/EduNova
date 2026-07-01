from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pgvector.sqlalchemy import Vector

from backend.app.db.base import Base
from backend.app.models.mixins import CreatedAtMixin, IdMixin

if TYPE_CHECKING:
    from backend.app.models.course import Course, CourseMaterial


class KnowledgePoint(IdMixin, Base):
    __tablename__ = "knowledge_points"

    course_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    chapter: Mapped[str | None] = mapped_column(String(255), nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    difficulty: Mapped[str | None] = mapped_column(String(50), nullable=True)
    prerequisites_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    course: Mapped["Course"] = relationship(back_populates="knowledge_points")
    knowledge_chunks: Mapped[list["KnowledgeChunk"]] = relationship(
        back_populates="knowledge_point",
    )


class KnowledgeChunk(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "knowledge_chunks"
    __table_args__ = (
        Index(
            "ix_knowledge_chunks_embedding",
            "embedding",
            postgresql_using="ivfflat",
            postgresql_ops={"embedding": "vector_cosine_ops"},
            postgresql_with={"lists": 100},
        ),
    )

    course_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    material_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("course_materials.id", ondelete="CASCADE"),
        nullable=False,
    )
    knowledge_point_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("knowledge_points.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    course: Mapped["Course"] = relationship(back_populates="knowledge_chunks")
    material: Mapped["CourseMaterial"] = relationship(back_populates="knowledge_chunks")
    knowledge_point: Mapped["KnowledgePoint | None"] = relationship(
        back_populates="knowledge_chunks",
    )

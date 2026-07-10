from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector

from backend.app.db.base import Base
from backend.app.models.mixins import CreatedAtMixin, IdMixin

if TYPE_CHECKING:
    from backend.app.models.course import Course
    from backend.app.models.user import User


class Material(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "materials"
    __table_args__ = (
        Index("ix_materials_user_status_created", "user_id", "parse_status", "created_at"),
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    parse_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="uploaded",
    )
    agent_trace_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    user: Mapped["User"] = relationship(back_populates="library_materials")
    course_links: Mapped[list["CourseMaterialLink"]] = relationship(
        back_populates="material",
        cascade="all, delete-orphan",
    )
    chunks: Mapped[list["MaterialChunk"]] = relationship(
        back_populates="material",
        cascade="all, delete-orphan",
    )


class MaterialChunk(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "material_chunks"
    __table_args__ = (
        UniqueConstraint("material_id", "chunk_index", name="uq_material_chunks_material_index"),
        Index("ix_material_chunks_material", "material_id"),
        Index(
            "ix_material_chunks_embedding",
            "embedding",
            postgresql_using="ivfflat",
            postgresql_ops={"embedding": "vector_cosine_ops"},
            postgresql_with={"lists": 100},
        ),
    )

    material_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("materials.id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    section_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    material: Mapped["Material"] = relationship(back_populates="chunks")


class CourseMaterialLink(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "course_material_links"
    __table_args__ = (
        UniqueConstraint("course_id", "material_id", name="uq_course_material_links_course_material"),
        Index("ix_course_material_links_material", "material_id"),
        Index("ix_course_material_links_added_by_user", "added_by_user_id"),
    )

    course_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
    )
    material_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("materials.id", ondelete="CASCADE"),
        nullable=False,
    )
    added_by_user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    usage_type: Mapped[str] = mapped_column(String(50), nullable=False, default="reference")

    course: Mapped["Course"] = relationship(back_populates="material_links")
    material: Mapped["Material"] = relationship(back_populates="course_links")
    added_by_user: Mapped["User"] = relationship(back_populates="material_links")

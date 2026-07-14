from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
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
    ingestion_status: Mapped[str] = mapped_column(String(50), nullable=False, default="legacy")
    parser_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    outline_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    outline_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    quality_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    parsed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

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
        Index("ix_material_chunks_material_embedding_profile", "material_id", "embedding_profile_hash"),
    )

    material_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("materials.id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    section_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section_path_json: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    chunk_type: Mapped[str] = mapped_column(String(50), nullable=False, default="body")
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    quality_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(), nullable=True)
    embedding_provider: Mapped[str | None] = mapped_column(String(80), nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    embedding_dimension: Mapped[int | None] = mapped_column(Integer, nullable=True)
    embedding_profile_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    embedding_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    material: Mapped["Material"] = relationship(back_populates="chunks")


class MaterialComparisonRun(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "material_comparison_runs"
    __table_args__ = (
        Index("ix_material_comparison_runs_user_course_created", "user_id", "course_id", "created_at"),
        Index("ix_material_comparison_runs_agent_trace_id", "agent_trace_id"),
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    course_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
    )
    material_ids_json: Mapped[list[int]] = mapped_column(JSONB, nullable=False, default=list)
    result_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    agent_trace_id: Mapped[str] = mapped_column(String(120), nullable=False)
    generation_mode: Mapped[str] = mapped_column(String(50), nullable=False, default="deterministic_source")
    review_mode: Mapped[str] = mapped_column(String(50), nullable=False, default="rules_only")


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

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, Index, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base
from backend.app.models.mixins import CreatedAtMixin, IdMixin, TimestampMixin

if TYPE_CHECKING:
    from backend.app.models.knowledge import KnowledgeChunk, KnowledgePoint
    from backend.app.models.material import CourseMaterialLink
    from backend.app.models.user import User


class Course(IdMixin, TimestampMixin, Base):
    __tablename__ = "courses"

    owner_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    subject: Mapped[str | None] = mapped_column(String(120), nullable=True)
    source_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="uploaded",
    )
    visibility: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="private",
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="draft")
    agent_trace_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    structure_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    owner: Mapped["User | None"] = relationship(back_populates="owned_courses")
    enrollments: Mapped[list["CourseEnrollment"]] = relationship(
        back_populates="course",
        cascade="all, delete-orphan",
    )
    materials: Mapped[list["CourseMaterial"]] = relationship(
        back_populates="course",
        cascade="all, delete-orphan",
    )
    material_links: Mapped[list["CourseMaterialLink"]] = relationship(
        back_populates="course",
        cascade="all, delete-orphan",
    )
    knowledge_points: Mapped[list["KnowledgePoint"]] = relationship(
        back_populates="course",
        cascade="all, delete-orphan",
    )
    knowledge_chunks: Mapped[list["KnowledgeChunk"]] = relationship(
        back_populates="course",
        cascade="all, delete-orphan",
    )


class CourseEnrollment(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "course_enrollments"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "course_id",
            name="uq_course_enrollments_user_course",
        ),
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
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="learner")
    progress_percent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=0,
    )

    user: Mapped["User"] = relationship(back_populates="enrollments")
    course: Mapped["Course"] = relationship(back_populates="enrollments")


class CourseMaterial(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "course_materials"
    __table_args__ = (
        Index("ix_course_materials_user_course", "user_id", "course_id"),
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

    user: Mapped["User"] = relationship(back_populates="materials")
    course: Mapped["Course"] = relationship(back_populates="materials")
    knowledge_chunks: Mapped[list["KnowledgeChunk"]] = relationship(
        back_populates="material",
        cascade="all, delete-orphan",
    )

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base
from backend.app.models.mixins import IdMixin, TimestampMixin

if TYPE_CHECKING:
    from backend.app.models.course import Course, CourseEnrollment, CourseMaterial


class User(IdMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="student")

    owned_courses: Mapped[list["Course"]] = relationship(
        back_populates="owner",
        cascade="save-update, merge",
    )
    enrollments: Mapped[list["CourseEnrollment"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    materials: Mapped[list["CourseMaterial"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )

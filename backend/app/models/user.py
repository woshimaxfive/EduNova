from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base
from backend.app.models.mixins import IdMixin, TimestampMixin

if TYPE_CHECKING:
    from backend.app.models.course import Course, CourseEnrollment, CourseMaterial
    from backend.app.models.material import CourseMaterialLink, Material


class User(IdMixin, TimestampMixin, Base):
    __tablename__ = "users"

    account: Mapped[str] = mapped_column(String(24), nullable=False, unique=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="student")
    starter_mode: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="blank",
    )
    auth_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

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
    library_materials: Mapped[list["Material"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    material_links: Mapped[list["CourseMaterialLink"]] = relationship(
        back_populates="added_by_user",
        cascade="all, delete-orphan",
    )

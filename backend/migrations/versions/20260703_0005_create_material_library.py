"""create material library

Revision ID: 20260703_0005
Revises: 20260701_0004
Create Date: 2026-07-03 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260703_0005"
down_revision = "20260701_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "materials",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=120), nullable=False),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column("parse_status", sa.String(length=50), nullable=False),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_materials_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_materials")),
    )
    op.create_index(
        "ix_materials_user_status_created",
        "materials",
        ["user_id", "parse_status", "created_at"],
        unique=False,
    )
    op.create_table(
        "course_material_links",
        sa.Column("course_id", sa.BigInteger(), nullable=False),
        sa.Column("material_id", sa.BigInteger(), nullable=False),
        sa.Column("added_by_user_id", sa.BigInteger(), nullable=False),
        sa.Column("usage_type", sa.String(length=50), nullable=False),
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["added_by_user_id"],
            ["users.id"],
            name=op.f("fk_course_material_links_added_by_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["course_id"],
            ["courses.id"],
            name=op.f("fk_course_material_links_course_id_courses"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["material_id"],
            ["materials.id"],
            name=op.f("fk_course_material_links_material_id_materials"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_course_material_links")),
        sa.UniqueConstraint("course_id", "material_id", name="uq_course_material_links_course_material"),
    )
    op.create_index("ix_course_material_links_added_by_user", "course_material_links", ["added_by_user_id"], unique=False)
    op.create_index("ix_course_material_links_material", "course_material_links", ["material_id"], unique=False)

    op.execute(
        """
        INSERT INTO materials (
            id,
            user_id,
            filename,
            content_type,
            storage_path,
            parse_status,
            extracted_text,
            metadata_json,
            created_at
        )
        SELECT
            id,
            user_id,
            filename,
            content_type,
            storage_path,
            parse_status,
            extracted_text,
            metadata_json,
            created_at
        FROM course_materials
        """
    )
    op.execute(
        """
        INSERT INTO course_material_links (
            course_id,
            material_id,
            added_by_user_id,
            usage_type,
            created_at
        )
        SELECT
            course_id,
            id,
            user_id,
            'course_source',
            created_at
        FROM course_materials
        ON CONFLICT (course_id, material_id) DO NOTHING
        """
    )
    op.execute(
        """
        SELECT setval(
            pg_get_serial_sequence('materials', 'id'),
            GREATEST((SELECT COALESCE(MAX(id), 1) FROM materials), 1),
            true
        )
        WHERE pg_get_serial_sequence('materials', 'id') IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_index("ix_course_material_links_material", table_name="course_material_links")
    op.drop_index("ix_course_material_links_added_by_user", table_name="course_material_links")
    op.drop_table("course_material_links")
    op.drop_index("ix_materials_user_status_created", table_name="materials")
    op.drop_table("materials")

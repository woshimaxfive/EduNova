"""add resource export jobs

Revision ID: 20260710_0010
Revises: 20260710_0009
Create Date: 2026-07-10 13:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260710_0010"
down_revision = "20260710_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("export_jobs", sa.Column("resource_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        "fk_export_jobs_resource_id_generated_resources",
        "export_jobs",
        "generated_resources",
        ["resource_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_export_jobs_resource_status",
        "export_jobs",
        ["resource_id", "status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_export_jobs_resource_status", table_name="export_jobs")
    op.drop_constraint(
        "fk_export_jobs_resource_id_generated_resources",
        "export_jobs",
        type_="foreignkey",
    )
    op.drop_column("export_jobs", "resource_id")

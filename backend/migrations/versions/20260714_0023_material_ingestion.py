"""Add versioned material ingestion metadata and section-aware chunks.

Revision ID: 20260714_0023
Revises: 20260714_0022
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260714_0023"
down_revision = "20260714_0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("materials", sa.Column("ingestion_status", sa.String(length=50), nullable=False, server_default="legacy"))
    op.add_column("materials", sa.Column("parser_version", sa.String(length=50), nullable=True))
    op.add_column("materials", sa.Column("content_hash", sa.String(length=64), nullable=True))
    op.add_column("materials", sa.Column("outline_version", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("materials", sa.Column("outline_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")))
    op.add_column("materials", sa.Column("quality_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")))
    op.add_column("materials", sa.Column("parsed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_materials_user_ingestion_status", "materials", ["user_id", "ingestion_status"])
    op.create_index("ix_materials_content_hash", "materials", ["content_hash"])

    op.add_column("material_chunks", sa.Column("end_page_number", sa.Integer(), nullable=True))
    op.add_column("material_chunks", sa.Column("section_path_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")))
    op.add_column("material_chunks", sa.Column("chunk_type", sa.String(length=50), nullable=False, server_default="body"))
    op.add_column("material_chunks", sa.Column("content_hash", sa.String(length=64), nullable=True))
    op.add_column("material_chunks", sa.Column("quality_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")))
    op.create_index("ix_material_chunks_material_content_hash", "material_chunks", ["material_id", "content_hash"])


def downgrade() -> None:
    op.drop_index("ix_material_chunks_material_content_hash", table_name="material_chunks")
    for column in ("quality_json", "content_hash", "chunk_type", "section_path_json", "end_page_number"):
        op.drop_column("material_chunks", column)
    op.drop_index("ix_materials_content_hash", table_name="materials")
    op.drop_index("ix_materials_user_ingestion_status", table_name="materials")
    for column in ("parsed_at", "quality_json", "outline_json", "outline_version", "content_hash", "parser_version", "ingestion_status"):
        op.drop_column("materials", column)

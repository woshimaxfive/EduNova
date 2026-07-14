"""Add durable generated resource version lineage.

Revision ID: 20260714_0021
Revises: 20260713_0020
"""

from alembic import op
import sqlalchemy as sa


revision = "20260714_0021"
down_revision = "20260713_0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("generated_resources", sa.Column("version_family_id", sa.String(length=36), nullable=True))
    op.add_column(
        "generated_resources",
        sa.Column(
            "revision_of_resource_id",
            sa.BigInteger(),
            sa.ForeignKey("generated_resources.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column("generated_resources", sa.Column("version_number", sa.Integer(), nullable=True))
    op.add_column(
        "generated_resources",
        sa.Column("generation_action", sa.String(length=20), nullable=False, server_default="new"),
    )
    op.create_index(
        "ix_generated_resources_user_version_family",
        "generated_resources",
        ["user_id", "version_family_id", "version_number"],
    )
    op.create_index(
        "ix_generated_resources_revision_of",
        "generated_resources",
        ["revision_of_resource_id"],
    )
    op.create_unique_constraint(
        "uq_generated_resources_version_family_number",
        "generated_resources",
        ["version_family_id", "version_number"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_generated_resources_version_family_number", "generated_resources", type_="unique")
    op.drop_index("ix_generated_resources_revision_of", table_name="generated_resources")
    op.drop_index("ix_generated_resources_user_version_family", table_name="generated_resources")
    op.drop_column("generated_resources", "generation_action")
    op.drop_column("generated_resources", "version_number")
    op.drop_column("generated_resources", "revision_of_resource_id")
    op.drop_column("generated_resources", "version_family_id")

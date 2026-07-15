"""Add multimodal learning bundles and resource interaction events.

Revision ID: 20260715_0025
Revises: 20260715_0024
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260715_0025"
down_revision = "20260715_0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "learning_tasks",
        sa.Column("learning_bundle_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
    )
    op.create_table(
        "resource_interactions",
        sa.Column("event_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("course_id", sa.BigInteger(), nullable=True),
        sa.Column("resource_id", sa.BigInteger(), nullable=False),
        sa.Column("path_task_id", sa.BigInteger(), nullable=True),
        sa.Column("event_type", sa.String(length=30), nullable=False),
        sa.Column("progress_percent", sa.Integer(), nullable=True),
        sa.Column("feedback", sa.String(length=30), nullable=True),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["path_task_id"], ["learning_tasks.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["resource_id"], ["generated_resources.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "event_id", name="uq_resource_interactions_user_event"),
    )
    op.create_index(
        "ix_resource_interactions_user_resource", "resource_interactions", ["user_id", "resource_id", "created_at"]
    )
    op.create_index("ix_resource_interactions_course_type", "resource_interactions", ["course_id", "event_type"])


def downgrade() -> None:
    op.drop_table("resource_interactions")
    op.drop_column("learning_tasks", "learning_bundle_json")

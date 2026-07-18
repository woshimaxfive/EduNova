"""Persist resource-generation jobs on tutor answers.

Revision ID: 20260718_0030
Revises: 20260718_0029
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260718_0030"
down_revision = "20260718_0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("chat_messages", sa.Column("resource_job_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"))
    op.alter_column("chat_messages", "resource_job_ids", server_default=None)


def downgrade() -> None:
    op.drop_column("chat_messages", "resource_job_ids")

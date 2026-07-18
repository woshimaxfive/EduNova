"""add persisted chat resource proposals

Revision ID: 20260718_0031
Revises: 20260718_0030
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260718_0031"
down_revision = "20260718_0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "chat_messages",
        sa.Column(
            "resource_proposal_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
    )
    op.alter_column("chat_messages", "resource_proposal_json", server_default=None)


def downgrade() -> None:
    op.drop_column("chat_messages", "resource_proposal_json")

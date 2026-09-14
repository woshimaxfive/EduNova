"""Preserve exact resource activity provenance without inventing historical evidence."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260914_0036"
down_revision = "20260914_0035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("resource_interactions", sa.Column("evidence_json", postgresql.JSONB(), nullable=False, server_default="{}"))


def downgrade() -> None:
    if op.get_bind().scalar(sa.text("SELECT count(*) FROM resource_interactions WHERE evidence_json <> '{}'::jsonb")):
        raise RuntimeError("已有活动来源证据，禁止降级丢弃；请备份后前向修复。")
    op.drop_column("resource_interactions", "evidence_json")

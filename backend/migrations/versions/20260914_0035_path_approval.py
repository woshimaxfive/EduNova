"""Add explicit path approval without inventing historical confirmation.

Revision ID: 20260914_0035
Revises: 20260819_0034
"""
from alembic import op
import sqlalchemy as sa

revision = "20260914_0035"
down_revision = "20260819_0034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("learning_paths", sa.Column("approval_status", sa.String(20), nullable=False, server_default="legacy"))
    op.add_column("learning_paths", sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint("ck_learning_paths_approval_status", "learning_paths", "approval_status IN ('legacy', 'draft', 'approved')")


def downgrade() -> None:
    # Do not silently destroy user confirmation when rolling back an application.
    if op.get_bind().scalar(sa.text("SELECT count(*) FROM learning_paths WHERE approval_status <> 'legacy'")):
        raise RuntimeError("已有草稿或批准记录，请备份并制定前向修复方案；禁止丢弃批准信息。")
    op.drop_constraint("ck_learning_paths_approval_status", "learning_paths", type_="check")
    op.drop_column("learning_paths", "approved_at")
    op.drop_column("learning_paths", "approval_status")

"""Add nullable numeric usage observations to existing call audit records."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260925_0038"
down_revision = "20260923_0037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("model_call_runs", sa.Column("usage_json", postgresql.JSONB(), nullable=True))
    op.add_column("model_call_runs", sa.Column("session_id", sa.BigInteger(), nullable=True))


def downgrade() -> None:
    op.drop_column("model_call_runs", "session_id")
    op.drop_column("model_call_runs", "usage_json")

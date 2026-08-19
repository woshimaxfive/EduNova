"""stop exposing user-level embedding and rerank defaults

Revision ID: 20260819_0034
Revises: 20260819_0033
"""

from alembic import op


revision = "20260819_0034"
down_revision = "20260819_0033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Keep legacy model fields readable for a non-destructive migration, but
    # remove their routing authority. Runtime selection is system settings only.
    op.execute("UPDATE model_settings SET is_embedding_default = false, is_rerank_default = false")


def downgrade() -> None:
    # The previous default owner cannot be reconstructed safely.
    pass

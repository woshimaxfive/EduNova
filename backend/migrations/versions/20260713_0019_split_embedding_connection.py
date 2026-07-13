"""Split embedding provider credentials from the chat connection.

Revision ID: 20260713_0019
Revises: 20260713_0018
"""

from alembic import op
import sqlalchemy as sa


revision = "20260713_0019"
down_revision = "20260713_0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("model_settings", sa.Column("embedding_provider", sa.String(length=80), nullable=True))
    op.add_column("model_settings", sa.Column("embedding_preset_id", sa.String(length=80), nullable=True))
    op.add_column("model_settings", sa.Column("embedding_base_url", sa.Text(), nullable=True))
    op.add_column("model_settings", sa.Column("embedding_api_key_ciphertext", sa.Text(), nullable=True))
    op.execute(
        """
        UPDATE model_settings
        SET embedding_provider = provider,
            embedding_preset_id = preset_id,
            embedding_base_url = base_url,
            embedding_api_key_ciphertext = api_key_ciphertext
        WHERE embedding_model IS NOT NULL
          AND btrim(embedding_model) <> ''
        """
    )


def downgrade() -> None:
    op.drop_column("model_settings", "embedding_api_key_ciphertext")
    op.drop_column("model_settings", "embedding_base_url")
    op.drop_column("model_settings", "embedding_preset_id")
    op.drop_column("model_settings", "embedding_provider")

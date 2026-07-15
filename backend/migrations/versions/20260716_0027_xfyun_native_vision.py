"""add native xfyun vision credentials

Revision ID: 20260716_0027
Revises: 20260716_0026
"""

from alembic import op
import sqlalchemy as sa


revision = "20260716_0027"
down_revision = "20260716_0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("model_settings", sa.Column("vision_app_id_ciphertext", sa.Text(), nullable=True))
    op.add_column("model_settings", sa.Column("vision_api_key_ciphertext", sa.Text(), nullable=True))
    op.add_column("model_settings", sa.Column("vision_api_secret_ciphertext", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("model_settings", "vision_api_secret_ciphertext")
    op.drop_column("model_settings", "vision_api_key_ciphertext")
    op.drop_column("model_settings", "vision_app_id_ciphertext")

"""Link chat image attachments to durable material assets.

Revision ID: 20260716_0028
Revises: 20260716_0027
"""

from alembic import op
import sqlalchemy as sa


revision = "20260716_0028"
down_revision = "20260716_0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("chat_message_attachments", sa.Column("material_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        "fk_chat_message_attachments_material_id",
        "chat_message_attachments",
        "materials",
        ["material_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_chat_message_attachments_material_id",
        "chat_message_attachments",
        ["material_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_chat_message_attachments_material_id", table_name="chat_message_attachments")
    op.drop_constraint(
        "fk_chat_message_attachments_material_id",
        "chat_message_attachments",
        type_="foreignkey",
    )
    op.drop_column("chat_message_attachments", "material_id")

"""Support dynamic vector dimensions and independent rerank connections.

Revision ID: 20260713_0020
Revises: 20260713_0019
"""

from alembic import op
import sqlalchemy as sa


revision = "20260713_0020"
down_revision = "20260713_0019"
branch_labels = None
depends_on = None


def _upgrade_chunk_table(table_name: str, scope_column: str, index_name: str) -> None:
    op.drop_index(f"ix_{table_name}_embedding", table_name=table_name)
    op.execute(f"ALTER TABLE {table_name} ALTER COLUMN embedding TYPE vector USING embedding::vector")
    op.add_column(table_name, sa.Column("embedding_provider", sa.String(length=80), nullable=True))
    op.add_column(table_name, sa.Column("embedding_model", sa.String(length=120), nullable=True))
    op.add_column(table_name, sa.Column("embedding_dimension", sa.Integer(), nullable=True))
    op.add_column(table_name, sa.Column("embedding_profile_hash", sa.String(length=64), nullable=True))
    op.add_column(table_name, sa.Column("embedding_updated_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(index_name, table_name, [scope_column, "embedding_profile_hash"])


def _downgrade_chunk_table(table_name: str, index_name: str) -> None:
    op.drop_index(index_name, table_name=table_name)
    op.execute(
        f"UPDATE {table_name} SET embedding = NULL "
        "WHERE embedding IS NOT NULL AND vector_dims(embedding) <> 1536"
    )
    for column in (
        "embedding_updated_at",
        "embedding_profile_hash",
        "embedding_dimension",
        "embedding_model",
        "embedding_provider",
    ):
        op.drop_column(table_name, column)
    op.execute(
        f"ALTER TABLE {table_name} ALTER COLUMN embedding "
        "TYPE vector(1536) USING embedding::vector(1536)"
    )
    op.create_index(
        f"ix_{table_name}_embedding",
        table_name,
        ["embedding"],
        postgresql_using="ivfflat",
        postgresql_ops={"embedding": "vector_cosine_ops"},
        postgresql_with={"lists": 100},
    )


def upgrade() -> None:
    _upgrade_chunk_table(
        "knowledge_chunks",
        "course_id",
        "ix_knowledge_chunks_course_embedding_profile",
    )
    _upgrade_chunk_table(
        "material_chunks",
        "material_id",
        "ix_material_chunks_material_embedding_profile",
    )

    op.add_column("model_settings", sa.Column("embedding_app_id_ciphertext", sa.Text(), nullable=True))
    op.add_column("model_settings", sa.Column("embedding_api_secret_ciphertext", sa.Text(), nullable=True))
    op.add_column("model_settings", sa.Column("embedding_dimension", sa.Integer(), nullable=True))
    op.add_column("model_settings", sa.Column("rerank_provider", sa.String(length=80), nullable=True))
    op.add_column("model_settings", sa.Column("rerank_preset_id", sa.String(length=80), nullable=True))
    op.add_column("model_settings", sa.Column("rerank_base_url", sa.Text(), nullable=True))
    op.add_column("model_settings", sa.Column("rerank_api_key_ciphertext", sa.Text(), nullable=True))
    op.add_column("model_settings", sa.Column("rerank_model", sa.String(length=120), nullable=True))
    op.add_column("model_settings", sa.Column("rerank_workspace_id", sa.String(length=120), nullable=True))
    op.add_column(
        "model_settings",
        sa.Column("is_rerank_default", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index(
        "ix_model_settings_user_rerank_default",
        "model_settings",
        ["user_id", "is_rerank_default"],
    )


def downgrade() -> None:
    op.drop_index("ix_model_settings_user_rerank_default", table_name="model_settings")
    for column in (
        "is_rerank_default",
        "rerank_workspace_id",
        "rerank_model",
        "rerank_api_key_ciphertext",
        "rerank_base_url",
        "rerank_preset_id",
        "rerank_provider",
        "embedding_dimension",
        "embedding_api_secret_ciphertext",
        "embedding_app_id_ciphertext",
    ):
        op.drop_column("model_settings", column)
    _downgrade_chunk_table("material_chunks", "ix_material_chunks_material_embedding_profile")
    _downgrade_chunk_table("knowledge_chunks", "ix_knowledge_chunks_course_embedding_profile")

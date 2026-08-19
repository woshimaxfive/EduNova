"""add explicit practice question identity and answer uniqueness

Revision ID: 20260819_0033
Revises: 20260718_0032
"""

from alembic import op
import sqlalchemy as sa


revision = "20260819_0033"
down_revision = "20260718_0032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("practice_answers", sa.Column("question_id", sa.String(length=80), nullable=True))
    op.execute(
        """
        UPDATE practice_answers
        SET question_id = COALESCE(NULLIF(question_json ->> 'id', ''), 'legacy-' || id::text)
        WHERE question_id IS NULL
        """
    )
    op.execute(
        """
        WITH ranked AS (
            SELECT id, question_id,
                   ROW_NUMBER() OVER (PARTITION BY session_id, question_id ORDER BY id) AS row_number
            FROM practice_answers
        )
        UPDATE practice_answers AS target
        SET question_id = target.question_id || '-legacy-' || target.id::text
        FROM ranked
        WHERE target.id = ranked.id AND ranked.row_number > 1
        """
    )
    op.alter_column("practice_answers", "question_id", nullable=False)
    op.create_unique_constraint(
        "uq_practice_answers_session_question",
        "practice_answers",
        ["session_id", "question_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_practice_answers_session_question", "practice_answers", type_="unique")
    op.drop_column("practice_answers", "question_id")

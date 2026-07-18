"""add multi-course learner state

Revision ID: 20260718_0032
Revises: 20260718_0031
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260718_0032"
down_revision = "20260718_0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("course_enrollments", sa.Column("learning_status", sa.String(length=30), nullable=False, server_default="active"))
    op.add_column("course_enrollments", sa.Column("last_accessed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("course_enrollments", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("course_enrollments", sa.Column("learning_context_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"))
    op.add_column("course_enrollments", sa.Column("learning_context_confidence_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"))
    op.execute("UPDATE course_enrollments SET last_accessed_at = created_at WHERE last_accessed_at IS NULL")
    op.alter_column("course_enrollments", "learning_status", server_default=None)
    op.alter_column("course_enrollments", "learning_context_json", server_default=None)
    op.alter_column("course_enrollments", "learning_context_confidence_json", server_default=None)
    op.create_index("ix_course_enrollments_user_learning_access", "course_enrollments", ["user_id", "learning_status", "last_accessed_at"], unique=False)

    op.add_column("profile_events", sa.Column("course_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key("fk_profile_events_course_id_courses", "profile_events", "courses", ["course_id"], ["id"], ondelete="CASCADE")
    op.create_index("ix_profile_events_course_id", "profile_events", ["course_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_profile_events_course_id", table_name="profile_events")
    op.drop_constraint("fk_profile_events_course_id_courses", "profile_events", type_="foreignkey")
    op.drop_column("profile_events", "course_id")
    op.drop_index("ix_course_enrollments_user_learning_access", table_name="course_enrollments")
    op.drop_column("course_enrollments", "learning_context_confidence_json")
    op.drop_column("course_enrollments", "learning_context_json")
    op.drop_column("course_enrollments", "completed_at")
    op.drop_column("course_enrollments", "last_accessed_at")
    op.drop_column("course_enrollments", "learning_status")

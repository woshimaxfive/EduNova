from pathlib import Path

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKeyConstraint, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB

from backend.app.db.base import Base
from backend.app.models import (
    Course,
    CourseEnrollment,
    CourseMaterial,
    CourseMaterialLink,
    KnowledgeChunk,
    KnowledgePoint,
    Material,
    User,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_core_models_are_registered_for_alembic() -> None:
    assert {
        User.__tablename__,
        Course.__tablename__,
        CourseEnrollment.__tablename__,
        CourseMaterial.__tablename__,
        Material.__tablename__,
        CourseMaterialLink.__tablename__,
        KnowledgePoint.__tablename__,
        KnowledgeChunk.__tablename__,
    } <= set(Base.metadata.tables)


def test_users_table_contract() -> None:
    table = User.__table__

    assert table.c.email.unique is True
    assert table.c.email.nullable is False
    assert table.c.hashed_password.nullable is False
    assert table.c.role.default.arg == "student"
    assert table.c.starter_mode.default.arg == "blank"
    assert table.c.starter_mode.nullable is False


def test_course_enrollment_has_user_course_unique_constraint() -> None:
    table = CourseEnrollment.__table__
    unique_columns = {
        tuple(constraint.columns.keys())
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }

    assert ("user_id", "course_id") in unique_columns
    assert table.c.progress_percent.default.arg == 0


def test_course_materials_and_chunks_keep_json_and_vector_columns() -> None:
    material_table = CourseMaterial.__table__
    library_material_table = Material.__table__
    chunk_table = KnowledgeChunk.__table__

    assert isinstance(material_table.c.metadata_json.type, JSONB)
    assert isinstance(library_material_table.c.metadata_json.type, JSONB)
    assert isinstance(chunk_table.c.metadata_json.type, JSONB)
    assert isinstance(KnowledgePoint.__table__.c.prerequisites_json.type, JSONB)
    assert isinstance(chunk_table.c.embedding.type, Vector)
    assert chunk_table.c.embedding.type.dim == 1536


def test_independent_material_library_model_contract() -> None:
    material_table = Material.__table__
    link_table = CourseMaterialLink.__table__
    unique_columns = {
        tuple(constraint.columns.keys())
        for constraint in link_table.constraints
        if isinstance(constraint, UniqueConstraint)
    }

    assert material_table.c.user_id.nullable is False
    assert "course_id" not in material_table.c
    assert material_table.c.parse_status.default.arg == "uploaded"
    assert link_table.c.usage_type.default.arg == "reference"
    assert ("course_id", "material_id") in unique_columns


def test_core_tables_have_expected_foreign_keys() -> None:
    expected_foreign_keys = {
        "courses": {("owner_id",)},
        "course_enrollments": {("user_id",), ("course_id",)},
        "course_materials": {("user_id",), ("course_id",)},
        "materials": {("user_id",)},
        "course_material_links": {("course_id",), ("material_id",), ("added_by_user_id",)},
        "knowledge_points": {("course_id",)},
        "knowledge_chunks": {
            ("course_id",),
            ("material_id",),
            ("knowledge_point_id",),
        },
    }

    for table_name, constrained_columns in expected_foreign_keys.items():
        constraints = {
            tuple(constraint.column_keys)
            for constraint in Base.metadata.tables[table_name].constraints
            if isinstance(constraint, ForeignKeyConstraint)
        }
        assert constrained_columns <= constraints


def test_core_schema_migration_creates_tables_and_indexes() -> None:
    migration_path = (
        REPO_ROOT
        / "backend"
        / "migrations"
        / "versions"
        / "20260701_0002_create_core_learning_tables.py"
    )
    migration_text = migration_path.read_text(encoding="utf-8")

    assert migration_text.count("op.create_table(") >= 6
    for table_name in (
        "users",
        "courses",
        "course_enrollments",
        "course_materials",
        "knowledge_points",
        "knowledge_chunks",
    ):
        assert f'"{table_name}"' in migration_text

    assert "uq_course_enrollments_user_course" in migration_text
    assert "ix_knowledge_chunks_embedding" in migration_text


def test_material_library_migration_copies_legacy_course_materials() -> None:
    migration_path = (
        REPO_ROOT
        / "backend"
        / "migrations"
        / "versions"
        / "20260703_0005_create_material_library.py"
    )
    migration_text = migration_path.read_text(encoding="utf-8")

    assert "op.create_table(\n        \"materials\"" in migration_text
    assert "op.create_table(\n        \"course_material_links\"" in migration_text
    assert "uq_course_material_links_course_material" in migration_text
    assert "INSERT INTO materials" in migration_text
    assert "INSERT INTO course_material_links" in migration_text

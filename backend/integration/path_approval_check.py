"""Synthetic PostgreSQL migration and competing-approval regression."""
from concurrent.futures import ThreadPoolExecutor
from importlib import import_module
from threading import Barrier
from uuid import uuid4

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import delete, select, text

from backend.app.core.errors import ConflictDomainError
from backend.app.db.session import SessionLocal, engine
from backend.app.models import Course, CourseEnrollment, LearningPath, LearningTask, User
from backend.app.services.paths import PathService, SqlAlchemyPathRepository


def migration_check() -> None:
    migration = import_module("backend.migrations.versions.20260914_0035_path_approval")
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            # Temporary table shadows the real relation only in this connection.
            connection.execute(text("CREATE TEMP TABLE learning_paths (id bigint PRIMARY KEY, plan_json jsonb NOT NULL)"))
            connection.execute(text("INSERT INTO learning_paths VALUES (1, CAST(:payload AS jsonb))"),
                               {"payload": '{"schema_version":5,"revision_of":null}'})
            context = MigrationContext.configure(connection)
            with Operations.context(context):
                migration.upgrade()
                row = connection.execute(text("SELECT approval_status, approved_at, plan_json FROM learning_paths")).one()
                assert row.approval_status == "legacy" and row.approved_at is None
                assert row.plan_json == {"schema_version": 5, "revision_of": None}
                migration.downgrade()
                migration.upgrade()
                connection.execute(text("UPDATE learning_paths SET approval_status='draft'"))
                try:
                    migration.downgrade()
                except RuntimeError:
                    pass
                else:
                    raise AssertionError("Downgrade discarded confirmation state")
        finally:
            transaction.rollback()


def concurrency_check() -> None:
    user_id = course_id = None
    with SessionLocal() as db:
        try:
            user = User(account=f"approval_{uuid4().hex[:12]}", hashed_password="synthetic-only", display_name="approval test", role="student", starter_mode="blank")
            db.add(user)
            db.flush()
            user_id = user.id
            course = Course(owner_id=user_id, title="批准并发脱敏夹具", status="ready")
            db.add(course)
            db.flush()
            course_id = course.id
            db.add(CourseEnrollment(user_id=user_id, course_id=course_id, learning_status="active"))
            ids = []
            for _ in range(2):
                path = LearningPath(user_id=user_id, course_id=course_id, title="草稿", status="draft", approval_status="draft", plan_json={"schema_version": 5, "revision_of": None})
                db.add(path)
                db.flush()
                ids.append(path.id)
                db.add(LearningTask(path_id=path.id, user_id=user_id, course_id=course_id, title="阅读", task_type="learn", status="todo"))
            db.commit()
            barrier = Barrier(2, timeout=10)

            def approve(path_id):
                with SessionLocal() as worker:
                    actor = worker.get(User, user_id)
                    barrier.wait()
                    try:
                        PathService(SqlAlchemyPathRepository(worker)).approve_path(actor, path_id, None)
                        return "approved"
                    except ConflictDomainError:
                        return "conflict"

            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(approve, ids))
            assert sorted(results) == ["approved", "conflict"], results
            db.expire_all()
            paths = list(db.scalars(select(LearningPath).where(LearningPath.id.in_(ids))))
            assert sum(path.status == "active" for path in paths) == 1
            assert sum(path.approved_at is not None for path in paths) == 1
        finally:
            db.rollback()
            if course_id is not None:
                db.execute(delete(Course).where(Course.id == course_id))
            if user_id is not None:
                db.execute(delete(User).where(User.id == user_id))
            db.commit()


if __name__ == "__main__":
    migration_check()
    concurrency_check()
    print("path approval migration, downgrade guard and concurrent approval checks passed")

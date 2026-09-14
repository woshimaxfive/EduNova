"""Isolated PostgreSQL acceptance for exact task/resource/assessment provenance."""
from concurrent.futures import ThreadPoolExecutor
from importlib import import_module
from threading import Barrier
from uuid import uuid4

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import delete, select, text

from backend.app.core.errors import ConflictDomainError
from backend.app.db.session import SessionLocal, engine
from backend.app.models import Course, CourseEnrollment, CourseMaterial, GeneratedResource, KnowledgeChunk, LearningPath, LearningTask, PracticeAnswer, ResourceInteraction, User
from backend.app.schemas.resources import ResourceInteractionRequest
from backend.app.services.paths import PathService, SqlAlchemyPathRepository
from backend.app.services.practice import PracticeConflictError, PracticeService, SqlAlchemyPracticeRepository
from backend.app.services.resource_interactions import ResourceInteractionService, ResourceInteractionValidationError
from backend.app.services.task_practice import TaskPracticeService
from backend.app.services.task_resource_binding import resource_snapshot


def migration_check():
    migration = import_module("backend.migrations.versions.20260914_0036_activity_evidence")
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            connection.execute(text("CREATE TEMP TABLE resource_interactions (id bigint PRIMARY KEY)"))
            connection.execute(text("INSERT INTO resource_interactions VALUES (1)"))
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
                assert connection.scalar(text("SELECT evidence_json FROM resource_interactions")) == {}
                migration.downgrade()
                migration.upgrade()
                connection.execute(text("UPDATE resource_interactions SET evidence_json = jsonb_build_object('schema_version', 1)"))
                try:
                    migration.downgrade()
                except RuntimeError:
                    pass
                else:
                    raise AssertionError("Downgrade discarded provenance")
        finally:
            transaction.rollback()


def binding_check():
    user_id = course_id = None
    with SessionLocal() as db:
        try:
            user = User(account=f"binding_{uuid4().hex[:12]}", hashed_password="synthetic-only", display_name="binding test", role="student", starter_mode="blank")
            db.add(user)
            db.flush()
            user_id = user.id
            course = Course(owner_id=user_id, title="精确绑定合成课程", status="ready")
            db.add(course)
            db.flush()
            course_id = course.id
            db.add(CourseEnrollment(user_id=user_id, course_id=course_id, learning_status="active"))
            material = CourseMaterial(user_id=user_id, course_id=course_id, filename="synthetic.txt", content_type="text/plain", storage_path="synthetic-only", parse_status="completed")
            db.add(material)
            db.flush()
            chunk = KnowledgeChunk(course_id=course_id, material_id=material.id, content="原文：A 是正确结论。")
            db.add(chunk)
            db.flush()
            resource = GeneratedResource(user_id=user_id, course_id=course_id, title="绑定测验", resource_type="quiz", status="completed", review_status="passed",
                version_number=1, version_family_id=str(uuid4()), citation_json=[{"chunk_id": chunk.id}], content_json={"artifact": {"kind": "quiz", "questions": [
                    {"id": "original-q1", "type": "single_choice", "prompt": "根据原文选择结论", "options": [{"key": "A", "text": "正确"}, {"key": "B", "text": "错误"}],
                     "answer": "A", "explanation": "来自课程原文", "citation_refs": [chunk.id]}]}})
            db.add(resource)
            db.flush()
            path = LearningPath(user_id=user_id, course_id=course_id, title="草稿", status="draft", approval_status="draft", plan_json={"revision_of": None})
            db.add(path)
            db.flush()
            task = LearningTask(user_id=user_id, course_id=course_id, path_id=path.id, title="学习原文", task_type="learn", status="todo", recommended_resource_ids=[resource.id],
                learning_bundle_json={"binding_contract": 1, "items": [{"resource_type": "quiz", "resource_id": resource.id, "binding": resource_snapshot(resource)}]})
            db.add(task)
            db.commit()
            task_id, resource_id, path_id = task.id, resource.id, path.id
            try:
                TaskPracticeService(db).create(user, task_id, resource_id)
            except ConflictDomainError:
                pass
            else:
                raise AssertionError("Unapproved plan executed")
            PathService(SqlAlchemyPathRepository(db)).approve_path(user, path_id, None)
            barrier = Barrier(2, timeout=15)

            def create_practice(_):
                with SessionLocal() as worker:
                    actor = worker.get(User, user_id)
                    barrier.wait()
                    return TaskPracticeService(worker).create(actor, task_id, resource_id).id

            with ThreadPoolExecutor(max_workers=2) as pool:
                ids = list(pool.map(create_practice, range(2)))
            assert ids[0] == ids[1], ids
            detail = TaskPracticeService(db).create(user, task_id, resource_id)
            assert detail.questions[0].id == "original-q1" and detail.questions[0].correct_answer is None
            provenance = detail.source_binding
            assert provenance["path_id"] == path_id and provenance["resource"]["resource_id"] == resource_id
            interaction_service = ResourceInteractionService(db)
            payload = ResourceInteractionRequest(event_id=f"evt_{uuid4().hex}", event_type="completed", path_task_id=task_id)
            activity_barrier = Barrier(2, timeout=15)

            def record_activity(_):
                with SessionLocal() as worker:
                    actor = worker.get(User, user_id)
                    activity_barrier.wait()
                    return ResourceInteractionService(worker).record(actor, resource_id, payload).event_count

            with ThreadPoolExecutor(max_workers=2) as pool:
                assert list(pool.map(record_activity, range(2))) == [1, 1]
            state = interaction_service.record(user, resource_id, payload)
            assert state.completed and state.evidence[0]["mastery_claim"] is False
            assert task.status == "todo"
            assert not interaction_service.state(user, resource_id).completed
            assert interaction_service.record(user, resource_id, payload).event_count == 1
            try:
                interaction_service.record(user, resource_id, payload.model_copy(update={"path_task_id": None}))
            except ResourceInteractionValidationError:
                db.rollback()
            else:
                raise AssertionError("Event id changed task identity")
            # Replanning does not redirect an old task or its running assessment.
            path.status = "archived"
            db.add(LearningPath(user_id=user_id, course_id=course_id, title="新计划", status="active", approval_status="legacy", plan_json={}))
            db.commit()
            assert PathService(SqlAlchemyPathRepository(db)).get_task_version(user, task_id).path_id == str(path_id)
            practice = PracticeService(SqlAlchemyPracticeRepository(db))
            completed = practice.submit_answers(user, int(detail.id), [{"question_id": "original-q1", "answer_text": "A"}])
            assert completed.score == 100 and completed.source_binding == provenance
            row = db.scalar(select(PracticeAnswer).where(PracticeAnswer.session_id == int(detail.id)))
            assert row.question_json["source_binding"] == provenance and row.feedback_json["grading_status"] == "deterministic"
            try:
                practice.submit_answers(user, int(detail.id), [{"question_id": "original-q1", "answer_text": "B"}])
            except PracticeConflictError:
                pass
            else:
                raise AssertionError("Repeated submission accepted")
            assert db.scalar(select(ResourceInteraction).where(ResourceInteraction.event_id == payload.event_id)).evidence_json["path_id"] == path_id
        finally:
            db.rollback()
            if course_id is not None:
                db.execute(delete(Course).where(Course.id == course_id))
            if user_id is not None:
                db.execute(delete(User).where(User.id == user_id))
            db.commit()


if __name__ == "__main__":
    migration_check()
    binding_check()
    print("exact task binding, concurrent assessment, activity provenance and server scoring checks passed")

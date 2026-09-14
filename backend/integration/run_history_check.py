"""Run after learning_closure_check verify in the disposable E2E database."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from sqlalchemy import select, text

from backend.app.core.config import get_settings
from backend.app.core.errors import ConflictDomainError
from backend.app.db.session import SessionLocal
from backend.app.models import AiJob, LearningPath, LearningTask, PracticeAnswer, PracticeSession, ResourceInteraction, User
from backend.app.schemas.run_history import BranchRunRequest
from backend.app.services.ai_jobs import AiJobService, SqlAlchemyAiJobRepository
from backend.app.services.ai_job_contracts import AiJobNotFoundError
from backend.app.services.run_history import RunHistoryService
from backend.integration.learning_closure_check import ACCOUNT


def history(db):
    return RunHistoryService(AiJobService(SqlAlchemyAiJobRepository(db)))


def expect_conflict(action):
    try:
        action()
    except ConflictDomainError:
        return
    raise AssertionError("Unsupported or stale operation was accepted")


def evidence_ids(db, user_id):
    return {model.__name__: list(db.scalars(select(model.id).where(model.user_id == user_id).order_by(model.id)))
            for model in (PracticeSession, PracticeAnswer, ResourceInteraction)}


def verify():
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.account == ACCOUNT))
        assert user is not None
        user_id = user.id
        job = db.scalar(select(AiJob).where(AiJob.user_id == user.id, AiJob.workflow == "path_planning", AiJob.status == "completed"))
        assert job is not None
        job_id, course_id = job.id, job.course_id
        path_id = int(job.result_json["path_id"])
        original_evidence = evidence_ids(db, user_id)
        assert len(original_evidence["PracticeSession"]) == 1
        assert len(original_evidence["PracticeAnswer"]) == 3
        assert original_evidence["ResourceInteraction"]
        service = history(db)
        saved = service.capture(user, job_id)
        assert service.capture(user, job_id) == saved
        assert "request_json" not in saved.model_dump() and saved.path_content_hash
        db.rollback()
        # PostgreSQL itself rejects any SQL write, including accidental reconciliation.
        db.execute(text("SET TRANSACTION READ ONLY"))
        assert service.replay(user, job_id) == saved
        assert service.replay(user, job_id) == saved
        try:
            service.replay(User(id=-1), job_id)
        except AiJobNotFoundError:
            pass
        else:
            raise AssertionError("Snapshot leaked across users")
        db.rollback()
        expect_conflict(lambda: service.branch(user, job_id, BranchRunRequest(expected_digest=saved.digest, expected_active_path_id=None)))
        source = db.get(LearningPath, path_id)
        source.title = "模拟源版本变化"
        db.flush()
        expect_conflict(lambda: service.branch(user, job_id, BranchRunRequest(expected_digest=saved.digest, expected_active_path_id=path_id)))
        # branch rolls back this synthetic source edit on conflict.

    barrier = Barrier(2)

    def branch():
        with SessionLocal() as db:
            user = db.get(User, user_id)
            barrier.wait(timeout=15)
            result = history(db).branch(user, job_id, BranchRunRequest(expected_digest=saved.digest, expected_active_path_id=path_id))
            return result.path.id

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(branch) for _ in range(2)]
        branch_ids = [future.result(timeout=30) for future in futures]
    assert len(set(branch_ids)) == 1

    with SessionLocal() as db:
        user = db.get(User, user_id)
        service = history(db)
        branch_path = db.get(LearningPath, int(branch_ids[0]))
        assert branch_path.status == branch_path.approval_status == "draft"
        assert branch_path.approved_at is None
        assert branch_path.plan_json["revision_of"] == path_id
        tasks = list(db.scalars(select(LearningTask).where(LearningTask.path_id == branch_path.id)))
        assert tasks and all(task.status == "todo" for task in tasks)
        assert db.scalar(select(LearningPath.id).where(LearningPath.user_id == user_id, LearningPath.status == "active")) == path_id
        assert evidence_ids(db, user_id) == original_evidence
        session = db.scalar(select(PracticeSession).where(PracticeSession.user_id == user_id))
        assert session.score == 100
        expect_conflict(lambda: service.reexecute(user, job_id, "0" * 64, "stale"))
        created = service.reexecute(user, job_id, saved.digest, "new-run")
        repeated = service.reexecute(user, job_id, saved.digest, "new-run")
        assert created.job_id == repeated.job_id and int(created.job_id) != job_id
        new_job = db.get(AiJob, int(created.job_id))
        assert new_job.request_json["draft"] is True and new_job.retry_of_job_id is None
        assert new_job.progress_json["reexecuted_from"] == job_id
        assert new_job.progress_json["source_snapshot"] == saved.digest
        assert new_job.course_id == course_id
        assert service.replay(user, job_id) == saved
        assert evidence_ids(db, user_id) == original_evidence
        print("PostgreSQL read-only replay, cross-user denial, concurrent draft branch and idempotent new execution passed; no copied scores or activity")


if __name__ == "__main__":
    if get_settings().app_env != "test":
        raise SystemExit("Synthetic fixture requires APP_ENV=test")
    verify()

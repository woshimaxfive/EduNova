from __future__ import annotations

from types import SimpleNamespace

import pytest

from backend.app.services.ai_capabilities import AI_CAPABILITIES, CapabilityInputError
from backend.app.services.ai_job_contracts import AiJobCancelled
from backend.app.services.ai_job_runtime import AgentJobContext, AiJobTimeoutError
from backend.tests import test_ai_jobs as jobs
from backend.tests import test_learning_paths as paths
from backend.tests import test_resource_generation as resources


class RecordingContext:
    def __init__(self, job_id, *, timeout_seconds=None):
        self.job_id = job_id
        self.timeout_seconds = timeout_seconds
        self.stages = []
        self.stop_at = None
        self.failure = AiJobCancelled

    def check_cancelled(self):
        return None

    def before_node(self, stage, label=None):
        self.stages.append(stage)
        if stage == self.stop_at:
            raise self.failure("测试停止")

    def after_node(self, **kwargs):
        return None

    def record_model_usage(self, usage):
        return None


@pytest.fixture(params=["path_planning", "resource_generation"])
def pilot(request, monkeypatch):
    """Exercise AIJob's actual runner and compiled graph, replace only I/O seams."""
    workflow = request.param
    domain = paths.make_repo() if workflow == "path_planning" else resources.make_repo()
    model = paths.DefaultPathModelService() if workflow == "path_planning" else resources.FakeModelSettingsService()
    repo = jobs.FakeRepository(users=[jobs.make_user()], courses=domain.courses, points=domain.knowledge_points)
    repo.db = SimpleNamespace()
    service = jobs.make_service(repo)
    monkeypatch.setattr("backend.app.services.ai_job_execution.AgentTraceRecorder", lambda: paths.make_trace_recorder([]))
    if workflow == "path_planning":
        monkeypatch.setattr("backend.app.services.paths.SqlAlchemyPathRepository", lambda db: domain)
        response = service.create_path_planning_job(repo.users[0], course_id=101, idempotency_key=None)
    else:
        monkeypatch.setattr("backend.app.services.resources.SqlAlchemyResourceRepository", lambda db: domain)
        response = service.create_resource_generation_job(
            repo.users[0], course_id=101, knowledge_point_id=501,
            resource_types=["doc"], learning_goal="理解 A* 搜索", difficulty="medium",
        )
    monkeypatch.setattr("backend.app.services.model_settings.ModelSettingsService", lambda **kwargs: model)
    context = RecordingContext(int(response.job_id))
    def make_context(job_id, **kwargs):
        context.timeout_seconds = kwargs.get("timeout_seconds")
        return context
    monkeypatch.setattr("backend.app.services.ai_job_execution.AgentJobContext", make_context)
    return SimpleNamespace(
        workflow=workflow, repo=repo, domain=domain, model=model, service=service,
        job=repo.jobs[0], context=context,
    )


def test_pilot_executes_real_graph_and_keeps_wire_contract(pilot):
    response = pilot.service.run_job(pilot.job.id)
    assert response.status == "completed", response.error_message
    assert pilot.model.calls
    assert "persist" in pilot.context.stages
    assert pilot.context.timeout_seconds == pilot.service.settings.ai_job_timeout_seconds
    assert response.result["course_id"] == (101 if pilot.workflow == "path_planning" else "101")
    assert pilot.domain.paths if pilot.workflow == "path_planning" else pilot.domain.resources
    calls = len(pilot.model.calls)
    assert pilot.service.run_job(pilot.job.id).status == "completed"
    assert len(pilot.model.calls) == calls


@pytest.mark.parametrize("pilot", ["path_planning"], indirect=True)
def test_path_job_runs_real_graph_as_draft(pilot):
    pilot.job.request_json = {**pilot.job.request_json, "draft": True}
    response = pilot.service.run_job(pilot.job.id)
    assert response.status == "completed", response.error_message
    path = pilot.domain.paths[0]
    assert response.result["path_id"] == str(path.id)
    assert path.status == "draft"
    assert path.approval_status == "draft"
    assert path.approved_at is None
    assert pilot.domain.get_active_path(1, 101) is None


@pytest.mark.parametrize("change", ["owner", "archive", "input", "scope"])
def test_execution_revalidates_before_model_or_domain_write(pilot, monkeypatch, change):
    if change == "owner":
        pilot.repo.courses[0].owner_id = 99
    elif change == "archive":
        monkeypatch.setattr(pilot.repo, "is_course_active", lambda *args: False)
    elif change == "input":
        pilot.job.request_json = {**pilot.job.request_json, "arbitrary_prompt": "private-input"}
    else:
        pilot.job.course_id = 202
    response = pilot.service.run_job(pilot.job.id)
    assert response.status == "failed"
    assert not pilot.model.calls
    assert "private-input" not in (response.error_message or "")


@pytest.mark.parametrize("failure,expected", [(AiJobCancelled, "cancelled"), (AiJobTimeoutError, "failed")])
def test_real_graph_stops_before_persistence(pilot, failure, expected):
    pilot.context.stop_at = "persist"
    pilot.context.failure = failure
    response = pilot.service.run_job(pilot.job.id)
    assert response.status == expected
    if failure is AiJobTimeoutError:
        assert response.error_code == "JOB_TIMEOUT"
    assert not pilot.domain.paths if pilot.workflow == "path_planning" else not pilot.domain.committed


def test_real_graph_provider_failure_keeps_honest_failed_job(pilot, monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("private-provider-body")
    monkeypatch.setattr(pilot.model, "chat_completion_for_task", fail)
    response = pilot.service.run_job(pilot.job.id)
    assert response.status == "failed"
    assert "private-provider-body" not in response.error_message
    assert not pilot.domain.paths if pilot.workflow == "path_planning" else not pilot.domain.resources


@pytest.mark.parametrize("failure,expected", [(AiJobCancelled, "cancelled"), (AiJobTimeoutError, "failed")])
def test_model_stop_is_not_swallowed_as_generation_failure(pilot, monkeypatch, failure, expected):
    def stop(*args, **kwargs):
        raise failure("测试停止")
    monkeypatch.setattr(pilot.model, "chat_completion_for_task", stop)
    response = pilot.service.run_job(pilot.job.id)
    assert response.status == expected
    if failure is AiJobTimeoutError:
        assert response.error_code == "JOB_TIMEOUT"
    assert not pilot.domain.paths if pilot.workflow == "path_planning" else not pilot.domain.resources


def test_invalid_runner_output_is_not_published_as_success(pilot, monkeypatch):
    monkeypatch.setattr(pilot.service, f"_run_{pilot.workflow}", lambda *args: {"secret": "private-output"})
    response = pilot.service.run_job(pilot.job.id)
    assert response.status == "failed"
    assert response.error_code == "CAPABILITY_OUTPUT_INVALID"
    assert not response.result
    assert "private-output" not in response.error_message


def test_retry_rechecks_archival_without_consuming_quota(pilot, monkeypatch):
    pilot.job.status = "failed"
    monkeypatch.setattr(pilot.repo, "is_course_active", lambda *args: False)
    with pytest.raises(jobs.AiJobValidationError):
        pilot.service.retry_job(pilot.repo.users[0], pilot.job.id)
    assert pilot.job.attempt_count == 0
    assert len(pilot.repo.jobs) == 1


@pytest.mark.parametrize("pilot,field", [
    ("path_planning", "assessment_session_id"),
    *[("resource_generation", field) for field in (
        "source_resource_id", "path_task_id", "knowledge_point_id", "tutor_message_id", "evidence_chunk_ids",
    )],
], indirect=["pilot"])
def test_queued_related_object_is_reauthorized(pilot, monkeypatch, field):
    payload = {**pilot.job.request_json, field: [999] if field == "evidence_chunk_ids" else 999}
    if field == "source_resource_id":
        payload["generation_action"] = "refine"
    monkeypatch.setattr(pilot.repo, "has_message_for_user", lambda *args: False, raising=False)
    monkeypatch.setattr(pilot.repo, "has_course_chunks", lambda *args: False, raising=False)
    pilot.job.request_json = payload
    response = pilot.service.run_job(pilot.job.id)
    assert response.status == "failed"
    assert response.error_code == "NOT_FOUND"
    assert not pilot.model.calls


def test_repository_queries_scope_message_and_evidence_ids():
    from sqlalchemy import Column, Integer, MetaData, Table, create_engine
    from sqlalchemy.orm import Session
    from backend.app.services.ai_job_repository import SqlAlchemyAiJobRepository

    # Only queried columns are needed; use a disposable SQL database, no app DB.
    metadata = MetaData()
    messages = Table("chat_messages", metadata, Column("id", Integer, primary_key=True), Column("user_id", Integer))
    chunks = Table("knowledge_chunks", metadata, Column("id", Integer, primary_key=True), Column("course_id", Integer))
    engine = create_engine("sqlite://")
    try:
        metadata.create_all(engine)
        with Session(engine) as db:
            db.execute(messages.insert(), [{"id": 1, "user_id": 1}, {"id": 2, "user_id": 2}])
            db.execute(chunks.insert(), [{"id": 1, "course_id": 101}, {"id": 2, "course_id": 202}])
            repo = SqlAlchemyAiJobRepository(db)
            assert repo.has_message_for_user(1, 1)
            assert not repo.has_message_for_user(1, 2)
            assert not repo.has_message_for_user(1, 999)
            assert repo.has_course_chunks(101, [1, 1])
            assert not repo.has_course_chunks(101, [1, 2])
            assert not repo.has_course_chunks(101, [999])
    finally:
        engine.dispose()


@pytest.mark.parametrize("payload", [
    {"course_id": True}, {"course_id": "101"}, {"course_id": 0},
    {"course_id": 101, "trigger": "admin"},
])
def test_path_input_is_strict(payload):
    with pytest.raises(CapabilityInputError):
        AI_CAPABILITIES["path_planning"].validate_input(payload, 101)


@pytest.mark.parametrize("method", ["before_node", "check_cancelled"])
def test_context_deadline_and_cancel_priority(method):
    job = SimpleNamespace(status="running", cancel_requested_at=None)
    class Session:
        def __enter__(self): return self
        def __exit__(self, *args): return None
        def scalar(self, statement): return job
        def commit(self): return None
    context = AgentJobContext(1, session_factory=Session, timeout_seconds=-1)
    def call():
        return getattr(context, method)(*(["persist"] if method == "before_node" else []))
    with pytest.raises(AiJobTimeoutError):
        call()
    job.status = "cancelling"
    with pytest.raises(AiJobCancelled):
        call()

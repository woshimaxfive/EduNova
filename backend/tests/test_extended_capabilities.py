from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from backend.app.services.ai_capabilities import AI_CAPABILITIES, CapabilityInputError, CapabilityOutputError
from backend.tests import test_ai_jobs as jobs
from backend.tests.test_ai_capabilities import RecordingContext


CASES = [
    ("course_builder", None, {"material_ids": [11], "course_title": "课程"}, {"course_id": "21", "knowledge_point_count": 1, "warnings": []}),
    ("material_ingestion", None, {"material_id": 11}, {"material_id": "11", "ingestion_status": "awaiting_confirmation", "outline_version": 1, "section_count": 1, "chunk_count": 2, "quality": {"passed": True}, "classification": {}, "warnings": []}),
    ("practice_generation", 21, {"course_id": 21, "knowledge_point_ids": [31], "question_count": 5, "difficulty": "adaptive"}, {"course_id": 21, "session_id": "1", "question_count": 5, "agent_trace_id": "practice", "warnings": []}),
    ("report_generation", 21, {"course_id": 21, "practice_session_id": None}, {"course_id": 21, "report_id": "1", "agent_trace_id": "report", "warnings": []}),
    ("embedding_reindex", None, {"scope": "all_user_chunks", "runtime_scope": "system"}, {"embedded_chunk_count": 0, "embedding_dimension": 3, "warnings": []}),
]


@pytest.mark.parametrize("workflow,course_id,payload,result", CASES)
def test_remaining_job_contracts_execute_and_reject_unknown_fields(monkeypatch, workflow, course_id, payload, result):
    cap = AI_CAPABILITIES[workflow]
    with pytest.raises(CapabilityInputError):
        cap.validate_input({**payload, "extra_private_prompt": "hidden"}, course_id)
    with pytest.raises(CapabilityOutputError):
        cap.validate_output({**result, "raw_provider_body": "hidden"}, course_id)
    repo = jobs.FakeRepository(users=[jobs.make_user()], materials=[jobs.make_material()], courses=[jobs.make_course()],
                               points=[SimpleNamespace(id=31, course_id=21)])
    service = jobs.make_service(repo)
    context = RecordingContext(1)
    monkeypatch.setattr("backend.app.services.ai_job_execution.AgentJobContext", lambda *args, **kwargs: context)
    runner = Mock(return_value=result)
    monkeypatch.setattr(service, f"_run_{workflow}", runner)
    queued = service._create(repo.users[0], workflow=workflow, course_id=course_id, request_json=payload, idempotency_key="extended")
    completed = service.run_job(int(queued.job_id))
    assert completed.status == "completed", completed.error_message
    runner.assert_called_once()
    assert service.run_job(int(queued.job_id)).status == "completed"
    runner.assert_called_once()


@pytest.mark.parametrize("workflow,course_id,payload,result", CASES[:-1])
def test_queued_scope_change_stops_before_runner(monkeypatch, workflow, course_id, payload, result):
    repo = jobs.FakeRepository(users=[jobs.make_user()], materials=[jobs.make_material()], courses=[jobs.make_course()], points=[SimpleNamespace(id=31, course_id=21)])
    service = jobs.make_service(repo)
    queued = service._create(repo.users[0], workflow=workflow, course_id=course_id, request_json=payload, idempotency_key="scope")
    repo.courses[0].owner_id = 2
    repo.materials[0].user_id = 2
    monkeypatch.setattr("backend.app.services.ai_job_execution.AgentJobContext", lambda *args, **kwargs: RecordingContext(1))
    monkeypatch.setattr(service, "_mark_material_ingestion_failed", lambda *args: None)
    runner = Mock(side_effect=AssertionError("unauthorized runner executed"))
    monkeypatch.setattr(service, f"_run_{workflow}", runner)
    assert service.run_job(int(queued.job_id)).status == "failed"
    runner.assert_not_called()


@pytest.mark.parametrize("workflow", ["practice_generation", "report_generation"])
@pytest.mark.parametrize("stop", [False, True])
def test_extended_real_graph_contract_and_cancel_before_persist(monkeypatch, workflow, stop):
    from backend.tests import test_practice_assessment as practice
    from backend.app.services.ai_job_contracts import AiJobCancelled
    domain = practice.make_repo()
    repo = jobs.FakeRepository(users=[jobs.make_user()], courses=domain.courses, points=domain.knowledge_points)
    repo.db = SimpleNamespace()
    service = jobs.make_service(repo)
    model = practice.DefaultPracticeGenerationModel() if workflow == "practice_generation" else practice.DefaultReportModel()
    monkeypatch.setattr("backend.app.services.model_settings.ModelSettingsService", lambda **kwargs: model)
    monkeypatch.setattr("backend.app.services.practice.SqlAlchemyPracticeRepository", lambda db: domain)
    monkeypatch.setattr("backend.app.services.reports.SqlAlchemyReportRepository", lambda db: domain)
    monkeypatch.setattr("backend.app.services.ai_job_execution.AgentTraceRecorder", lambda: practice.make_trace_recorder([]))
    context = RecordingContext(1)
    if stop:
        context.stop_at = "persist"
        context.failure = AiJobCancelled
    monkeypatch.setattr("backend.app.services.ai_job_execution.AgentJobContext", lambda *args, **kwargs: context)
    payload = {"course_id": 101}
    if workflow == "practice_generation":
        payload.update(knowledge_point_ids=[401], question_count=3, difficulty="medium")
    queued = service._create(repo.users[0], workflow=workflow, course_id=101, request_json=payload, idempotency_key="graph")
    result = service.run_job(int(queued.job_id))
    assert result.status == ("cancelled" if stop else "completed"), result.error_message
    assert "persist" in context.stages
    if stop:
        assert not domain.sessions and not domain.reports


def test_unknown_capability_is_rejected_before_queue():
    from backend.app.services.ai_job_contracts import AiJobValidationError
    repo = jobs.FakeRepository(users=[jobs.make_user()])
    with pytest.raises(AiJobValidationError):
        jobs.make_service(repo)._create(repo.users[0], workflow="unregistered", course_id=None, request_json={}, idempotency_key="unknown")
    assert not repo.jobs


@pytest.mark.parametrize("stop", [False, True])
def test_course_builder_real_graph_preserves_wire_ids_and_cancellation(monkeypatch, stop):
    from backend.tests import test_courses as courses
    from backend.app.services.courses import CourseService
    domain = courses.FakeCourseRepository(materials=[courses.make_material(11, 1, "notes.txt", "神经网络基础\n\n反向传播使用链式法则计算梯度。\n\n过拟合需要用正则化缓解。")])
    repo = jobs.FakeRepository(users=[jobs.make_user()], materials=domain.materials)
    repo.db = SimpleNamespace()
    service = jobs.make_service(repo)
    monkeypatch.setattr("backend.app.services.courses.SqlAlchemyCourseRepository", lambda db: domain)
    monkeypatch.setattr("backend.app.services.courses.CourseService", lambda repository, **kwargs: CourseService(repository=repository))
    monkeypatch.setattr("backend.app.services.model_settings.ModelSettingsService", lambda **kwargs: None)
    context = RecordingContext(1)
    context.stop_at = "persist" if stop else None
    monkeypatch.setattr("backend.app.services.ai_job_execution.AgentJobContext", lambda *args, **kwargs: context)
    queued = service.create_course_builder_job(repo.users[0], material_ids=[11], course_title="神经网络", idempotency_key="course")
    result = service.run_job(int(queued.job_id))
    assert result.status == ("cancelled" if stop else "completed"), result.error_message
    assert len(domain.courses) == (0 if stop else 1)
    if not stop:
        assert result.result["course_id"] == str(domain.courses[0].id)


@pytest.mark.parametrize("count", [0, 2])
def test_embedding_actual_runner_contract_preserves_optional_wire_fields(monkeypatch, count):
    from backend.app.services.embeddings import EmbeddingBatch, EmbeddingProfile
    chunks = [SimpleNamespace(content="合成知识片段", metadata_json={}) for _ in range(count)]
    repo = jobs.FakeRepository(users=[jobs.make_user()])
    repo.db = SimpleNamespace(scalars=Mock(side_effect=[chunks, []]), add=Mock(), commit=Mock())
    profile = EmbeddingProfile("synthetic", "vector", 3, "profile")
    adapter = SimpleNamespace(expected_profile=lambda user: profile,
        embed_documents=lambda user, texts: EmbeddingBatch([[1.0, 0.0, 0.0] for _ in texts], "synthetic", "vector", 3, "completed", "profile"))
    monkeypatch.setattr("backend.app.services.embeddings.EmbeddingService", lambda model: adapter)
    archive = SimpleNamespace(content_hash=lambda text: "synthetic-content",
                              cached=lambda *args, **kwargs: None, replace=Mock())
    monkeypatch.setattr("backend.app.services.embedding_archive.EmbeddingArchiveService", lambda db: archive)
    monkeypatch.setattr("backend.app.services.model_settings.ModelSettingsService", lambda **kwargs: None)
    monkeypatch.setattr("backend.app.services.ai_job_execution.AgentJobContext", lambda *args, **kwargs: RecordingContext(1))
    service = jobs.make_service(repo)
    queued = service._create(repo.users[0], workflow="embedding_reindex", course_id=None, request_json={"scope": "all_user_chunks", "runtime_scope": "system"}, idempotency_key="embed")
    result = service.run_job(int(queued.job_id))
    assert result.status == "completed", result.error_message
    assert result.result["embedded_chunk_count"] == count
    assert ("embedding_provider" in result.result) is bool(count)
    assert repo.db.commit.call_count == bool(count)

from copy import deepcopy
from unittest.mock import Mock

import pytest

from backend.app.core.errors import ConflictDomainError, NotFoundDomainError
from backend.app.services.run_history import RunHistoryService
from backend.app.services.runtime_catalog import runtime_catalog
from backend.app.services.ai_capabilities import AI_CAPABILITIES
from backend.app.services.ai_job_contracts import AiJobNotFoundError
from backend.tests.test_ai_jobs import FakeRepository, make_user, make_service


def history():
    from backend.app.models import AiJob
    user = make_user()
    repo = FakeRepository(users=[user])
    jobs = make_service(repo)
    job = AiJob(id=1, user_id=user.id, course_id=None, workflow="embedding_reindex", status="completed",
                agent_trace_id="snapshot-test", request_json={"scope": "all_user_chunks", "runtime_scope": "system"},
                result_json={"private": "secret-body", "material_id": {"private": "secret-body"}},
                progress_json={"steps": [], "model_task_summary": {"call_count": 2, "private": "secret-body"}})
    repo.jobs.append(job)
    return RunHistoryService(jobs), user, job


def test_terminal_capture_is_idempotent_and_replay_is_frozen_read_only():
    service, user, job = history()
    first = service.capture(user, job.id)
    assert "secret-body" not in first.model_dump_json()
    job.status = "failed"
    job.result_json = {"changed": True}
    assert service.capture(user, job.id) == first
    service.repo.commit = Mock(side_effect=AssertionError("replay wrote"))
    service.jobs._reconcile_stale = Mock(side_effect=AssertionError("replay reconciled"))
    assert service.replay(user, job.id) == first
    assert first.status == "completed" and first.telemetry == {"call_count": 2}


def test_missing_active_tampered_and_foreign_snapshots_are_rejected():
    service, user, job = history()
    with pytest.raises(NotFoundDomainError):
        service.replay(user, job.id)
    job.status = "running"
    with pytest.raises(ConflictDomainError):
        service.capture(user, job.id)
    job.status = "completed"
    saved = service.capture(user, job.id)
    with pytest.raises(AiJobNotFoundError):
        service.replay(make_user(2), job.id)
    altered = deepcopy(saved.model_dump())
    altered["status"] = "failed"
    job.progress_json = {"snapshot": altered}
    with pytest.raises(ConflictDomainError):
        service.replay(user, job.id)


def test_unsupported_reexecution_is_explicitly_blocked():
    service, user, job = history()
    snapshot = service.capture(user, job.id)
    with pytest.raises(ConflictDomainError):
        service.reexecute(user, job.id, snapshot.digest, "new-run")


def test_catalog_matches_registered_jobs_and_does_not_claim_live_verification():
    catalog = runtime_catalog()
    assert {item.name for item in catalog.workflows if item.transport == "ai_job"} == set(AI_CAPABILITIES)
    assert len(AI_CAPABILITIES) == 7
    from typing import get_args
    from backend.app.schemas.ai_jobs import AiJobWorkflow
    assert set(AI_CAPABILITIES) == set(get_args(AiJobWorkflow))
    assert all(item["verification"] == "adapter_contract_not_live_probe" for item in catalog.provider_contracts.values())
    assert catalog.provider_contracts["custom"]["verified_structured_output"] is False
    assert catalog.tool_contracts["search_web"]["mastery_write"] is False


def test_runtime_http_auth_snapshot_replay_and_unsupported_actions():
    from fastapi.testclient import TestClient
    from backend.app.main import create_app
    from backend.app.api.v1.deps import get_current_user
    from backend.app.api.v1.ai_jobs import get_ai_job_service
    service, user, job = history()
    app = create_app()
    app.dependency_overrides[get_ai_job_service] = lambda: service.jobs
    with TestClient(app) as client:
        base = f"/api/v1/ai-jobs/{job.id}"
        assert client.get("/api/v1/agents/capabilities").status_code == 401
        assert client.get(base + "/replay").status_code == 401
        app.dependency_overrides[get_current_user] = lambda: user
        assert client.get(base + "/replay").status_code == 404
        saved = client.post(base + "/snapshot")
        assert saved.status_code == 200, saved.text
        data = saved.json()["data"]
        assert client.get(base + "/replay").json()["data"] == data
        assert client.post(base + "/branch", json={"expected_digest": data["digest"]}).status_code == 422
        assert client.post(base + "/branch", json={"expected_digest": data["digest"], "expected_active_path_id": None}).status_code == 409
        assert client.post(base + "/reexecute", json={"expected_digest": data["digest"]}).status_code == 422
        assert client.post(base + "/reexecute", headers={"Idempotency-Key": "fresh"}, json={"expected_digest": data["digest"]}).status_code == 409
        assert client.get("/api/v1/agents/capabilities").status_code == 200
        app.dependency_overrides[get_current_user] = lambda: make_user(2)
        assert client.get(base + "/replay").status_code == 404

import pytest
from fastapi.testclient import TestClient

from backend.app.core.errors import ConflictDomainError, NotFoundDomainError
from backend.app.services.paths import PathValidationError
from backend.tests import test_learning_paths as fixtures


def test_draft_approval_is_explicit_idempotent_and_version_bound():
    repo = fixtures.make_repo()
    service = fixtures.make_path_service(repo)
    user = fixtures.make_user()
    legacy = service.generate_path(user, 101)
    draft = service.generate_path(user, 101, draft=True)
    assert draft.status == "draft"
    assert draft.path.approval_status == "draft"
    assert draft.path.approved_at is None
    assert service.get_current_path(user, 101).path.id == legacy.path.id
    assert service.list_drafts(user, 101)[0].id == draft.path.id
    with pytest.raises(PathValidationError):
        service.update_task_status(user, int(draft.tasks[0].id), "doing")
    approved = service.approve_path(user, int(draft.path.id), int(legacy.path.id))
    assert approved.status == "active"
    assert approved.path.approval_status == "approved"
    timestamp = approved.path.approved_at
    assert timestamp
    assert service.approve_path(user, int(draft.path.id), int(legacy.path.id)).path.approved_at == timestamp
    assert service.get_path_version(user, int(legacy.path.id)).path.approval_status == "legacy"
    assert service.get_path_version(user, int(legacy.path.id)).path.approved_at is None


def test_two_drafts_cannot_overwrite_each_others_approval():
    repo = fixtures.make_repo()
    service = fixtures.make_path_service(repo)
    user = fixtures.make_user()
    first = service.generate_path(user, 101, draft=True)
    second = service.generate_path(user, 101, draft=True)
    service.approve_path(user, int(first.path.id), None)
    with pytest.raises(ConflictDomainError):
        service.approve_path(user, int(second.path.id), None)
    assert repo.paths[1].approval_status == "draft"
    assert service.get_current_path(user, 101).path.id == first.path.id
    with pytest.raises(NotFoundDomainError):
        service.approve_path(fixtures.make_user(2), int(second.path.id), None)


def test_approved_plan_replanning_creates_draft_without_mutation():
    repo = fixtures.make_repo()
    service = fixtures.make_path_service(repo)
    user = fixtures.make_user()
    first = service.generate_path(user, 101, draft=True)
    service.approve_path(user, int(first.path.id), None)
    snapshot = dict(repo.paths[0].plan_json)
    result = service.replan_after_assessment(user, 101, 123)
    assert result.detail.status == "draft"
    assert result.detail.path.plan_json["revision_of"] == first.path.id
    assert repo.paths[0].plan_json == snapshot
    assert service.get_current_path(user, 101).path.id == first.path.id


def test_course_less_legacy_path_is_rejected_without_server_error():
    repo = fixtures.make_repo()
    service = fixtures.make_path_service(repo)
    user = fixtures.make_user()
    legacy = service.generate_path(user, 101)
    repo.paths[0].course_id = None
    with pytest.raises(NotFoundDomainError):
        service.get_path_version(user, int(legacy.path.id))
    with pytest.raises(NotFoundDomainError):
        service.approve_path(user, int(legacy.path.id), None)


def test_legacy_path_cannot_be_retroactively_approved():
    service = fixtures.make_path_service(fixtures.make_repo())
    user = fixtures.make_user()
    legacy = service.generate_path(user, 101)
    with pytest.raises(ConflictDomainError):
        service.approve_path(user, int(legacy.path.id), None)


def test_generation_detects_base_changed_during_model_call(monkeypatch):
    repo = fixtures.make_repo()
    service = fixtures.make_path_service(repo)
    user = fixtures.make_user()
    base = service.generate_path(user, 101)
    original = repo.lock_course
    def change_base(user_id, course_id):
        repo.paths[0].status = "archived"
        return original(user_id, course_id)
    monkeypatch.setattr(repo, "lock_course", change_base)
    with pytest.raises(ConflictDomainError):
        service.generate_path(user, 101, draft=True)
    assert len(repo.paths) == 1
    assert repo.paths[0].id == int(base.path.id)


def test_resource_job_rejects_unapproved_task():
    from backend.tests import test_ai_jobs as jobs
    repo = jobs.FakeRepository(users=[jobs.make_user()], courses=[jobs.make_course()],
                               paths=[jobs.make_path(status="draft")], tasks=[jobs.make_task()])
    with pytest.raises(jobs.AiJobValidationError, match="确认计划"):
        jobs.make_service(repo).create_resource_generation_job(
            repo.users[0], course_id=21, knowledge_point_id=None, path_task_id=61,
            resource_types=["doc"], learning_goal="阅读", difficulty="medium",
        )
    assert not repo.jobs


def test_approval_api_authentication_validation_and_conflict():
    from backend.app.api.v1.paths import get_path_service
    repo = fixtures.make_repo()
    service = fixtures.make_path_service(repo)
    user = fixtures.make_user()
    settings = fixtures.Settings(_env_file=None, jwt_secret="path-approval-test-secret-32-bytes-long")
    app = fixtures.create_app()
    app.dependency_overrides[fixtures.get_auth_service] = lambda: fixtures.AuthService(
        repository=fixtures.TokenAuthRepository(user), settings=settings,
    )
    app.dependency_overrides[get_path_service] = lambda: service
    headers = {"Authorization": f"Bearer {fixtures.create_access_token(str(user.id), settings=settings)}"}
    with TestClient(app) as client:
        draft = client.post("/api/v1/paths/generate", headers=headers, json={"course_id": 101, "draft": True})
        assert draft.status_code == 200
        path_id = draft.json()["data"]["path"]["id"]
        url = f"/api/v1/paths/{path_id}/approve"
        assert client.post(url, json={"expected_active_path_id": None}).status_code == 401
        assert client.post(url, headers=headers, json={}).status_code == 422
        assert client.post(url, headers=headers, json={"expected_active_path_id": 999}).status_code == 409
        assert client.get("/api/v1/paths/drafts?course_id=101", headers=headers).json()["data"][0]["id"] == path_id
        assert client.post(url, headers=headers, json={"expected_active_path_id": None}).status_code == 200
        assert client.get(f"/api/v1/paths/{path_id}", headers=headers).json()["data"]["path"]["approval_status"] == "approved"

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import pytest

from backend.app.core.config import Settings
from backend.app.models import AiJob, Course, GeneratedResource, KnowledgePoint, Material, User
from backend.app.services.ai_jobs import (
    AiJobConflictError,
    AiJobNotFoundError,
    AiJobService,
)


NOW = datetime(2026, 7, 11, 12, 0, tzinfo=UTC)


@dataclass
class FakeQueue:
    enqueued: list[int] = field(default_factory=list)
    cancelled: list[str] = field(default_factory=list)
    active: set[str] = field(default_factory=set)
    fail_enqueue: bool = False

    def enqueue(self, job_id: int) -> str:
        if self.fail_enqueue:
            raise RuntimeError("redis unavailable: secret details")
        queue_id = f"ai-job-{job_id}"
        self.enqueued.append(job_id)
        self.active.add(queue_id)
        return queue_id

    def cancel(self, queue_job_id: str) -> None:
        self.cancelled.append(queue_job_id)
        self.active.discard(queue_job_id)

    def is_active(self, queue_job_id: str) -> bool:
        return queue_job_id in self.active


@dataclass
class FakeRepository:
    users: list[User] = field(default_factory=list)
    materials: list[Material] = field(default_factory=list)
    courses: list[Course] = field(default_factory=list)
    points: list[KnowledgePoint] = field(default_factory=list)
    resources: list[GeneratedResource] = field(default_factory=list)
    jobs: list[AiJob] = field(default_factory=list)
    next_id: int = 1

    def get_user(self, user_id: int) -> User | None:
        return next((item for item in self.users if item.id == user_id), None)

    def lock_user(self, user_id: int) -> User | None:
        return self.get_user(user_id)

    def get_job(self, job_id: int, *, for_update: bool = False) -> AiJob | None:
        return next((item for item in self.jobs if item.id == job_id), None)

    def get_job_for_user(self, user_id: int, job_id: int, *, for_update: bool = False) -> AiJob | None:
        return next((item for item in self.jobs if item.id == job_id and item.user_id == user_id), None)

    def get_by_idempotency(self, user_id: int, key: str) -> AiJob | None:
        return next((item for item in self.jobs if item.user_id == user_id and item.idempotency_key == key), None)

    def count_active(self, user_id: int) -> int:
        return len([item for item in self.jobs if item.user_id == user_id and item.status in {"queued", "running", "cancelling"}])

    def list_jobs(self, user_id: int, statuses: set[str] | None, limit: int) -> list[AiJob]:
        jobs = [item for item in self.jobs if item.user_id == user_id and (not statuses or item.status in statuses)]
        return sorted(jobs, key=lambda item: item.id, reverse=True)[:limit]

    def get_course_for_user(self, user_id: int, course_id: int) -> Course | None:
        return next((item for item in self.courses if item.id == course_id and item.owner_id == user_id), None)

    def get_materials_for_user(self, user_id: int, ids: list[int]) -> list[Material]:
        return [item for item in self.materials if item.user_id == user_id and item.id in ids]

    def get_knowledge_point(self, course_id: int, point_id: int) -> KnowledgePoint | None:
        return next((item for item in self.points if item.course_id == course_id and item.id == point_id), None)

    def get_resource_for_user(self, user_id: int, resource_id: int) -> GeneratedResource | None:
        return next((item for item in self.resources if item.user_id == user_id and item.id == resource_id), None)

    def add(self, job: AiJob) -> AiJob:
        job.id = self.next_id
        self.next_id += 1
        job.created_at = NOW + timedelta(seconds=job.id)
        job.updated_at = job.created_at
        self.jobs.append(job)
        return job

    def commit(self) -> None:
        return None

    def rollback(self) -> None:
        return None

    def refresh(self, instance: object) -> None:
        return None


def make_user(user_id: int = 1) -> User:
    return User(id=user_id, account=f"u{user_id}", hashed_password="x", display_name="学生", role="student", starter_mode="blank")


def make_material(material_id: int = 11, *, user_id: int = 1, status: str = "completed") -> Material:
    return Material(
        id=material_id,
        user_id=user_id,
        filename="人工智能.md",
        storage_path="safe/path",
        content_type="text/markdown",
        parse_status=status,
        ingestion_status="confirmed" if status == "completed" else "failed",
        extracted_text="课程内容",
        outline_json={"confirmed": status == "completed", "sections": []},
        quality_json={"passed": status == "completed"},
        metadata_json={},
    )


def make_course(course_id: int = 21, *, owner_id: int = 1) -> Course:
    return Course(id=course_id, owner_id=owner_id, title="人工智能", source_type="uploaded", visibility="private", status="ready")


def make_service(repository: FakeRepository, queue: FakeQueue | None = None, *, maximum: int = 2) -> AiJobService:
    settings = Settings(ai_job_max_active_per_user=maximum, ai_job_stale_seconds=180)
    return AiJobService(repository, settings=settings, queue=queue)


def test_course_job_is_idempotent_and_request_is_safe() -> None:
    user = make_user()
    repository = FakeRepository(users=[user], materials=[make_material()])
    queue = FakeQueue()
    service = make_service(repository, queue)

    first = service.create_course_builder_job(user, material_ids=[11], course_title="  人工智能 导论  ", idempotency_key="same-click")
    second = service.create_course_builder_job(user, material_ids=[11], course_title="不同标题", idempotency_key="same-click")

    assert first.job_id == second.job_id
    assert first.request == {"material_ids": [11], "course_title": "人工智能 导论"}
    assert queue.enqueued == [1]


def test_active_job_limit_is_enforced_per_user() -> None:
    user = make_user()
    repository = FakeRepository(users=[user], materials=[make_material()])
    service = make_service(repository, FakeQueue(), maximum=1)
    service.create_course_builder_job(user, material_ids=[11], course_title="课程一", idempotency_key="one")

    with pytest.raises(AiJobConflictError, match="达到上限"):
        service.create_course_builder_job(user, material_ids=[11], course_title="课程二", idempotency_key="two")


def test_invalid_material_and_resource_ownership_are_rejected() -> None:
    user = make_user()
    repository = FakeRepository(users=[user], materials=[make_material(status="failed")], courses=[make_course(owner_id=2)])
    service = make_service(repository, FakeQueue())

    with pytest.raises(AiJobConflictError, match="精细解析"):
        service.create_course_builder_job(user, material_ids=[11], course_title="", idempotency_key="course")
    with pytest.raises(AiJobNotFoundError, match="课程"):
        service.create_resource_generation_job(user, course_id=21, knowledge_point_id=None, resource_types=["doc"], learning_goal="", difficulty="medium", idempotency_key="resource")


def test_resource_version_job_persists_action_and_source_for_retry() -> None:
    user = make_user()
    source = GeneratedResource(
        id=31,
        user_id=1,
        course_id=21,
        knowledge_point_id=41,
        resource_type="doc",
        title="A* 讲解",
        content_json={
            "intent": {"learning_goal": "理解 A* 搜索"},
            "metadata": {"difficulty": "hard"},
        },
        citation_json=[],
        status="completed",
    )
    repository = FakeRepository(
        users=[user],
        courses=[make_course()],
        points=[KnowledgePoint(id=41, course_id=21, title="A*", chapter="搜索", order_index=1)],
        resources=[source],
    )
    service = make_service(repository, FakeQueue(fail_enqueue=True))

    created = service.create_resource_generation_job(
        user,
        course_id=21,
        knowledge_point_id=41,
        resource_types=["doc"],
        learning_goal="将被来源意图覆盖",
        difficulty="easy",
        generation_action="alternative",
        source_resource_id=31,
        idempotency_key="alternative-resource",
    )

    assert created.request["generation_action"] == "alternative"
    assert created.request["source_resource_id"] == 31
    assert created.request["learning_goal"] == "理解 A* 搜索"
    assert created.request["difficulty"] == "hard"

    service.queue = FakeQueue()
    retried = service.retry_job(user, int(created.job_id))
    assert retried.request == created.request


def test_queued_job_can_be_cancelled_without_running() -> None:
    user = make_user()
    repository = FakeRepository(users=[user], materials=[make_material()])
    queue = FakeQueue()
    service = make_service(repository, queue)
    created = service.create_course_builder_job(user, material_ids=[11], course_title="课程", idempotency_key="cancel")

    cancelled = service.cancel_job(user, int(created.job_id))

    assert cancelled.status == "cancelled"
    assert cancelled.can_cancel is False
    assert queue.cancelled == ["ai-job-1"]


def test_enqueue_failure_keeps_safe_failed_job() -> None:
    user = make_user()
    repository = FakeRepository(users=[user], materials=[make_material()])
    service = make_service(repository, FakeQueue(fail_enqueue=True))

    result = service.create_course_builder_job(user, material_ids=[11], course_title="课程", idempotency_key="queue-fail")

    assert result.status == "failed"
    assert result.error_code == "QUEUE_UNAVAILABLE"
    assert "secret" not in str(result.error_message)


def test_retry_creates_linked_job_and_revalidates_scope() -> None:
    user = make_user()
    repository = FakeRepository(users=[user], materials=[make_material()])
    service = make_service(repository, FakeQueue(fail_enqueue=True))
    original = service.create_course_builder_job(user, material_ids=[11], course_title="课程", idempotency_key="first")
    service.queue = FakeQueue()

    retried = service.retry_job(user, int(original.job_id))

    assert retried.retry_of_job_id == original.job_id
    assert retried.attempt_count == 1
    repository.materials.clear()
    repository.jobs[-1].status = "failed"
    with pytest.raises(AiJobNotFoundError):
        service.retry_job(user, int(retried.job_id))


def test_same_failed_job_cannot_be_retried_more_than_three_times() -> None:
    user = make_user()
    repository = FakeRepository(users=[user], materials=[make_material()])
    service = make_service(repository, FakeQueue(fail_enqueue=True))
    original = service.create_course_builder_job(user, material_ids=[11], course_title="课程", idempotency_key="retry-limit")

    attempts = [service.retry_job(user, int(original.job_id)).attempt_count for _ in range(3)]

    assert attempts == [1, 2, 3]
    with pytest.raises(AiJobConflictError, match="最大重试次数"):
        service.retry_job(user, int(original.job_id))


def test_stale_job_is_failed_only_when_queue_no_longer_has_it() -> None:
    user = make_user()
    repository = FakeRepository(users=[user])
    stale_at = datetime.now(UTC) - timedelta(minutes=10)
    job = AiJob(id=1, user_id=1, workflow="course_builder", status="running", progress_percent=20, stage="chunk", label="切片", agent_trace_id="trace_safe", queue_job_id="ai-job-1", idempotency_key="stale", request_json={}, progress_json={}, result_json={}, attempt_count=0, heartbeat_at=stale_at, created_at=stale_at, updated_at=stale_at)
    repository.jobs.append(job)
    queue = FakeQueue()
    service = make_service(repository, queue)

    result = service.get_job(user, 1)

    assert result.status == "failed"
    assert result.error_code == "WORKER_LOST"


def test_job_response_never_exposes_queue_id() -> None:
    user = make_user()
    repository = FakeRepository(users=[user], materials=[make_material()])
    result = make_service(repository, FakeQueue()).create_course_builder_job(user, material_ids=[11], course_title="课程", idempotency_key="safe")

    serialized = result.model_dump()
    assert "queue_job_id" not in serialized
    assert "api_key" not in str(serialized).lower()

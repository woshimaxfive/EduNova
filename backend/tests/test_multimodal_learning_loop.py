from __future__ import annotations

from datetime import UTC, datetime

from backend.app.models import GeneratedResource, LearningTask, ResourceInteraction, User
from backend.app.schemas.resources import ResourceInteractionRequest
from backend.app.services.resource_interactions import ResourceInteractionService
from backend.app.services.video_resources import normalize_video


def test_video_normalization_accepts_only_supported_canonical_ids() -> None:
    youtube = normalize_video({"title": "A* 教学", "url": "https://youtu.be/abcDEF_1234", "snippet": "逐步讲解 A*"})
    bilibili = normalize_video({"title": "红黑树讲解", "url": "https://www.bilibili.com/video/BV1xx411c7mD"})

    assert youtube is not None
    assert youtube.watch_url == "https://www.youtube.com/watch?v=abcDEF_1234"
    assert youtube.embed_url == "https://www.youtube.com/embed/abcDEF_1234"
    assert bilibili is not None
    assert bilibili.embed_url == "https://player.bilibili.com/player.html?bvid=BV1xx411c7mD"


def test_video_normalization_rejects_dangerous_or_unverified_urls() -> None:
    candidates = (
        {"title": "恶意链接", "url": "javascript:alert(1)"},
        {"title": "伪装域名", "url": "https://youtube.com.example.org/watch?v=abcDEF_1234"},
        {"title": "危险凭据", "url": "https://user:pass@youtube.com/watch?v=abcDEF_1234"},
        {"title": "非法 ID", "url": "https://www.bilibili.com/video/not-a-bv"},
        {"title": "重定向", "url": "https://example.com/redirect?to=https://youtube.com/watch?v=abcDEF_1234"},
    )
    assert all(normalize_video(item) is None for item in candidates)


class FakeInteractionDb:
    def __init__(self, resource: GeneratedResource, task: LearningTask) -> None:
        self.resource = resource
        self.task = task
        self.events: list[ResourceInteraction] = []
        self.scalar_count = 0
        self.committed = False

    def scalar(self, _statement):  # type: ignore[no-untyped-def]
        self.scalar_count += 1
        cycle = (self.scalar_count - 1) % 4
        if cycle == 0:
            return self.resource
        if cycle == 1:
            return None
        if cycle == 2:
            return self.task
        return self.resource

    def scalars(self, _statement):  # type: ignore[no-untyped-def]
        return list(self.events)

    def add(self, interaction: ResourceInteraction) -> None:
        interaction.id = len(self.events) + 1
        interaction.created_at = datetime(2026, 7, 15, 12, 0, tzinfo=UTC)
        self.events.append(interaction)

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        raise AssertionError("valid interaction should not roll back")


def test_manual_resource_completion_completes_only_the_linked_path_task() -> None:
    user = User(id=1, account="student001", display_name="学生", hashed_password="hash")
    resource = GeneratedResource(id=8, user_id=1, course_id=3, resource_type="doc", title="讲解")
    task = LearningTask(
        id=9,
        path_id=2,
        user_id=1,
        course_id=3,
        title="学习 A*",
        task_type="resource",
        recommended_resource_ids=[8],
        learning_bundle_json={"items": [{"resource_type": "doc", "resource_id": 8}]},
        status="doing",
    )
    db = FakeInteractionDb(resource, task)

    state = ResourceInteractionService(db).record(  # type: ignore[arg-type]
        user,
        8,
        ResourceInteractionRequest(event_id="evt_complete_001", event_type="completed", path_task_id=9),
    )

    assert db.committed is True
    assert task.status == "completed"
    assert state.completed is True
    assert state.progress_percent == 100

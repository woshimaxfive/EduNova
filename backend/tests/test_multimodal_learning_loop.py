from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from backend.app.models import GeneratedResource, LearningTask, ResourceInteraction, User
from backend.app.schemas.resources import ResourceInteractionRequest
from backend.app.services.resource_interactions import ResourceInteractionService
from backend.app.services.resource_feedback import (
    aggregate_resource_interactions,
    deterministic_bundle_types,
    rank_resource_types,
)
from backend.app.services.video_resources import VideoCurationService, normalize_video


def test_video_normalization_accepts_only_supported_canonical_ids() -> None:
    youtube = normalize_video({"title": "A* 教学", "url": "https://youtu.be/abcDEF_1234", "snippet": "逐步讲解 A*"})
    bilibili = normalize_video({"title": "红黑树讲解", "url": "https://www.bilibili.com/video/BV1xx411c7mD"})

    assert youtube is not None
    assert youtube.watch_url == "https://www.youtube.com/watch?v=abcDEF_1234"
    assert youtube.embed_url == "https://www.youtube.com/embed/abcDEF_1234"
    assert bilibili is not None
    assert bilibili.embed_url == "https://player.bilibili.com/player.html?bvid=BV1xx411c7mD"
    assert youtube.artifact(topic="A*", fit_reason="补充讲解")["embed_status"] == "unknown"
    assert youtube.access_scope == "external_fallback"
    assert bilibili.access_scope == "mainland_preferred"


class FakeVideoSearch:
    def __init__(self, results: list[object]) -> None:
        self.results = list(results)
        self.queries: list[str] = []

    def search(self, query: str, max_results: int | None = None) -> object:
        self.queries.append(query)
        return self.results.pop(0)


def test_video_curation_stops_after_a_valid_bilibili_result() -> None:
    search = FakeVideoSearch([
        SimpleNamespace(citations=[{
            "title": "二叉树遍历",
            "url": "https://www.bilibili.com/video/BV1xx411c7mD",
        }], warning=None),
    ])

    result = VideoCurationService(search).curate(topic="二叉树遍历", profile_summary={})

    assert result.platform == "bilibili"
    assert len(search.queries) == 1
    assert "site:bilibili.com/video" in search.queries[0]


def test_video_curation_skips_popular_but_unrelated_search_result() -> None:
    search = FakeVideoSearch([
        SimpleNamespace(citations=[
            {
                "title": "Java 架构全套课程免费分享",
                "url": "https://www.bilibili.com/video/BV1nF411u7Xe",
                "snippet": "面向 Java 工程师的完整架构课程。",
            },
            {
                "title": "冒泡排序可视化：相邻比较与交换",
                "url": "https://www.bilibili.com/video/BV1xx411c7mD",
                "snippet": "逐轮演示冒泡排序。",
            },
        ], warning=None),
    ])

    result = VideoCurationService(search).curate(topic="冒泡排序", profile_summary={})

    assert result.video_id == "BV1xx411c7mD"
    assert result.title.startswith("冒泡排序")


def test_video_curation_uses_youtube_only_as_second_stage_fallback() -> None:
    search = FakeVideoSearch([
        SimpleNamespace(citations=[], warning=None),
        SimpleNamespace(citations=[{
            "title": "Binary tree traversal",
            "url": "https://youtu.be/abcDEF_1234",
            "snippet": "二叉树遍历的英文动画讲解。",
        }], warning=None),
    ])

    result = VideoCurationService(search).curate(topic="二叉树遍历", profile_summary={})

    assert result.platform == "youtube"
    assert result.access_scope == "external_fallback"
    assert len(search.queries) == 2
    assert "site:youtube.com/watch" in search.queries[1]


def test_video_normalization_rejects_dangerous_or_unverified_urls() -> None:
    candidates = (
        {"title": "恶意链接", "url": "javascript:alert(1)"},
        {"title": "伪装域名", "url": "https://youtube.com.example.org/watch?v=abcDEF_1234"},
        {"title": "危险凭据", "url": "https://user:pass@youtube.com/watch?v=abcDEF_1234"},
        {"title": "非法 ID", "url": "https://www.bilibili.com/video/not-a-bv"},
        {"title": "重定向", "url": "https://example.com/redirect?to=https://youtube.com/watch?v=abcDEF_1234"},
    )
    assert all(normalize_video(item) is None for item in candidates)


def test_feedback_aggregation_uses_unique_resources_and_latest_feedback() -> None:
    rows = [
        (1, "doc", "opened", None, datetime(2026, 7, 15, 8, 0, tzinfo=UTC), 1),
        (1, "doc", "opened", None, datetime(2026, 7, 15, 8, 1, tzinfo=UTC), 2),
        (1, "doc", "feedback", "too_hard", datetime(2026, 7, 15, 8, 2, tzinfo=UTC), 3),
        (1, "doc", "feedback", "helpful", datetime(2026, 7, 15, 8, 3, tzinfo=UTC), 4),
        (2, "doc", "completed", None, datetime(2026, 7, 15, 8, 4, tzinfo=UTC), 5),
        (2, "doc", "feedback", "not_helpful", datetime(2026, 7, 15, 8, 5, tzinfo=UTC), 6),
    ]

    summary = aggregate_resource_interactions(rows)

    assert summary == {"doc": {"opened": 1, "helpful": 1, "completed": 1, "not_helpful": 1}}


def test_feedback_reorders_but_never_removes_modalities() -> None:
    summary = {
        "quiz": {"helpful": 2, "completed": 2},
        "doc": {"not_helpful": 2},
        "mindmap": {"too_hard": 1},
    }

    assert deterministic_bundle_types(summary) == ("quiz", "mindmap", "doc")
    assert set(rank_resource_types(("doc", "mindmap", "quiz", "video"), summary)) == {
        "doc", "mindmap", "quiz", "video"
    }


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


def test_manual_resource_completion_does_not_complete_the_linked_path_task() -> None:
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
    assert task.status == "doing"
    assert state.completed is True
    assert state.progress_percent == 100

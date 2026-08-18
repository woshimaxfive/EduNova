from __future__ import annotations

from types import SimpleNamespace

from backend.app.models import ConversationMemoryEntry
from backend.app.services.conversation_memory import ConversationMemoryService, PrivacySettingsResponse
from backend.app.services.embeddings import EmbeddingBatch


class FakeQueue:
    def __init__(self) -> None:
        self.calls: list[dict[str, int]] = []

    def enqueue(self, **ids: int) -> None:
        self.calls.append(ids)

    def enqueue_backfill(self, *, user_id: int) -> None:
        pass


class EnabledMemoryService(ConversationMemoryService):
    def get_settings(self, user):
        return PrivacySettingsResponse(conversation_memory_enabled=True, indexed_memory_count=0)


class FakeDb:
    def __init__(self, existing: ConversationMemoryEntry | None = None) -> None:
        self.existing = existing
        self.commits = 0

    def scalar(self, _query):
        return self.existing

    def add(self, _value) -> None:
        raise AssertionError("the migration test should update the existing entry")

    def commit(self) -> None:
        self.commits += 1


def test_new_memory_pair_is_scheduled_with_ids_instead_of_raw_text() -> None:
    queue = FakeQueue()
    service = EnabledMemoryService(SimpleNamespace(), queue=queue)

    scheduled = service.schedule_pair(
        user=SimpleNamespace(id=7),
        session=SimpleNamespace(id=11),
        user_message=SimpleNamespace(id=13, content="私人问题"),
        assistant_message=SimpleNamespace(id=14, content="私人回答"),
    )

    assert scheduled is True
    assert queue.calls == [{
        "user_id": 7,
        "session_id": 11,
        "user_message_id": 13,
        "assistant_message_id": 14,
    }]
    assert "私人问题" not in str(queue.calls)


def test_memory_summary_redacts_common_secrets() -> None:
    summary = ConversationMemoryService._safe_summary(
        "邮箱 me@example.com，手机号 13800138000",
        "api_key=secret-value",
    )

    assert "me@example.com" not in summary
    assert "13800138000" not in summary
    assert "secret-value" not in summary


def test_stale_memory_profile_is_reembedded_and_dimension_migrated() -> None:
    existing = ConversationMemoryEntry(
        user_id=7,
        session_id=11,
        user_message_id=13,
        assistant_message_id=14,
        summary="旧摘要",
        embedding=[0.1, 0.2],
        embedding_provider="openai_compatible",
        embedding_model="old-embedding",
        embedding_dimension=2,
        embedding_profile_hash="old-profile",
    )
    db = FakeDb(existing)
    embedding = SimpleNamespace(
        embed_documents=lambda _user, _texts: EmbeddingBatch(
            vectors=[[0.5] * 2048],
            source="openai_compatible",
            model="text-embedding-v4",
            dimension=2048,
            status="completed",
            profile_hash="new-profile",
        )
    )
    service = EnabledMemoryService(db, embedding_service=embedding)

    migrated = service.index_pair(
        user=SimpleNamespace(id=7),
        session=SimpleNamespace(id=11),
        user_message=SimpleNamespace(id=13, content="新的问题"),
        assistant_message=SimpleNamespace(id=14, content="新的回答"),
    )

    assert migrated is True
    assert db.commits == 1
    assert existing.embedding_dimension == 2048
    assert len(existing.embedding) == 2048
    assert existing.embedding_model == "text-embedding-v4"
    assert existing.embedding_profile_hash == "new-profile"

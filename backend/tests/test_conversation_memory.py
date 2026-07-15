from __future__ import annotations

from types import SimpleNamespace

from backend.app.services.conversation_memory import ConversationMemoryService, PrivacySettingsResponse


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

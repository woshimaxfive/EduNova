from types import SimpleNamespace
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from backend.app.api.v1.deps import get_current_user
from backend.app.db.session import get_db_session
from backend.app.main import create_app
from backend.app.schemas.memory import MemoryPage, MemoryItem
from backend.app.services.memory_control import MemoryControlService, MemoryControlError


def test_memory_routes_require_auth_and_explicit_confirmation(monkeypatch):
    app = create_app()
    app.dependency_overrides[get_db_session] = lambda: SimpleNamespace()
    client = TestClient(app)
    root = "/api/v1/settings/privacy/memories"
    assert client.get(root).status_code == 401
    assert client.get(root + "/export").status_code == 401
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=17)
    calls = []
    def listing(self, user_id, layer, page, page_size):
        calls.append((user_id, layer, page, page_size))
        return MemoryPage(items=[], total=0, page=page, page_size=page_size)
    monkeypatch.setattr(MemoryControlService, "list_items", listing)
    assert client.get(root + "?user_id=99&layer=fact").status_code == 200
    assert calls == [(17, "fact", 1, 20)]
    for suffix in ("?layer=unknown", "?page=0", "?page_size=101"):
        assert client.get(root + suffix).status_code == 422
    for payload in ({"content": "目标", "category": "goal"}, {"content": "目标", "category": "goal", "confirmed": False}):
        assert client.post(root + "/facts", json=payload).status_code == 422
    assert client.delete(root + "/fact/1").status_code == 422
    def conflict(*_):
        raise MemoryControlError("版本冲突")
    monkeypatch.setattr(MemoryControlService, "correct", conflict)
    response = client.patch(root + "/fact/1", json={"content": "新目标", "revision": 1, "confirmed": True})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "MEMORY_CONTROL_ERROR"


def test_memory_response_serializes_source_and_times_without_private_vectors(monkeypatch):
    now = datetime.now(UTC)
    item = MemoryItem(id="3", layer="fact", category="goal", topic="goal", content="掌握队列",
                      source="用户在设置页明确确认", created_at=now, updated_at=now, revision=1)
    calls = []
    def create(self, user_id, payload):
        calls.append(user_id)
        return item
    monkeypatch.setattr(MemoryControlService, "create_fact", create)
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=17)
    app.dependency_overrides[get_db_session] = lambda: SimpleNamespace()
    response = TestClient(app).post("/api/v1/settings/privacy/memories/facts", json={
        "content": "掌握队列", "category": "goal", "confirmed": True,
    })
    assert response.status_code == 200 and calls == [17]
    assert response.json()["data"]["source"] == "用户在设置页明确确认"
    assert "embedding" not in response.text

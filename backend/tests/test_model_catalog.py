from contextlib import contextmanager
from types import SimpleNamespace
import json

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.app.api.v1.deps import get_current_user
from backend.app.api.v1.settings import get_model_settings_service
from backend.app.main import create_app
from backend.app.services.model_catalog import (
    ModelCatalogClient, ModelCatalogError, ModelCatalogRequest, personal_catalog_key,
)
from backend.app.services.model_settings_contracts import ModelSettingsValidationError


class CatalogPool:
    def __init__(self, payload=None, status=200):
        self.payload = payload
        self.status = status
        self.requests = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    @contextmanager
    def stream(self, method, url, **kwargs):
        self.requests.append((method, url, kwargs))
        yield SimpleNamespace(status=self.status, iter_stream=lambda: iter([json.dumps(self.payload).encode()]))


@pytest.mark.parametrize("base, suffix", [
    ("https://provider.example", "/v1/models"),
    ("https://provider.example/v1", "/models"),
    ("https://provider.example/compatible-mode/v1", "/models"),
])
def test_catalog_parses_deduplicates_and_preserves_custom_prefix(base, suffix):
    pool = CatalogPool({"data": [{"id": "z"}, {"id": "a"}, {"id": "a"}, {}, {"id": 1}]})
    result = ModelCatalogClient(lambda: pool).fetch(base, "synthetic-key")
    assert result.models == ["a", "z"]
    assert len(pool.requests) == 1
    assert pool.requests[0][0:2] == ("GET", base + suffix)
    assert pool.requests[0][2]["headers"]["Authorization"] == "Bearer synthetic-key"


def test_slug_catalog_and_empty_catalog():
    assert ModelCatalogClient(lambda: CatalogPool({"models": [{"slug": "chat"}]})).fetch(
        "https://provider.example/v1", "key").models == ["chat"]
    assert ModelCatalogClient(lambda: CatalogPool({"data": []})).fetch(
        "https://provider.example/v1", "key").models == []


@pytest.mark.parametrize("status", [301, 302, 401, 403, 404, 405, 429, 500])
def test_provider_errors_are_safe_and_redirects_are_not_followed(status):
    pool = CatalogPool({"error": "synthetic-secret"}, status)
    with pytest.raises(ModelCatalogError) as error:
        ModelCatalogClient(lambda: pool).fetch("https://provider.example", "synthetic-secret")
    assert "synthetic-secret" not in str(error.value)
    assert len(pool.requests) == 1


@pytest.mark.parametrize("url", ["http://provider.example", "https://user:password@provider.example", "https://provider.example?key=secret", "https://provider.example/#fragment"])
def test_catalog_rejects_unsafe_url_forms(url):
    with pytest.raises(ValidationError):
        ModelCatalogRequest(base_url=url)


def test_only_current_users_key_for_same_address_can_be_reused():
    looked_up = []
    setting = SimpleNamespace(base_url="https://original.example/v1", api_key_ciphertext="encrypted")
    def lookup(user_id):
        looked_up.append(user_id)
        return setting
    service = SimpleNamespace(repository=SimpleNamespace(get_default_for_user=lookup), _decrypt_api_key=lambda _: "personal-key")
    user = SimpleNamespace(id=17)
    assert personal_catalog_key(service, user, ModelCatalogRequest(base_url=setting.base_url)) == "personal-key"
    assert looked_up == [17]
    with pytest.raises(ModelSettingsValidationError):
        personal_catalog_key(service, user, ModelCatalogRequest(base_url="https://other.example/v1"))
    assert personal_catalog_key(service, user, ModelCatalogRequest(base_url="https://other.example", api_key="new-key")) == "new-key"
    service.repository.get_default_for_user = lambda _: None
    with pytest.raises(ModelSettingsValidationError):
        personal_catalog_key(service, user, ModelCatalogRequest(base_url=setting.base_url))


def test_catalog_api_requires_login_and_returns_typed_directory(monkeypatch):
    app = create_app()
    app.dependency_overrides[get_model_settings_service] = lambda: SimpleNamespace()
    client = TestClient(app)
    payload = {"base_url": "https://provider.example", "api_key": "synthetic-key"}
    assert client.post("/api/v1/settings/model/catalog", json=payload).status_code == 401
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=17)
    pool = CatalogPool({"data": [{"id": "example-model"}]})
    monkeypatch.setattr("backend.app.api.v1.settings.ModelCatalogClient", lambda: ModelCatalogClient(lambda: pool))
    response = client.post("/api/v1/settings/model/catalog", json=payload)
    assert response.status_code == 200
    assert response.json()["data"] == {"models": ["example-model"]}
    assert "synthetic-key" not in response.text


def test_catalog_private_network_resolution_is_rejected():
    with pytest.raises(ModelCatalogError, match="公网"):
        ModelCatalogClient().fetch("https://127.0.0.1/v1", "synthetic-key")


def test_invalid_response_and_size_limit():
    for payload in [{"error": "secret"}, {"data": "invalid"}, {"data": ["x" * 1_000_001]}]:
        with pytest.raises(ModelCatalogError):
            ModelCatalogClient(lambda: CatalogPool(payload)).fetch("https://provider.example", "key")

from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.app.api.v1.deps import get_auth_service
from backend.app.core.config import Settings
from backend.app.core.security import create_access_token
from backend.app.main import create_app
from backend.app.models import ModelSetting, User
from backend.app.services.auth import AuthService


FERNET_TEST_KEY = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="


def load_model_settings_module():
    try:
        return importlib.import_module("backend.app.services.model_settings")
    except ModuleNotFoundError as exc:
        pytest.fail(f"缺少模型设置服务模块: {exc.name}")


def load_model_settings_api_module():
    try:
        return importlib.import_module("backend.app.api.v1.settings")
    except ModuleNotFoundError as exc:
        pytest.fail(f"缺少模型设置 API 模块: {exc.name}")


def load_openai_provider_module():
    try:
        return importlib.import_module("backend.app.providers.openai_compatible")
    except ModuleNotFoundError as exc:
        pytest.fail(f"缺少 OpenAI-compatible Provider 模块: {exc.name}")


@dataclass
class FakeModelSettingsRepository:
    settings_by_user: dict[int, ModelSetting]
    committed: bool = False
    rolled_back: bool = False

    def get_for_user(self, user_id: int) -> ModelSetting | None:
        return self.settings_by_user.get(user_id)

    def save(self, setting: ModelSetting) -> None:
        if setting.id is None:
            setting.id = len(self.settings_by_user) + 1
        self.settings_by_user[setting.user_id] = setting

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True


@dataclass
class FakeProvider:
    content: str = "ok"
    should_raise: Exception | None = None
    calls: list[dict[str, Any]] | None = None

    def chat_completion(self, config: Any, messages: list[dict[str, str]], timeout_seconds: float) -> str:
        if self.calls is None:
            self.calls = []
        self.calls.append(
            {
                "config": config,
                "messages": messages,
                "timeout_seconds": timeout_seconds,
            }
        )
        if self.should_raise is not None:
            raise self.should_raise
        return self.content


@dataclass
class TokenAuthRepository:
    user: User

    def get_user_by_id(self, user_id: int) -> User | None:
        return self.user if self.user.id == user_id else None


def make_user(user_id: int = 1) -> User:
    return User(
        id=user_id,
        email=f"user{user_id}@edunova.local",
        hashed_password="not-used",
        display_name="测试学生",
        role="student",
        starter_mode="blank",
    )


def make_settings(**overrides: Any) -> Settings:
    defaults = {
        "_env_file": None,
        "jwt_secret": "model-settings-test-secret-with-more-than-32-bytes",
        "system_model_provider": "openai_compatible",
        "system_model_base_url": "https://model.example.local/v1",
        "system_model_api_key": "sk-system-secret",
        "system_chat_model": "system-chat",
        "system_embedding_model": "system-embedding",
        "model_settings_encryption_key": FERNET_TEST_KEY,
        "model_request_timeout_seconds": 12.5,
    }
    defaults.update(overrides)
    return Settings(**defaults)


def as_dict(value: Any) -> dict[str, Any]:
    return value.model_dump() if hasattr(value, "model_dump") else value


def test_model_settings_route_requires_login() -> None:
    client = TestClient(create_app())

    response = client.get("/api/v1/settings/model")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_model_settings_uses_system_configuration_without_leaking_key() -> None:
    module = load_model_settings_module()
    user = make_user()
    service = module.ModelSettingsService(
        repository=FakeModelSettingsRepository(settings_by_user={}),
        settings=make_settings(),
        provider=FakeProvider(),
    )

    summary = as_dict(service.get_summary(user))
    runtime = service.resolve_runtime_config(user)

    assert summary["source"] == "system"
    assert summary["provider"] == "openai_compatible"
    assert summary["base_url"] == "https://model.example.local/v1"
    assert summary["chat_model"] == "system-chat"
    assert summary["embedding_model"] == "system-embedding"
    assert summary["has_api_key"] is True
    assert summary["api_key_masked"].startswith("sk-s")
    assert summary["api_key_masked"].endswith("cret")
    assert summary["can_use_model"] is True
    assert "sk-system-secret" not in str(summary)
    assert runtime.api_key == "sk-system-secret"
    assert runtime.source == "system"


def test_save_user_model_settings_encrypts_key_and_user_config_wins() -> None:
    module = load_model_settings_module()
    user = make_user()
    repo = FakeModelSettingsRepository(settings_by_user={})
    service = module.ModelSettingsService(repository=repo, settings=make_settings(), provider=FakeProvider())
    request = module.SaveModelSettingsRequest(
        provider="openai_compatible",
        base_url="https://user-model.example.local/v1",
        api_key="sk-user-secret",
        chat_model="user-chat",
        embedding_model="user-embedding",
    )

    summary = as_dict(service.save(user, request))
    stored = repo.settings_by_user[user.id]
    runtime = service.resolve_runtime_config(user)

    assert repo.committed is True
    assert stored.api_key_ciphertext is not None
    assert "sk-user-secret" not in stored.api_key_ciphertext
    assert summary["source"] == "user"
    assert summary["api_key_masked"].startswith("sk-u")
    assert runtime.source == "user"
    assert runtime.api_key == "sk-user-secret"
    assert runtime.chat_model == "user-chat"


def test_save_empty_api_key_preserves_existing_encrypted_key() -> None:
    module = load_model_settings_module()
    user = make_user()
    repo = FakeModelSettingsRepository(settings_by_user={})
    service = module.ModelSettingsService(repository=repo, settings=make_settings(), provider=FakeProvider())
    service.save(
        user,
        module.SaveModelSettingsRequest(
            provider="openai_compatible",
            base_url="https://user-model.example.local/v1",
            api_key="sk-user-secret",
            chat_model="user-chat",
            embedding_model="user-embedding",
        ),
    )
    first_ciphertext = repo.settings_by_user[user.id].api_key_ciphertext

    service.save(
        user,
        module.SaveModelSettingsRequest(
            provider="openai_compatible",
            base_url="https://user-model.example.local/v1",
            api_key="",
            chat_model="new-chat",
            embedding_model="new-embedding",
        ),
    )

    assert repo.settings_by_user[user.id].api_key_ciphertext == first_ciphertext
    assert service.resolve_runtime_config(user).api_key == "sk-user-secret"
    assert service.resolve_runtime_config(user).chat_model == "new-chat"


def test_save_user_api_key_requires_encryption_key() -> None:
    module = load_model_settings_module()
    user = make_user()
    service = module.ModelSettingsService(
        repository=FakeModelSettingsRepository(settings_by_user={}),
        settings=make_settings(model_settings_encryption_key=""),
        provider=FakeProvider(),
    )

    with pytest.raises(module.ModelSettingsConfigurationError, match="MODEL_SETTINGS_ENCRYPTION_KEY"):
        service.save(
            user,
            module.SaveModelSettingsRequest(
                provider="openai_compatible",
                base_url="https://user-model.example.local/v1",
                api_key="sk-user-secret",
                chat_model="user-chat",
                embedding_model="user-embedding",
            ),
        )


def test_model_settings_test_connection_uses_current_runtime_config() -> None:
    module = load_model_settings_module()
    user = make_user()
    provider = FakeProvider(content="ok")
    service = module.ModelSettingsService(
        repository=FakeModelSettingsRepository(settings_by_user={}),
        settings=make_settings(),
        provider=provider,
    )

    result = as_dict(service.test_connection(user))

    assert result["ok"] is True
    assert result["source"] == "system"
    assert result["chat_model"] == "system-chat"
    assert provider.calls is not None
    assert provider.calls[0]["messages"][-1]["content"] == "请只回复 ok。"


def test_openai_compatible_provider_posts_chat_completions_and_reads_content() -> None:
    provider_module = load_openai_provider_module()
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": "基于资料的回答",
                        }
                    }
                ]
            },
        )

    provider = provider_module.OpenAICompatibleChatProvider(transport=httpx.MockTransport(handler))
    config = provider_module.OpenAICompatibleConfig(
        base_url="https://model.example.local/v1",
        api_key="sk-user-secret",
        chat_model="user-chat",
    )

    content = provider.chat_completion(
        config=config,
        messages=[{"role": "user", "content": "请回答"}],
        timeout_seconds=3.0,
    )

    assert content == "基于资料的回答"
    assert str(requests[0].url) == "https://model.example.local/v1/chat/completions"
    assert requests[0].headers["authorization"] == "Bearer sk-user-secret"
    assert requests[0].read()


@pytest.mark.parametrize(
    ("response", "expected_message"),
    [
        (httpx.Response(401, json={"error": "unauthorized"}), "模型服务认证失败"),
        (httpx.Response(200, content=b"not json"), "模型服务返回了无法解析的响应"),
        (httpx.Response(200, json={"choices": [{"message": {"content": "  "}}]}), "模型服务没有返回可用内容"),
    ],
)
def test_openai_compatible_provider_returns_stable_errors(response: httpx.Response, expected_message: str) -> None:
    provider_module = load_openai_provider_module()
    provider = provider_module.OpenAICompatibleChatProvider(
        transport=httpx.MockTransport(lambda _request: response)
    )
    config = provider_module.OpenAICompatibleConfig(
        base_url="https://model.example.local/v1",
        api_key="sk-user-secret",
        chat_model="user-chat",
    )

    with pytest.raises(provider_module.ModelProviderError, match=expected_message):
        provider.chat_completion(config=config, messages=[{"role": "user", "content": "hi"}], timeout_seconds=3.0)


def test_openai_compatible_provider_wraps_timeout() -> None:
    provider_module = load_openai_provider_module()

    def raise_timeout(_request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timeout")

    provider = provider_module.OpenAICompatibleChatProvider(transport=httpx.MockTransport(raise_timeout))
    config = provider_module.OpenAICompatibleConfig(
        base_url="https://model.example.local/v1",
        api_key="sk-user-secret",
        chat_model="user-chat",
    )

    with pytest.raises(provider_module.ModelProviderError, match="模型服务请求超时"):
        provider.chat_completion(config=config, messages=[{"role": "user", "content": "hi"}], timeout_seconds=3.0)


def test_model_settings_routes_use_documented_envelopes() -> None:
    api_module = load_model_settings_api_module()
    module = load_model_settings_module()
    user = make_user()
    settings = make_settings()
    provider = FakeProvider(content="ok")
    repo = FakeModelSettingsRepository(settings_by_user={})
    service = module.ModelSettingsService(repository=repo, settings=settings, provider=provider)
    app = create_app()
    app.dependency_overrides[get_auth_service] = lambda: AuthService(
        repository=TokenAuthRepository(user),
        settings=settings,
    )
    app.dependency_overrides[api_module.get_model_settings_service] = lambda: service
    client = TestClient(app)
    token = create_access_token(str(user.id), settings=settings)

    get_response = client.get("/api/v1/settings/model", headers={"Authorization": f"Bearer {token}"})
    put_response = client.put(
        "/api/v1/settings/model",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "provider": "openai_compatible",
            "base_url": "https://user-model.example.local/v1",
            "api_key": "sk-user-secret",
            "chat_model": "user-chat",
            "embedding_model": "user-embedding",
        },
    )
    test_response = client.post("/api/v1/settings/model/test", headers={"Authorization": f"Bearer {token}"})

    assert get_response.status_code == 200
    assert get_response.json()["data"]["source"] == "system"
    assert "sk-system-secret" not in str(get_response.json())
    assert put_response.status_code == 200
    assert put_response.json()["data"]["source"] == "user"
    assert "sk-user-secret" not in str(put_response.json())
    assert test_response.status_code == 200
    assert test_response.json()["data"]["ok"] is True

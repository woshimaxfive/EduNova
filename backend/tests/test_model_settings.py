from __future__ import annotations

import importlib
from dataclasses import dataclass
from datetime import datetime
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

    def __post_init__(self) -> None:
        self.settings_by_id: dict[int, ModelSetting] = {}
        for index, setting in enumerate(self.settings_by_user.values(), start=1):
            if setting.id is None:
                setting.id = index
            if not setting.is_default:
                setting.is_default = True
            self.settings_by_id[setting.id] = setting

    def get_for_user(self, user_id: int) -> ModelSetting | None:
        return self.get_default_for_user(user_id)

    def get_default_for_user(self, user_id: int) -> ModelSetting | None:
        default = next(
            (
                setting
                for setting in self.settings_by_id.values()
                if setting.user_id == user_id and setting.is_default
            ),
            None,
        )
        return default or self.settings_by_user.get(user_id)

    def get_embedding_default_for_user(self, user_id: int) -> ModelSetting | None:
        return next(
            (
                setting
                for setting in self.settings_by_id.values()
                if setting.user_id == user_id and setting.is_embedding_default
            ),
            None,
        )

    def list_for_user(self, user_id: int) -> list[ModelSetting]:
        return sorted(
            [setting for setting in self.settings_by_id.values() if setting.user_id == user_id],
            key=lambda setting: (not setting.is_default, not setting.is_embedding_default, -(setting.id or 0)),
        )

    def get_by_id_for_user(self, setting_id: int, user_id: int) -> ModelSetting | None:
        setting = self.settings_by_id.get(setting_id)
        if setting is None or setting.user_id != user_id:
            return None
        return setting

    def save(self, setting: ModelSetting) -> None:
        if setting.id is None:
            setting.id = len(self.settings_by_id) + 1
        self.settings_by_id[setting.id] = setting
        if setting.is_default:
            self.settings_by_user[setting.user_id] = setting

    def delete(self, setting: ModelSetting) -> None:
        if setting.id is not None:
            self.settings_by_id.pop(setting.id, None)
        if self.settings_by_user.get(setting.user_id) is setting:
            self.settings_by_user.pop(setting.user_id, None)

    def unset_defaults_for_user(self, user_id: int, except_setting_id: int | None = None) -> None:
        for setting in self.settings_by_id.values():
            if setting.user_id == user_id and setting.id != except_setting_id:
                setting.is_default = False
        if except_setting_id is None:
            self.settings_by_user.pop(user_id, None)

    def unset_embedding_defaults_for_user(self, user_id: int, except_setting_id: int | None = None) -> None:
        for setting in self.settings_by_id.values():
            if setting.user_id == user_id and setting.id != except_setting_id:
                setting.is_embedding_default = False

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
    def embed_texts(
        self,
        config: Any,
        texts: list[str],
        timeout_seconds: float,
        dimensions: int = 1536,
    ) -> list[list[float]]:
        if self.calls is None:
            self.calls = []
        self.calls.append(
            {
                "config": config,
                "texts": texts,
                "timeout_seconds": timeout_seconds,
                "dimensions": dimensions,
            }
        )
        if self.should_raise is not None:
            raise self.should_raise
        return [[1.0, 0.0, 0.0] + [0.0] * (dimensions - 3) for _ in texts]


class ImmediateExecutionRuntime:
    def execute(self, *, call, **_kwargs):
        return call()


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


def test_system_embedding_connection_can_use_a_different_provider_endpoint() -> None:
    module = load_model_settings_module()
    user = make_user()
    service = module.ModelSettingsService(
        repository=FakeModelSettingsRepository(settings_by_user={}),
        settings=make_settings(
            system_embedding_provider="openai_compatible",
            system_embedding_base_url="https://embedding.example.local/v1",
            system_embedding_api_key="embedding-system-secret",
            system_embedding_model="embedding-system-model",
        ),
        provider=FakeProvider(),
    )

    summary = as_dict(service.get_summary(user))
    embedding_runtime = service.resolve_embedding_runtime_config(user)

    assert summary["base_url"] == "https://model.example.local/v1"
    assert summary["embedding_base_url"] == "https://embedding.example.local/v1"
    assert summary["api_key_masked"] != summary["embedding_api_key_masked"]
    assert "embedding-system-secret" not in str(summary)
    assert embedding_runtime.base_url == "https://embedding.example.local/v1"
    assert embedding_runtime.api_key == "embedding-system-secret"
    assert embedding_runtime.embedding_model == "embedding-system-model"


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


def test_save_user_model_settings_allows_embedding_model_to_be_optional() -> None:
    module = load_model_settings_module()
    user = make_user()
    repo = FakeModelSettingsRepository(settings_by_user={})
    service = module.ModelSettingsService(repository=repo, settings=make_settings(), provider=FakeProvider())
    request = module.SaveModelSettingsRequest(
        provider="openai_compatible",
        base_url="https://spark-api-open.xf-yun.com/v1",
        api_key="spark-user-token",
        chat_model="4.0Ultra",
    )

    summary = as_dict(service.save(user, request))
    stored = repo.settings_by_user[user.id]

    assert stored.embedding_model is None
    assert summary["embedding_model"] == "system-embedding"
    assert summary["embedding_base_url"] == "https://model.example.local/v1"
    assert summary["base_url"] == "https://spark-api-open.xf-yun.com/v1"
    assert summary["chat_model"] == "4.0Ultra"


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
        execution_runtime=ImmediateExecutionRuntime(),
    )

    result = as_dict(service.test_connection(user))

    assert result["ok"] is True
    assert result["source"] == "system"
    assert result["chat_model"] == "system-chat"
    assert provider.calls is not None
    assert provider.calls[0]["messages"][-1]["content"] == "请只回复 ok。"


def test_multi_model_configs_are_independently_saved_and_defaulted() -> None:
    module = load_model_settings_module()
    user = make_user()
    repo = FakeModelSettingsRepository(settings_by_user={})
    service = module.ModelSettingsService(repository=repo, settings=make_settings(), provider=FakeProvider())

    spark = as_dict(service.create_config(
        user,
        module.SaveModelConfigRequest(
            display_name="星火 Lite",
            preset_id="spark",
            provider="openai_compatible",
            base_url="https://spark-api-open.xf-yun.com/v1",
            api_key="spark-secret",
            chat_model="lite",
            make_default=True,
        ),
    ))
    local = as_dict(service.create_config(
        user,
        module.SaveModelConfigRequest(
            display_name="本地 Ollama",
            preset_id="ollama",
            provider="openai_compatible",
            base_url="http://localhost:11434/v1",
            chat_model="qwen3:8b",
            make_default=False,
        ),
    ))

    configs = as_dict(service.list_configs(user))
    runtime = service.resolve_runtime_config(user)

    assert spark["is_default"] is True
    assert local["is_default"] is False
    assert configs["default_config_id"] == spark["id"]
    assert [config["display_name"] for config in configs["configs"]] == ["星火 Lite", "本地 Ollama"]
    assert "spark-secret" not in str(configs)
    assert repo.settings_by_id[spark["id"]].api_key_ciphertext != repo.settings_by_id[local["id"]].api_key_ciphertext
    assert runtime.chat_model == "lite"
    assert runtime.api_key == "spark-secret"

    service.set_default_config(user, local["id"])
    runtime = service.resolve_runtime_config(user)
    configs = as_dict(service.list_configs(user))

    assert runtime.chat_model == "qwen3:8b"
    assert runtime.api_key is None
    assert runtime.can_use_model is True
    assert configs["default_config_id"] == local["id"]
    assert [config["is_default"] for config in configs["configs"]] == [True, False]


def test_chat_and_embedding_defaults_can_use_different_configs() -> None:
    module = load_model_settings_module()
    user = make_user()
    repo = FakeModelSettingsRepository(settings_by_user={})
    service = module.ModelSettingsService(repository=repo, settings=make_settings(), provider=FakeProvider())

    spark = as_dict(service.create_config(
        user,
        module.SaveModelConfigRequest(
            display_name="星火回答",
            preset_id="spark",
            provider="openai_compatible",
            base_url="https://spark-api-open.xf-yun.com/v1",
            api_key="spark-secret",
            chat_model="lite",
            make_default=True,
        ),
    ))
    qwen_embedding = as_dict(service.create_config(
        user,
        module.SaveModelConfigRequest(
            display_name="通义向量",
            preset_id="qwen",
            provider="openai_compatible",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            api_key="qwen-secret",
            embedding_model="text-embedding-v4",
            make_embedding_default=True,
        ),
    ))

    configs = as_dict(service.list_configs(user))
    chat_runtime = service.resolve_runtime_config(user)
    embedding_runtime = service.resolve_embedding_runtime_config(user)

    assert configs["default_config_id"] == spark["id"]
    assert configs["default_chat_config_id"] == spark["id"]
    assert configs["default_embedding_config_id"] == qwen_embedding["id"]
    assert chat_runtime.base_url == "https://spark-api-open.xf-yun.com/v1"
    assert chat_runtime.chat_model == "lite"
    assert chat_runtime.api_key == "spark-secret"
    assert embedding_runtime.base_url == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert embedding_runtime.embedding_model == "text-embedding-v4"
    assert embedding_runtime.api_key == "qwen-secret"


def test_one_config_can_combine_different_chat_and_embedding_providers() -> None:
    module = load_model_settings_module()
    user = make_user()
    repo = FakeModelSettingsRepository(settings_by_user={})
    provider = FakeProvider()
    service = module.ModelSettingsService(
        repository=repo,
        settings=make_settings(),
        provider=provider,
        execution_runtime=ImmediateExecutionRuntime(),
    )

    combined = as_dict(service.create_config(
        user,
        module.SaveModelConfigRequest(
            display_name="星火回答 + 通义向量",
            preset_id="spark",
            provider="openai_compatible",
            base_url="https://spark-api-open.xf-yun.com/v1",
            api_key="spark-chat-secret",
            chat_model="lite",
            embedding_preset_id="qwen",
            embedding_provider="openai_compatible",
            embedding_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            embedding_api_key="qwen-embedding-secret",
            embedding_model="text-embedding-v4",
            make_default=True,
            make_embedding_default=True,
        ),
    ))

    chat_runtime = service.resolve_runtime_config(user)
    embedding_runtime = service.resolve_embedding_runtime_config(user)
    stored = repo.settings_by_id[combined["id"]]
    service.chat_completion(user, [{"role": "user", "content": "测试组合配置"}])
    service.embedding_vectors(user, ["测试向量连接"])

    assert combined["preset_id"] == "spark"
    assert combined["embedding_preset_id"] == "qwen"
    assert combined["base_url"] == "https://spark-api-open.xf-yun.com/v1"
    assert combined["embedding_base_url"] == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert combined["api_key_masked"] != combined["embedding_api_key_masked"]
    assert "spark-chat-secret" not in str(combined)
    assert "qwen-embedding-secret" not in str(combined)
    assert stored.api_key_ciphertext != stored.embedding_api_key_ciphertext
    assert chat_runtime.base_url == "https://spark-api-open.xf-yun.com/v1"
    assert chat_runtime.api_key == "spark-chat-secret"
    assert chat_runtime.chat_model == "lite"
    assert embedding_runtime.base_url == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert embedding_runtime.api_key == "qwen-embedding-secret"
    assert embedding_runtime.embedding_model == "text-embedding-v4"
    assert provider.calls is not None
    assert provider.calls[0]["config"].base_url == "https://spark-api-open.xf-yun.com/v1"
    assert provider.calls[0]["config"].api_key == "spark-chat-secret"
    assert provider.calls[1]["config"].base_url == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert provider.calls[1]["config"].api_key == "qwen-embedding-secret"


def test_setting_default_requires_matching_capability() -> None:
    module = load_model_settings_module()
    user = make_user()
    repo = FakeModelSettingsRepository(settings_by_user={})
    service = module.ModelSettingsService(repository=repo, settings=make_settings(), provider=FakeProvider())
    embedding_only = as_dict(service.create_config(
        user,
        module.SaveModelConfigRequest(
            display_name="仅向量",
            preset_id="custom",
            provider="openai_compatible",
            base_url="https://embedding.example.local/v1",
            api_key="embedding-secret",
            embedding_model="embedding-model",
        ),
    ))

    with pytest.raises(module.ModelSettingsValidationError, match="没有回答模型"):
        service.set_default_config(user, embedding_only["id"])


def test_split_model_defaults_migration_preserves_existing_embedding_default() -> None:
    migration_path = (
        __import__("pathlib").Path(__file__).resolve().parents[1]
        / "migrations"
        / "versions"
        / "20260713_0018_split_model_defaults.py"
    )
    migration_text = migration_path.read_text(encoding="utf-8")

    assert 'revision = "20260713_0018"' in migration_text
    assert 'down_revision = "20260713_0017"' in migration_text
    assert "is_embedding_default" in migration_text
    assert "WHERE is_default = true" in migration_text


def test_split_embedding_connection_migration_preserves_legacy_values() -> None:
    migration_path = (
        __import__("pathlib").Path(__file__).resolve().parents[1]
        / "migrations"
        / "versions"
        / "20260713_0019_split_embedding_connection.py"
    )
    migration_text = migration_path.read_text(encoding="utf-8")

    assert 'revision = "20260713_0019"' in migration_text
    assert 'down_revision = "20260713_0018"' in migration_text
    assert "embedding_provider" in migration_text
    assert "embedding_base_url" in migration_text
    assert "embedding_api_key_ciphertext" in migration_text
    assert "embedding_provider = provider" in migration_text
    assert "embedding_api_key_ciphertext = api_key_ciphertext" in migration_text


def test_update_config_preserves_key_and_cross_user_access_is_blocked() -> None:
    module = load_model_settings_module()
    user = make_user()
    other_user = make_user(2)
    repo = FakeModelSettingsRepository(settings_by_user={})
    service = module.ModelSettingsService(repository=repo, settings=make_settings(), provider=FakeProvider())
    created = as_dict(service.create_config(
        user,
        module.SaveModelConfigRequest(
            display_name="DeepSeek 主力",
            preset_id="deepseek",
            provider="openai_compatible",
            base_url="https://api.deepseek.com",
            api_key="deepseek-secret",
            chat_model="deepseek-v4-pro",
            make_default=True,
        ),
    ))

    updated = as_dict(service.update_config(
        user,
        created["id"],
        module.UpdateModelConfigRequest(
            display_name="DeepSeek 默认",
            api_key="",
            chat_model="deepseek-v4-pro",
        ),
    ))

    assert updated["display_name"] == "DeepSeek 默认"
    assert service.resolve_runtime_config(user).api_key == "deepseek-secret"
    with pytest.raises(module.ModelSettingsNotFoundError):
        service.update_config(other_user, created["id"], module.UpdateModelConfigRequest(chat_model="hijack"))


def test_changing_provider_endpoint_without_new_key_drops_old_credentials() -> None:
    module = load_model_settings_module()
    user = make_user()
    repo = FakeModelSettingsRepository(settings_by_user={})
    service = module.ModelSettingsService(repository=repo, settings=make_settings(), provider=FakeProvider())
    created = as_dict(service.create_config(
        user,
        module.SaveModelConfigRequest(
            display_name="组合配置",
            provider="openai_compatible",
            base_url="https://chat-a.example.local/v1",
            api_key="chat-a-secret",
            chat_model="chat-a",
            embedding_provider="openai_compatible",
            embedding_base_url="https://embedding-a.example.local/v1",
            embedding_api_key="embedding-a-secret",
            embedding_model="embedding-a",
            make_default=True,
            make_embedding_default=True,
        ),
    ))

    service.update_config(
        user,
        created["id"],
        module.UpdateModelConfigRequest(
            provider="openai_compatible",
            base_url="https://chat-b.example.local/v1",
            embedding_provider="openai_compatible",
            embedding_base_url="https://embedding-b.example.local/v1",
        ),
    )
    stored = repo.settings_by_id[created["id"]]

    assert stored.api_key_ciphertext is None
    assert stored.embedding_api_key_ciphertext is None
    assert service._runtime_from_user_setting(stored).api_key is None
    assert service._embedding_runtime_from_user_setting(stored).api_key is None


def test_changing_only_embedding_endpoint_does_not_reuse_chat_key() -> None:
    module = load_model_settings_module()
    user = make_user()
    repo = FakeModelSettingsRepository(settings_by_user={})
    service = module.ModelSettingsService(repository=repo, settings=make_settings(), provider=FakeProvider())
    created = as_dict(service.create_config(
        user,
        module.SaveModelConfigRequest(
            display_name="独立向量连接",
            provider="openai_compatible",
            base_url="https://chat.example.local/v1",
            api_key="chat-secret",
            chat_model="chat-model",
            embedding_provider="openai_compatible",
            embedding_base_url="https://embedding-a.example.local/v1",
            embedding_api_key="embedding-secret",
            embedding_model="embedding-model",
            make_default=True,
            make_embedding_default=True,
        ),
    ))

    service.update_config(
        user,
        created["id"],
        module.UpdateModelConfigRequest(
            embedding_provider="openai_compatible",
            embedding_base_url="https://embedding-b.example.local/v1",
        ),
    )
    stored = repo.settings_by_id[created["id"]]

    assert service._runtime_from_user_setting(stored).api_key == "chat-secret"
    assert stored.embedding_api_key_ciphertext is None
    assert service._embedding_runtime_from_user_setting(stored).api_key is None


def test_delete_default_config_promotes_latest_remaining_config() -> None:
    module = load_model_settings_module()
    user = make_user()
    repo = FakeModelSettingsRepository(settings_by_user={})
    service = module.ModelSettingsService(repository=repo, settings=make_settings(), provider=FakeProvider())
    first = as_dict(service.create_config(
        user,
        module.SaveModelConfigRequest(
            display_name="星火",
            preset_id="spark",
            provider="openai_compatible",
            base_url="https://spark-api-open.xf-yun.com/v1",
            api_key="spark-secret",
            chat_model="lite",
            make_default=True,
        ),
    ))
    second = as_dict(service.create_config(
        user,
        module.SaveModelConfigRequest(
            display_name="Kimi",
            preset_id="kimi",
            provider="openai_compatible",
            base_url="https://api.moonshot.cn/v1",
            api_key="kimi-secret",
            chat_model="kimi-k2.6",
            make_default=False,
        ),
    ))

    configs = as_dict(service.delete_config(user, first["id"]))

    assert configs["default_config_id"] == second["id"]
    assert service.resolve_runtime_config(user).chat_model == "kimi-k2.6"
    with pytest.raises(module.ModelSettingsNotFoundError):
        service.delete_config(user, first["id"])


def test_connection_test_can_target_one_config_and_persist_safe_status() -> None:
    module = load_model_settings_module()
    user = make_user()
    provider = FakeProvider(content="ok")
    repo = FakeModelSettingsRepository(settings_by_user={})
    service = module.ModelSettingsService(
        repository=repo,
        settings=make_settings(),
        provider=provider,
        execution_runtime=ImmediateExecutionRuntime(),
    )
    created = as_dict(service.create_config(
        user,
        module.SaveModelConfigRequest(
            display_name="星火 Lite",
            preset_id="spark",
            provider="openai_compatible",
            base_url="https://spark-api-open.xf-yun.com/v1",
            api_key="spark-secret",
            chat_model="lite",
            make_default=True,
        ),
    ))

    result = as_dict(service.test_config_connection(user, created["id"]))
    stored = repo.settings_by_id[created["id"]]

    assert result["ok"] is True
    assert result["config_id"] == created["id"]
    assert result["source"] == "user"
    assert result["chat_model"] == "lite"
    assert stored.last_test_ok is True
    assert stored.last_test_message == "模型连接成功。"
    assert isinstance(stored.last_tested_at, datetime)
    assert provider.calls is not None
    assert provider.calls[0]["config"].chat_model == "lite"


def test_connection_tests_persist_chat_and_embedding_independently() -> None:
    module = load_model_settings_module()
    user = make_user()
    provider = FakeProvider(content="ok")
    repo = FakeModelSettingsRepository(settings_by_user={})
    service = module.ModelSettingsService(
        repository=repo,
        settings=make_settings(),
        provider=provider,
        execution_runtime=ImmediateExecutionRuntime(),
    )
    created = as_dict(service.create_config(
        user,
        module.SaveModelConfigRequest(
            display_name="双模型配置",
            preset_id="custom",
            provider="openai_compatible",
            base_url="https://models.example.local/v1",
            api_key="safe-secret",
            chat_model="chat-model",
            embedding_model="embedding-model",
            make_default=True,
        ),
    ))

    chat_result = as_dict(service.test_config_connection(user, created["id"], operation="chat"))
    embedding_result = as_dict(service.test_config_connection(user, created["id"], operation="embedding"))
    stored = repo.settings_by_id[created["id"]]
    summary = as_dict(service.list_configs(user))["configs"][0]

    assert chat_result["operation"] == "chat"
    assert chat_result["model"] == "chat-model"
    assert embedding_result["operation"] == "embedding"
    assert embedding_result["model"] == "embedding-model"
    assert stored.connection_test_json["chat"]["ok"] is True
    assert stored.connection_test_json["embedding"]["ok"] is True
    assert summary["connection_tests"]["chat"]["model"] == "chat-model"
    assert summary["connection_tests"]["embedding"]["model"] == "embedding-model"


def test_embedding_not_configured_does_not_overwrite_chat_test_status() -> None:
    module = load_model_settings_module()
    user = make_user()
    repo = FakeModelSettingsRepository(settings_by_user={})
    service = module.ModelSettingsService(
        repository=repo,
        settings=make_settings(),
        provider=FakeProvider(content="ok"),
        execution_runtime=ImmediateExecutionRuntime(),
    )
    created = as_dict(service.create_config(
        user,
        module.SaveModelConfigRequest(
            display_name="仅回答模型",
            provider="openai_compatible",
            base_url="https://models.example.local/v1",
            api_key="safe-secret",
            chat_model="chat-model",
            make_default=True,
        ),
    ))

    chat_result = as_dict(service.test_config_connection(user, created["id"], operation="chat"))
    embedding_result = as_dict(service.test_config_connection(user, created["id"], operation="embedding"))
    stored = repo.settings_by_id[created["id"]]

    assert chat_result["ok"] is True
    assert embedding_result["ok"] is False
    assert embedding_result["code"] == "not_configured"
    assert stored.last_test_ok is True
    assert stored.connection_test_json["chat"]["ok"] is True
    assert stored.connection_test_json["embedding"]["ok"] is False


def test_model_settings_multi_config_migration_contract() -> None:
    migration_text = (
        __import__("pathlib")
        .Path(__file__)
        .resolve()
        .parents[1]
        / "migrations"
        / "versions"
        / "20260704_0006_expand_model_settings_configs.py"
    ).read_text(encoding="utf-8")

    assert "display_name" in migration_text
    assert "preset_id" in migration_text
    assert "is_default" in migration_text
    assert "last_test_ok" in migration_text
    assert "last_test_message" in migration_text
    assert "last_tested_at" in migration_text
    assert "uq_model_settings_user_id" in migration_text
    assert "ix_model_settings_user_default" in migration_text


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


def test_openai_compatible_provider_streams_chat_completion_deltas() -> None:
    provider_module = load_openai_provider_module()
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            content=(
                'data: {"choices":[{"delta":{"content":"第一段"}}]}\n\n'
                'data: {"choices":[{"delta":{"content":"第二段"}}]}\n\n'
                "data: [DONE]\n\n"
            ).encode("utf-8"),
            headers={"content-type": "text/event-stream"},
        )

    provider = provider_module.OpenAICompatibleChatProvider(transport=httpx.MockTransport(handler))
    config = provider_module.OpenAICompatibleConfig(
        base_url="https://model.example.local/v1",
        api_key="sk-user-secret",
        chat_model="user-chat",
    )

    chunks = list(
        provider.chat_completion_stream(
            config=config,
            messages=[{"role": "user", "content": "请回答"}],
            timeout_seconds=3.0,
        )
    )

    assert chunks == ["第一段", "第二段"]
    assert str(requests[0].url) == "https://model.example.local/v1/chat/completions"
    assert requests[0].headers["authorization"] == "Bearer sk-user-secret"
    assert b'"stream":true' in requests[0].read().replace(b" ", b"")


def test_openai_compatible_provider_creates_embeddings_and_retries_without_dimensions() -> None:
    provider_module = load_openai_provider_module()
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        payload = request.read()
        if b'"dimensions"' in payload:
            return httpx.Response(400, json={"error": {"message": "unsupported dimensions"}})
        return httpx.Response(
            200,
            json={
                "object": "list",
                "data": [
                    {"object": "embedding", "index": 0, "embedding": [1.0, 0.0, 0.0] + [0.0] * 1533},
                    {"object": "embedding", "index": 1, "embedding": [0.0, 1.0, 0.0] + [0.0] * 1533},
                ],
                "model": "text-embedding-v4",
            },
        )

    provider = provider_module.OpenAICompatibleChatProvider(transport=httpx.MockTransport(handler))
    config = provider_module.OpenAICompatibleEmbeddingConfig(
        base_url="https://model.example.local/v1",
        api_key="sk-user-secret",
        embedding_model="text-embedding-v4",
    )

    vectors = provider.embed_texts(
        config=config,
        texts=["启发式搜索", "反向传播"],
        timeout_seconds=3.0,
        dimensions=1536,
    )

    assert len(vectors) == 2
    assert len(vectors[0]) == 1536
    assert str(requests[0].url) == "https://model.example.local/v1/embeddings"
    assert b'"dimensions":1536' in requests[0].read().replace(b" ", b"")
    assert b'"dimensions"' not in requests[1].read()
    assert requests[1].headers["authorization"] == "Bearer sk-user-secret"


def test_model_settings_service_uses_embedding_model_for_vectors() -> None:
    module = load_model_settings_module()
    user = make_user()
    provider = FakeProvider()
    service = module.ModelSettingsService(
        repository=FakeModelSettingsRepository(settings_by_user={}),
        settings=make_settings(),
        provider=provider,
    )
    service.save(
        user,
        module.SaveModelSettingsRequest(
            provider="openai_compatible",
            base_url="https://model.example.local/v1",
            api_key="sk-user-secret",
            chat_model="user-chat",
            embedding_model="text-embedding-v4",
        ),
    )

    vectors = service.embedding_vectors(user, ["启发式搜索"], dimensions=1536)

    assert len(vectors) == 1
    assert len(vectors[0]) == 1536
    assert provider.calls is not None
    assert provider.calls[-1]["texts"] == ["启发式搜索"]
    assert provider.calls[-1]["config"].embedding_model == "text-embedding-v4"


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
    service = module.ModelSettingsService(
        repository=repo,
        settings=settings,
        provider=provider,
        execution_runtime=ImmediateExecutionRuntime(),
    )
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
    embedding_test_response = client.post(
        "/api/v1/settings/model/test",
        headers={"Authorization": f"Bearer {token}"},
        json={"operation": "embedding"},
    )
    configs_response = client.get("/api/v1/settings/model/configs", headers={"Authorization": f"Bearer {token}"})
    embedding_config_id = configs_response.json()["data"]["default_config_id"]
    embedding_default_response = client.post(
        f"/api/v1/settings/model/configs/{embedding_config_id}/embedding-default",
        headers={"Authorization": f"Bearer {token}"},
    )
    create_response = client.post(
        "/api/v1/settings/model/configs",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "display_name": "本地 Ollama",
            "preset_id": "ollama",
            "provider": "openai_compatible",
            "base_url": "http://localhost:11434/v1",
            "chat_model": "qwen3:8b",
            "make_default": False,
        },
    )
    created_config_id = create_response.json()["data"]["id"]
    default_response = client.post(
        f"/api/v1/settings/model/configs/{created_config_id}/default",
        headers={"Authorization": f"Bearer {token}"},
    )
    targeted_test_response = client.post(
        f"/api/v1/settings/model/configs/{created_config_id}/test",
        headers={"Authorization": f"Bearer {token}"},
    )
    delete_response = client.delete(
        f"/api/v1/settings/model/configs/{created_config_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    missing_response = client.patch(
        "/api/v1/settings/model/configs/9999",
        headers={"Authorization": f"Bearer {token}"},
        json={"chat_model": "missing"},
    )

    assert get_response.status_code == 200
    assert get_response.json()["data"]["source"] == "system"
    assert "sk-system-secret" not in str(get_response.json())
    assert put_response.status_code == 200
    assert put_response.json()["data"]["source"] == "user"
    assert "sk-user-secret" not in str(put_response.json())
    assert test_response.status_code == 200
    assert test_response.json()["data"]["ok"] is True
    assert test_response.json()["data"]["operation"] == "chat"
    assert embedding_test_response.status_code == 200
    assert embedding_test_response.json()["data"]["operation"] == "embedding"
    assert embedding_test_response.json()["data"]["model"] == "user-embedding"
    assert configs_response.status_code == 200
    assert configs_response.json()["data"]["default_config_id"] is not None
    assert configs_response.json()["data"]["default_chat_config_id"] == embedding_config_id
    assert configs_response.json()["data"]["default_embedding_config_id"] == embedding_config_id
    assert "sk-user-secret" not in str(configs_response.json())
    assert embedding_default_response.status_code == 200
    assert embedding_default_response.json()["data"]["default_embedding_config_id"] == embedding_config_id
    assert create_response.status_code == 200
    assert create_response.json()["data"]["display_name"] == "本地 Ollama"
    assert default_response.status_code == 200
    assert default_response.json()["data"]["default_config_id"] == created_config_id
    assert targeted_test_response.status_code == 200
    assert targeted_test_response.json()["data"]["config_id"] == created_config_id
    assert delete_response.status_code == 200
    assert missing_response.status_code == 404
    assert missing_response.json()["error"]["code"] == "MODEL_SETTINGS_NOT_FOUND"

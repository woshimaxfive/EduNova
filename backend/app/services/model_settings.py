from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, Protocol

from cryptography.fernet import Fernet, InvalidToken
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from backend.app.core.config import Settings
from backend.app.models import ModelSetting, User
from backend.app.providers.openai_compatible import (
    ModelProviderError,
    OpenAICompatibleChatProvider,
    OpenAICompatibleConfig,
)


MODEL_NOT_CONFIGURED_MESSAGE = "已找到资料依据，但当前未配置可用模型。"
LOCAL_PLACEHOLDER_API_KEY = "local-dev-key"


class ModelSettingsConfigurationError(RuntimeError):
    pass


class ModelSettingsNotFoundError(RuntimeError):
    pass


class ModelSettingsValidationError(RuntimeError):
    pass


class ModelNotConfiguredError(RuntimeError):
    pass


class ModelSettingsRepository(Protocol):
    def get_for_user(self, user_id: int) -> ModelSetting | None: ...
    def get_default_for_user(self, user_id: int) -> ModelSetting | None: ...
    def list_for_user(self, user_id: int) -> list[ModelSetting]: ...
    def get_by_id_for_user(self, setting_id: int, user_id: int) -> ModelSetting | None: ...
    def save(self, setting: ModelSetting) -> None: ...
    def delete(self, setting: ModelSetting) -> None: ...
    def unset_defaults_for_user(self, user_id: int, except_setting_id: int | None = None) -> None: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...


class ModelChatProvider(Protocol):
    def chat_completion(
        self,
        config: OpenAICompatibleConfig,
        messages: list[dict[str, str]],
        timeout_seconds: float,
    ) -> str: ...


class SaveModelSettingsRequest(BaseModel):
    provider: Literal["openai_compatible"]
    base_url: str = Field(min_length=1, max_length=500)
    api_key: str | None = Field(default=None, max_length=500)
    chat_model: str = Field(min_length=1, max_length=120)
    embedding_model: str | None = Field(default=None, max_length=120)

    @field_validator("base_url", "api_key", "chat_model", "embedding_model", mode="before")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return str(value).strip()


class SaveModelConfigRequest(SaveModelSettingsRequest):
    display_name: str = Field(min_length=1, max_length=120)
    preset_id: str | None = Field(default=None, max_length=80)
    make_default: bool = False

    @field_validator("display_name", "preset_id", mode="before")
    @classmethod
    def strip_config_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return str(value).strip()


class UpdateModelConfigRequest(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=120)
    preset_id: str | None = Field(default=None, max_length=80)
    provider: Literal["openai_compatible"] | None = None
    base_url: str | None = Field(default=None, min_length=1, max_length=500)
    api_key: str | None = Field(default=None, max_length=500)
    chat_model: str | None = Field(default=None, min_length=1, max_length=120)
    embedding_model: str | None = Field(default=None, max_length=120)
    make_default: bool | None = None

    @field_validator("display_name", "preset_id", "base_url", "api_key", "chat_model", "embedding_model", mode="before")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return str(value).strip()


class ModelSettingsSummary(BaseModel):
    source: Literal["user", "system", "none"]
    provider: str
    base_url: str | None
    chat_model: str | None
    embedding_model: str | None
    has_api_key: bool
    api_key_masked: str | None
    can_use_model: bool


class ModelConfigSummary(BaseModel):
    id: int
    source: Literal["user"] = "user"
    display_name: str
    preset_id: str | None
    provider: str
    base_url: str | None
    chat_model: str | None
    embedding_model: str | None
    has_api_key: bool
    api_key_masked: str | None
    can_use_model: bool
    is_default: bool
    last_test_ok: bool | None
    last_test_message: str | None
    last_tested_at: datetime | None


class ModelSettingsListResponse(BaseModel):
    configs: list[ModelConfigSummary]
    system_summary: ModelSettingsSummary
    default_config_id: int | None


class ModelConnectionTestResponse(BaseModel):
    ok: bool
    source: Literal["user", "system", "none"]
    chat_model: str | None
    message: str
    config_id: int | None = None


@dataclass(frozen=True)
class RuntimeModelConfig:
    source: Literal["user", "system", "none"]
    provider: str
    base_url: str | None
    api_key: str | None
    chat_model: str | None
    embedding_model: str | None
    can_use_model: bool
    config_id: int | None = None


class SqlAlchemyModelSettingsRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_for_user(self, user_id: int) -> ModelSetting | None:
        return self.get_default_for_user(user_id) or self._first_for_user(user_id)

    def get_default_for_user(self, user_id: int) -> ModelSetting | None:
        return self.db.scalar(
            select(ModelSetting)
            .where(ModelSetting.user_id == user_id, ModelSetting.is_default.is_(True))
            .order_by(ModelSetting.updated_at.desc(), ModelSetting.id.desc())
        )

    def list_for_user(self, user_id: int) -> list[ModelSetting]:
        return list(
            self.db.scalars(
                select(ModelSetting)
                .where(ModelSetting.user_id == user_id)
                .order_by(ModelSetting.is_default.desc(), ModelSetting.updated_at.desc(), ModelSetting.id.desc())
            )
        )

    def get_by_id_for_user(self, setting_id: int, user_id: int) -> ModelSetting | None:
        return self.db.scalar(
            select(ModelSetting).where(ModelSetting.id == setting_id, ModelSetting.user_id == user_id)
        )

    def save(self, setting: ModelSetting) -> None:
        self.db.add(setting)
        self.db.flush()

    def delete(self, setting: ModelSetting) -> None:
        self.db.delete(setting)
        self.db.flush()

    def unset_defaults_for_user(self, user_id: int, except_setting_id: int | None = None) -> None:
        statement = update(ModelSetting).where(ModelSetting.user_id == user_id)
        if except_setting_id is not None:
            statement = statement.where(ModelSetting.id != except_setting_id)
        self.db.execute(statement.values(is_default=False))

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()

    def _first_for_user(self, user_id: int) -> ModelSetting | None:
        return self.db.scalar(
            select(ModelSetting)
            .where(ModelSetting.user_id == user_id)
            .order_by(ModelSetting.updated_at.desc(), ModelSetting.id.desc())
        )


class ModelSettingsService:
    def __init__(
        self,
        repository: ModelSettingsRepository,
        settings: Settings,
        provider: ModelChatProvider | None = None,
    ) -> None:
        self.repository = repository
        self.settings = settings
        self.provider = provider or OpenAICompatibleChatProvider()

    def get_summary(self, user: User) -> ModelSettingsSummary:
        user_setting = self.repository.get_default_for_user(user.id)
        if user_setting is not None:
            return self._summary_from_runtime(self._runtime_from_user_setting(user_setting), source="user")

        system_runtime = self._runtime_from_system_settings()
        if system_runtime.base_url or system_runtime.chat_model or system_runtime.embedding_model:
            return self._summary_from_runtime(system_runtime, source="system")
        return self._empty_summary()

    def list_configs(self, user: User) -> ModelSettingsListResponse:
        configs = [self._config_summary(setting) for setting in self.repository.list_for_user(user.id)]
        default_config = next((config for config in configs if config.is_default), None)
        return ModelSettingsListResponse(
            configs=configs,
            system_summary=self._system_summary(),
            default_config_id=default_config.id if default_config else None,
        )

    def save(self, user: User, payload: SaveModelSettingsRequest) -> ModelSettingsSummary:
        existing = self.repository.get_default_for_user(user.id)
        setting = existing or ModelSetting(
            user_id=user.id,
            provider="openai_compatible",
            display_name="默认模型配置",
            is_default=True,
        )
        self._apply_settings_payload(setting, payload)
        setting.is_default = True
        self.repository.unset_defaults_for_user(user.id, except_setting_id=setting.id)
        self._save_and_commit(setting)
        return self.get_summary(user)

    def create_config(self, user: User, payload: SaveModelConfigRequest) -> ModelConfigSummary:
        existing_configs = self.repository.list_for_user(user.id)
        self._ensure_unique_display_name(user.id, payload.display_name)
        setting = ModelSetting(
            user_id=user.id,
            display_name=payload.display_name,
            preset_id=payload.preset_id or None,
            provider="openai_compatible",
            is_default=payload.make_default or not existing_configs,
        )
        self._apply_settings_payload(setting, payload)
        if setting.is_default:
            self.repository.unset_defaults_for_user(user.id)
        self._save_and_commit(setting)
        return self._config_summary(setting)

    def update_config(self, user: User, config_id: int, payload: UpdateModelConfigRequest) -> ModelConfigSummary:
        setting = self._get_user_setting_or_raise(user, config_id)
        if payload.display_name is not None and payload.display_name != setting.display_name:
            self._ensure_unique_display_name(user.id, payload.display_name, exclude_config_id=config_id)
            setting.display_name = payload.display_name
        if payload.preset_id is not None:
            setting.preset_id = payload.preset_id or None
        if payload.provider is not None:
            setting.provider = self._normalize_provider(payload.provider)
        if payload.base_url is not None:
            setting.base_url = payload.base_url
        if payload.chat_model is not None:
            setting.chat_model = payload.chat_model
        if payload.embedding_model is not None:
            setting.embedding_model = payload.embedding_model or None
        if payload.api_key:
            setting.api_key_ciphertext = self._encrypt_api_key(payload.api_key)
        if payload.make_default:
            self.repository.unset_defaults_for_user(user.id, except_setting_id=config_id)
            setting.is_default = True
        self._save_and_commit(setting)
        return self._config_summary(setting)

    def delete_config(self, user: User, config_id: int) -> ModelSettingsListResponse:
        setting = self._get_user_setting_or_raise(user, config_id)
        was_default = setting.is_default
        try:
            self.repository.delete(setting)
            if was_default:
                remaining = [candidate for candidate in self.repository.list_for_user(user.id) if candidate.id != config_id]
                if remaining:
                    remaining[0].is_default = True
                    self.repository.save(remaining[0])
            self.repository.commit()
        except Exception:
            self.repository.rollback()
            raise
        return self.list_configs(user)

    def set_default_config(self, user: User, config_id: int) -> ModelSettingsListResponse:
        setting = self._get_user_setting_or_raise(user, config_id)
        setting.is_default = True
        self.repository.unset_defaults_for_user(user.id, except_setting_id=config_id)
        self._save_and_commit(setting)
        return self.list_configs(user)

    def resolve_runtime_config(self, user: User) -> RuntimeModelConfig:
        user_setting = self.repository.get_default_for_user(user.id)
        if user_setting is not None:
            user_runtime = self._runtime_from_user_setting(user_setting)
            if user_runtime.can_use_model:
                return user_runtime

        system_runtime = self._runtime_from_system_settings()
        if system_runtime.can_use_model:
            return system_runtime
        return RuntimeModelConfig(
            source="none",
            provider="openai_compatible",
            base_url=None,
            api_key=None,
            chat_model=None,
            embedding_model=None,
            can_use_model=False,
        )

    def chat_completion(self, user: User, messages: list[dict[str, str]]) -> str:
        runtime = self.resolve_runtime_config(user)
        if not runtime.can_use_model or runtime.base_url is None or runtime.chat_model is None:
            raise ModelNotConfiguredError(MODEL_NOT_CONFIGURED_MESSAGE)
        return self.provider.chat_completion(
            config=OpenAICompatibleConfig(
                base_url=runtime.base_url,
                api_key=runtime.api_key or LOCAL_PLACEHOLDER_API_KEY,
                chat_model=runtime.chat_model,
            ),
            messages=messages,
            timeout_seconds=self.settings.model_request_timeout_seconds,
        )

    def test_connection(self, user: User) -> ModelConnectionTestResponse:
        setting = self.repository.get_default_for_user(user.id)
        if setting is not None:
            return self.test_config_connection(user, setting.id)

        runtime = self.resolve_runtime_config(user)
        if not runtime.can_use_model:
            return ModelConnectionTestResponse(
                ok=False,
                source=runtime.source,
                chat_model=runtime.chat_model,
                message="当前未配置可用模型。",
            )
        return self._test_runtime(runtime)

    def test_config_connection(self, user: User, config_id: int) -> ModelConnectionTestResponse:
        setting = self._get_user_setting_or_raise(user, config_id)
        runtime = self._runtime_from_user_setting(setting)
        result = self._test_runtime(runtime)
        setting.last_test_ok = result.ok
        setting.last_test_message = result.message
        setting.last_tested_at = datetime.now(UTC)
        self._save_and_commit(setting)
        return result

    def _test_runtime(self, runtime: RuntimeModelConfig) -> ModelConnectionTestResponse:
        if not runtime.can_use_model:
            return ModelConnectionTestResponse(
                ok=False,
                source=runtime.source,
                chat_model=runtime.chat_model,
                message="当前未配置可用模型。",
                config_id=runtime.config_id,
            )

        try:
            self.provider.chat_completion(
                config=OpenAICompatibleConfig(
                    base_url=runtime.base_url or "",
                    api_key=runtime.api_key or LOCAL_PLACEHOLDER_API_KEY,
                    chat_model=runtime.chat_model or "",
                ),
                messages=[
                    {"role": "system", "content": "你是 EduNova 的模型连通性检查器。"},
                    {"role": "user", "content": "请只回复 ok。"},
                ],
                timeout_seconds=self.settings.model_request_timeout_seconds,
            )
        except ModelProviderError as exc:
            return ModelConnectionTestResponse(
                ok=False,
                source=runtime.source,
                chat_model=runtime.chat_model,
                message=str(exc),
                config_id=runtime.config_id,
            )

        return ModelConnectionTestResponse(
            ok=True,
            source=runtime.source,
            chat_model=runtime.chat_model,
            message="模型连接成功。",
            config_id=runtime.config_id,
        )

    def _runtime_from_user_setting(self, setting: ModelSetting) -> RuntimeModelConfig:
        api_key = self._decrypt_api_key(setting.api_key_ciphertext)
        return RuntimeModelConfig(
            source="user",
            provider=self._normalize_provider(setting.provider),
            base_url=setting.base_url,
            api_key=api_key,
            chat_model=setting.chat_model,
            embedding_model=setting.embedding_model,
            can_use_model=self._can_use_model(
                provider=setting.provider,
                base_url=setting.base_url,
                api_key=api_key,
                chat_model=setting.chat_model,
            ),
            config_id=setting.id,
        )

    def _runtime_from_system_settings(self) -> RuntimeModelConfig:
        api_key = self.settings.system_model_api_key.strip()
        return RuntimeModelConfig(
            source="system",
            provider=self._normalize_provider(self.settings.system_model_provider),
            base_url=self.settings.system_model_base_url.strip() or None,
            api_key=api_key or None,
            chat_model=self.settings.system_chat_model.strip() or None,
            embedding_model=self.settings.system_embedding_model.strip() or None,
            can_use_model=self._can_use_model(
                provider=self.settings.system_model_provider,
                base_url=self.settings.system_model_base_url,
                api_key=api_key,
                chat_model=self.settings.system_chat_model,
            ),
        )

    def _config_summary(self, setting: ModelSetting) -> ModelConfigSummary:
        runtime = self._runtime_from_user_setting(setting)
        return ModelConfigSummary(
            id=setting.id,
            display_name=setting.display_name,
            preset_id=setting.preset_id,
            provider=runtime.provider,
            base_url=runtime.base_url,
            chat_model=runtime.chat_model,
            embedding_model=runtime.embedding_model,
            has_api_key=bool(runtime.api_key),
            api_key_masked=self._mask_api_key(runtime.api_key),
            can_use_model=runtime.can_use_model,
            is_default=setting.is_default,
            last_test_ok=setting.last_test_ok,
            last_test_message=setting.last_test_message,
            last_tested_at=setting.last_tested_at,
        )

    def _summary_from_runtime(self, runtime: RuntimeModelConfig, source: Literal["user", "system"]) -> ModelSettingsSummary:
        return ModelSettingsSummary(
            source=source,
            provider=runtime.provider,
            base_url=runtime.base_url,
            chat_model=runtime.chat_model,
            embedding_model=runtime.embedding_model,
            has_api_key=bool(runtime.api_key),
            api_key_masked=self._mask_api_key(runtime.api_key),
            can_use_model=runtime.can_use_model,
        )

    def _system_summary(self) -> ModelSettingsSummary:
        system_runtime = self._runtime_from_system_settings()
        if system_runtime.base_url or system_runtime.chat_model or system_runtime.embedding_model:
            return self._summary_from_runtime(system_runtime, source="system")
        return self._empty_summary()

    @staticmethod
    def _empty_summary() -> ModelSettingsSummary:
        return ModelSettingsSummary(
            source="none",
            provider="openai_compatible",
            base_url=None,
            chat_model=None,
            embedding_model=None,
            has_api_key=False,
            api_key_masked=None,
            can_use_model=False,
        )

    def _apply_settings_payload(self, setting: ModelSetting, payload: SaveModelSettingsRequest) -> None:
        setting.provider = self._normalize_provider(payload.provider)
        setting.base_url = payload.base_url
        setting.chat_model = payload.chat_model
        setting.embedding_model = payload.embedding_model or None
        if isinstance(payload, SaveModelConfigRequest):
            setting.display_name = payload.display_name
            setting.preset_id = payload.preset_id or None
        if payload.api_key:
            setting.api_key_ciphertext = self._encrypt_api_key(payload.api_key)

    def _save_and_commit(self, setting: ModelSetting) -> None:
        try:
            self.repository.save(setting)
            self.repository.commit()
        except Exception:
            self.repository.rollback()
            raise

    def _get_user_setting_or_raise(self, user: User, config_id: int) -> ModelSetting:
        setting = self.repository.get_by_id_for_user(config_id, user.id)
        if setting is None:
            raise ModelSettingsNotFoundError("模型配置不存在。")
        return setting

    def _ensure_unique_display_name(
        self,
        user_id: int,
        display_name: str,
        exclude_config_id: int | None = None,
    ) -> None:
        for setting in self.repository.list_for_user(user_id):
            if setting.id != exclude_config_id and setting.display_name == display_name:
                raise ModelSettingsValidationError("同名模型配置已存在。")

    def _encrypt_api_key(self, api_key: str) -> str:
        fernet = self._fernet()
        return fernet.encrypt(api_key.encode("utf-8")).decode("utf-8")

    def _decrypt_api_key(self, ciphertext: str | None) -> str | None:
        if not ciphertext:
            return None
        try:
            return self._fernet().decrypt(ciphertext.encode("utf-8")).decode("utf-8")
        except InvalidToken:
            return None

    def _fernet(self) -> Fernet:
        encryption_key = self.settings.model_settings_encryption_key.strip()
        if not encryption_key:
            raise ModelSettingsConfigurationError("缺少 MODEL_SETTINGS_ENCRYPTION_KEY，不能保存用户模型密钥。")
        try:
            return Fernet(encryption_key.encode("utf-8"))
        except ValueError as exc:
            raise ModelSettingsConfigurationError("MODEL_SETTINGS_ENCRYPTION_KEY 不是有效的 Fernet key。") from exc

    @classmethod
    def _can_use_model(cls, provider: str | None, base_url: str | None, api_key: str | None, chat_model: str | None) -> bool:
        return (
            cls._normalize_provider(provider or "") == "openai_compatible"
            and cls._is_real_value(base_url)
            and (cls._is_real_api_key(api_key) or cls._allows_empty_api_key(base_url))
            and cls._is_real_value(chat_model)
        )

    @staticmethod
    def _normalize_provider(provider: str) -> str:
        return provider.strip().lower().replace("-", "_")

    @staticmethod
    def _is_real_value(value: str | None) -> bool:
        cleaned = (value or "").strip()
        return bool(cleaned) and cleaned not in {"https://api.example.com/v1", "example-chat-model", "example-embedding-model"}

    @staticmethod
    def _is_real_api_key(value: str | None) -> bool:
        cleaned = (value or "").strip()
        return bool(cleaned) and cleaned not in {"replace-with-your-own-key", "example-key"}

    @staticmethod
    def _allows_empty_api_key(base_url: str | None) -> bool:
        cleaned = (base_url or "").strip().lower()
        return cleaned.startswith(("http://localhost", "http://127.0.0.1", "http://host.docker.internal", "http://0.0.0.0"))

    @staticmethod
    def _mask_api_key(api_key: str | None) -> str | None:
        if not api_key:
            return None
        if len(api_key) <= 8:
            return f"{api_key[:2]}...{api_key[-2:]}"
        return f"{api_key[:4]}...{api_key[-4:]}"

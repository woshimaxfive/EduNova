from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from cryptography.fernet import Fernet, InvalidToken
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.config import Settings
from backend.app.models import ModelSetting, User
from backend.app.providers.openai_compatible import (
    ModelProviderError,
    OpenAICompatibleChatProvider,
    OpenAICompatibleConfig,
)


MODEL_NOT_CONFIGURED_MESSAGE = "已找到资料依据，但当前未配置可用模型。"


class ModelSettingsConfigurationError(RuntimeError):
    pass


class ModelNotConfiguredError(RuntimeError):
    pass


class ModelSettingsRepository(Protocol):
    def get_for_user(self, user_id: int) -> ModelSetting | None: ...
    def save(self, setting: ModelSetting) -> None: ...
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


class ModelSettingsSummary(BaseModel):
    source: Literal["user", "system", "none"]
    provider: str
    base_url: str | None
    chat_model: str | None
    embedding_model: str | None
    has_api_key: bool
    api_key_masked: str | None
    can_use_model: bool


class ModelConnectionTestResponse(BaseModel):
    ok: bool
    source: Literal["user", "system", "none"]
    chat_model: str | None
    message: str


@dataclass(frozen=True)
class RuntimeModelConfig:
    source: Literal["user", "system", "none"]
    provider: str
    base_url: str | None
    api_key: str | None
    chat_model: str | None
    embedding_model: str | None
    can_use_model: bool


class SqlAlchemyModelSettingsRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_for_user(self, user_id: int) -> ModelSetting | None:
        return self.db.scalar(select(ModelSetting).where(ModelSetting.user_id == user_id))

    def save(self, setting: ModelSetting) -> None:
        self.db.add(setting)

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()


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
        user_setting = self.repository.get_for_user(user.id)
        if user_setting is not None:
            return self._summary_from_runtime(self._runtime_from_user_setting(user_setting), source="user")

        system_runtime = self._runtime_from_system_settings()
        if system_runtime.base_url or system_runtime.chat_model or system_runtime.embedding_model:
            return self._summary_from_runtime(system_runtime, source="system")
        return self._empty_summary()

    def save(self, user: User, payload: SaveModelSettingsRequest) -> ModelSettingsSummary:
        existing = self.repository.get_for_user(user.id)
        setting = existing or ModelSetting(user_id=user.id, provider="openai_compatible")
        setting.provider = self._normalize_provider(payload.provider)
        setting.base_url = payload.base_url
        setting.chat_model = payload.chat_model
        setting.embedding_model = payload.embedding_model or None

        if payload.api_key:
            setting.api_key_ciphertext = self._encrypt_api_key(payload.api_key)

        try:
            self.repository.save(setting)
            self.repository.commit()
        except Exception:
            self.repository.rollback()
            raise

        return self.get_summary(user)

    def resolve_runtime_config(self, user: User) -> RuntimeModelConfig:
        user_setting = self.repository.get_for_user(user.id)
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
        if not runtime.can_use_model or runtime.api_key is None or runtime.base_url is None or runtime.chat_model is None:
            raise ModelNotConfiguredError(MODEL_NOT_CONFIGURED_MESSAGE)
        return self.provider.chat_completion(
            config=OpenAICompatibleConfig(
                base_url=runtime.base_url,
                api_key=runtime.api_key,
                chat_model=runtime.chat_model,
            ),
            messages=messages,
            timeout_seconds=self.settings.model_request_timeout_seconds,
        )

    def test_connection(self, user: User) -> ModelConnectionTestResponse:
        runtime = self.resolve_runtime_config(user)
        if not runtime.can_use_model:
            return ModelConnectionTestResponse(
                ok=False,
                source=runtime.source,
                chat_model=runtime.chat_model,
                message="当前未配置可用模型。",
            )

        try:
            self.provider.chat_completion(
                config=OpenAICompatibleConfig(
                    base_url=runtime.base_url or "",
                    api_key=runtime.api_key or "",
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
            )

        return ModelConnectionTestResponse(
            ok=True,
            source=runtime.source,
            chat_model=runtime.chat_model,
            message="模型连接成功。",
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
            and cls._is_real_api_key(api_key)
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
    def _mask_api_key(api_key: str | None) -> str | None:
        if not api_key:
            return None
        if len(api_key) <= 8:
            return f"{api_key[:2]}...{api_key[-2:]}"
        return f"{api_key[:4]}...{api_key[-4:]}"

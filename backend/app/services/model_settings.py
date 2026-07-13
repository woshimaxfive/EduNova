from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Iterator, Literal, Protocol

from cryptography.fernet import Fernet, InvalidToken
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from backend.app.core.config import Settings
from backend.app.models import ModelSetting, User
from backend.app.providers.openai_compatible import (
    ModelProviderError,
    OpenAICompatibleChatProvider,
    OpenAICompatibleConfig,
    OpenAICompatibleEmbeddingConfig,
)
from backend.app.services.model_execution import (
    ModelExecutionContext,
    ModelExecutionRuntime,
    model_execution_scope,
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
    code = "not_configured"
    retryable = False
    retry_after_seconds = None


class ModelSettingsRepository(Protocol):
    def get_for_user(self, user_id: int) -> ModelSetting | None: ...
    def get_default_for_user(self, user_id: int) -> ModelSetting | None: ...
    def get_embedding_default_for_user(self, user_id: int) -> ModelSetting | None: ...
    def list_for_user(self, user_id: int) -> list[ModelSetting]: ...
    def get_by_id_for_user(self, setting_id: int, user_id: int) -> ModelSetting | None: ...
    def save(self, setting: ModelSetting) -> None: ...
    def delete(self, setting: ModelSetting) -> None: ...
    def unset_defaults_for_user(self, user_id: int, except_setting_id: int | None = None) -> None: ...
    def unset_embedding_defaults_for_user(self, user_id: int, except_setting_id: int | None = None) -> None: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...


class ModelChatProvider(Protocol):
    def chat_completion(
        self,
        config: OpenAICompatibleConfig,
        messages: list[dict[str, str]],
        timeout_seconds: float,
    ) -> str: ...

    def chat_completion_stream(
        self,
        config: OpenAICompatibleConfig,
        messages: list[dict[str, str]],
        timeout_seconds: float,
    ) -> Iterator[str]: ...

    def embed_texts(
        self,
        config: OpenAICompatibleEmbeddingConfig,
        texts: list[str],
        timeout_seconds: float,
        dimensions: int = 1536,
    ) -> list[list[float]]: ...


class SaveModelSettingsRequest(BaseModel):
    provider: Literal["openai_compatible"]
    base_url: str = Field(min_length=1, max_length=500)
    api_key: str | None = Field(default=None, max_length=500)
    chat_model: str | None = Field(default=None, max_length=120)
    embedding_model: str | None = Field(default=None, max_length=120)

    @field_validator("base_url", "api_key", "chat_model", "embedding_model", mode="before")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return str(value).strip()

    @model_validator(mode="after")
    def require_at_least_one_model(self) -> SaveModelSettingsRequest:
        if not self.chat_model and not self.embedding_model:
            raise ValueError("回答模型和向量模型至少填写一项。")
        return self


class SaveModelConfigRequest(SaveModelSettingsRequest):
    display_name: str = Field(min_length=1, max_length=120)
    preset_id: str | None = Field(default=None, max_length=80)
    make_default: bool = False
    make_embedding_default: bool = False

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
    chat_model: str | None = Field(default=None, max_length=120)
    embedding_model: str | None = Field(default=None, max_length=120)
    make_default: bool | None = None
    make_embedding_default: bool | None = None

    @field_validator("display_name", "preset_id", "base_url", "api_key", "chat_model", "embedding_model", mode="before")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return str(value).strip()


ModelConnectionOperation = Literal["chat", "embedding"]


class ModelConnectionTestRequest(BaseModel):
    operation: ModelConnectionOperation = "chat"


class ModelConnectionTestSnapshot(BaseModel):
    operation: ModelConnectionOperation
    ok: bool
    model: str | None
    message: str
    code: str | None = None
    retryable: bool = False
    tested_at: datetime


class ModelSettingsSummary(BaseModel):
    source: Literal["user", "system", "none"]
    provider: str
    base_url: str | None
    chat_model: str | None
    embedding_model: str | None
    has_api_key: bool
    api_key_masked: str | None
    can_use_model: bool
    can_use_embedding_model: bool


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
    can_use_embedding_model: bool
    is_default: bool
    is_embedding_default: bool
    last_test_ok: bool | None
    last_test_message: str | None
    last_tested_at: datetime | None
    connection_tests: dict[str, ModelConnectionTestSnapshot] = Field(default_factory=dict)


class ModelSettingsListResponse(BaseModel):
    configs: list[ModelConfigSummary]
    system_summary: ModelSettingsSummary
    default_config_id: int | None
    default_chat_config_id: int | None
    default_embedding_config_id: int | None


class ModelConnectionTestResponse(BaseModel):
    ok: bool
    source: Literal["user", "system", "none"]
    chat_model: str | None
    message: str
    config_id: int | None = None
    operation: ModelConnectionOperation = "chat"
    model: str | None = None
    code: str | None = None
    retryable: bool = False
    tested_at: datetime


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

    def get_embedding_default_for_user(self, user_id: int) -> ModelSetting | None:
        return self.db.scalar(
            select(ModelSetting)
            .where(ModelSetting.user_id == user_id, ModelSetting.is_embedding_default.is_(True))
            .order_by(ModelSetting.updated_at.desc(), ModelSetting.id.desc())
        )

    def list_for_user(self, user_id: int) -> list[ModelSetting]:
        return list(
            self.db.scalars(
                select(ModelSetting)
                .where(ModelSetting.user_id == user_id)
                .order_by(
                    ModelSetting.is_default.desc(),
                    ModelSetting.is_embedding_default.desc(),
                    ModelSetting.updated_at.desc(),
                    ModelSetting.id.desc(),
                )
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

    def unset_embedding_defaults_for_user(self, user_id: int, except_setting_id: int | None = None) -> None:
        statement = update(ModelSetting).where(ModelSetting.user_id == user_id)
        if except_setting_id is not None:
            statement = statement.where(ModelSetting.id != except_setting_id)
        self.db.execute(statement.values(is_embedding_default=False))

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
        execution_runtime: ModelExecutionRuntime | None = None,
    ) -> None:
        self.repository = repository
        self.settings = settings
        self.provider = provider or OpenAICompatibleChatProvider()
        self.execution_runtime = execution_runtime or ModelExecutionRuntime(settings)

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
        default_chat_config = next((config for config in configs if config.is_default), None)
        default_embedding_config = next((config for config in configs if config.is_embedding_default), None)
        return ModelSettingsListResponse(
            configs=configs,
            system_summary=self._system_summary(),
            default_config_id=default_chat_config.id if default_chat_config else None,
            default_chat_config_id=default_chat_config.id if default_chat_config else None,
            default_embedding_config_id=default_embedding_config.id if default_embedding_config else None,
        )

    def save(self, user: User, payload: SaveModelSettingsRequest) -> ModelSettingsSummary:
        if not payload.chat_model:
            raise ModelSettingsValidationError("兼容设置接口必须填写回答模型。")
        existing = self.repository.get_default_for_user(user.id)
        setting = existing or ModelSetting(
            user_id=user.id,
            provider="openai_compatible",
            display_name="默认模型配置",
            is_default=True,
        )
        self._clear_changed_connection_tests(setting, payload)
        self._apply_settings_payload(setting, payload)
        setting.is_default = True
        self.repository.unset_defaults_for_user(user.id, except_setting_id=setting.id)
        setting.is_embedding_default = bool(setting.embedding_model)
        if setting.is_embedding_default:
            self.repository.unset_embedding_defaults_for_user(user.id, except_setting_id=setting.id)
        self._save_and_commit(setting)
        return self.get_summary(user)

    def create_config(self, user: User, payload: SaveModelConfigRequest) -> ModelConfigSummary:
        existing_configs = self.repository.list_for_user(user.id)
        self._ensure_unique_display_name(user.id, payload.display_name)
        has_chat_default = any(candidate.is_default for candidate in existing_configs)
        has_embedding_default = any(candidate.is_embedding_default for candidate in existing_configs)
        setting = ModelSetting(
            user_id=user.id,
            display_name=payload.display_name,
            preset_id=payload.preset_id or None,
            provider="openai_compatible",
            is_default=bool(payload.chat_model) and (payload.make_default or not has_chat_default),
            is_embedding_default=bool(payload.embedding_model)
            and (payload.make_embedding_default or not has_embedding_default),
        )
        self._apply_settings_payload(setting, payload)
        if setting.is_default:
            self.repository.unset_defaults_for_user(user.id)
        if setting.is_embedding_default:
            self.repository.unset_embedding_defaults_for_user(user.id)
        self._save_and_commit(setting)
        return self._config_summary(setting)

    def update_config(self, user: User, config_id: int, payload: UpdateModelConfigRequest) -> ModelConfigSummary:
        setting = self._get_user_setting_or_raise(user, config_id)
        self._clear_changed_connection_tests(setting, payload)
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
            setting.chat_model = payload.chat_model or None
        if payload.embedding_model is not None:
            setting.embedding_model = payload.embedding_model or None
        if payload.api_key:
            setting.api_key_ciphertext = self._encrypt_api_key(payload.api_key)
        if payload.make_default:
            if not setting.chat_model:
                raise ModelSettingsValidationError("该配置没有回答模型，不能设为回答默认。")
            self.repository.unset_defaults_for_user(user.id, except_setting_id=config_id)
            setting.is_default = True
        if payload.make_embedding_default:
            if not setting.embedding_model:
                raise ModelSettingsValidationError("该配置没有向量模型，不能设为向量默认。")
            self.repository.unset_embedding_defaults_for_user(user.id, except_setting_id=config_id)
            setting.is_embedding_default = True
        if not setting.chat_model and not setting.embedding_model:
            raise ModelSettingsValidationError("回答模型和向量模型至少填写一项。")
        if setting.is_default and not setting.chat_model:
            raise ModelSettingsValidationError("回答默认配置不能清空回答模型。")
        if setting.is_embedding_default and not setting.embedding_model:
            raise ModelSettingsValidationError("向量默认配置不能清空向量模型。")
        self._save_and_commit(setting)
        return self._config_summary(setting)

    def delete_config(self, user: User, config_id: int) -> ModelSettingsListResponse:
        setting = self._get_user_setting_or_raise(user, config_id)
        was_default = setting.is_default
        was_embedding_default = setting.is_embedding_default
        try:
            self.repository.delete(setting)
            if was_default:
                remaining = [candidate for candidate in self.repository.list_for_user(user.id) if candidate.id != config_id]
                next_chat = next((candidate for candidate in remaining if candidate.chat_model), None)
                if next_chat:
                    next_chat.is_default = True
                    self.repository.save(next_chat)
            if was_embedding_default:
                remaining = [candidate for candidate in self.repository.list_for_user(user.id) if candidate.id != config_id]
                next_embedding = next((candidate for candidate in remaining if candidate.embedding_model), None)
                if next_embedding:
                    next_embedding.is_embedding_default = True
                    self.repository.save(next_embedding)
            self.repository.commit()
        except Exception:
            self.repository.rollback()
            raise
        return self.list_configs(user)

    def set_default_config(self, user: User, config_id: int) -> ModelSettingsListResponse:
        setting = self._get_user_setting_or_raise(user, config_id)
        if not setting.chat_model:
            raise ModelSettingsValidationError("该配置没有回答模型，不能设为回答默认。")
        setting.is_default = True
        self.repository.unset_defaults_for_user(user.id, except_setting_id=config_id)
        self._save_and_commit(setting)
        return self.list_configs(user)

    def set_embedding_default_config(self, user: User, config_id: int) -> ModelSettingsListResponse:
        setting = self._get_user_setting_or_raise(user, config_id)
        if not setting.embedding_model:
            raise ModelSettingsValidationError("该配置没有向量模型，不能设为向量默认。")
        setting.is_embedding_default = True
        self.repository.unset_embedding_defaults_for_user(user.id, except_setting_id=config_id)
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

    def resolve_embedding_runtime_config(self, user: User) -> RuntimeModelConfig:
        user_setting = self.repository.get_embedding_default_for_user(user.id)
        if user_setting is not None:
            user_runtime = self._embedding_runtime_from_user_setting(user_setting)
            if user_runtime.can_use_model:
                return user_runtime

        system_runtime = self._embedding_runtime_from_system_settings()
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

    def chat_completion_with_timeout(self, user: User, messages: list[dict[str, str]], timeout_seconds: float) -> str:
        runtime = self.resolve_runtime_config(user)
        if not runtime.can_use_model or runtime.base_url is None or runtime.chat_model is None:
            raise ModelNotConfiguredError(MODEL_NOT_CONFIGURED_MESSAGE)
        config = OpenAICompatibleConfig(
            base_url=runtime.base_url,
            api_key=runtime.api_key or LOCAL_PLACEHOLDER_API_KEY,
            chat_model=runtime.chat_model,
        )
        return self.execution_runtime.execute(
            user_id=user.id,
            provider_source=runtime.source,
            model_config_id=runtime.config_id,
            model_name=runtime.chat_model,
            operation="chat",
            call=lambda: self.provider.chat_completion(config=config, messages=messages, timeout_seconds=timeout_seconds),
            timeout_seconds=timeout_seconds,
        )

    def chat_completion(self, user: User, messages: list[dict[str, str]]) -> str:
        return self.chat_completion_with_timeout(
            user,
            messages,
            timeout_seconds=self.settings.model_request_timeout_seconds,
        )

    def chat_completion_stream(self, user: User, messages: list[dict[str, str]]) -> Iterator[str]:
        runtime = self.resolve_runtime_config(user)
        if not runtime.can_use_model or runtime.base_url is None or runtime.chat_model is None:
            raise ModelNotConfiguredError(MODEL_NOT_CONFIGURED_MESSAGE)
        config = OpenAICompatibleConfig(
            base_url=runtime.base_url,
            api_key=runtime.api_key or LOCAL_PLACEHOLDER_API_KEY,
            chat_model=runtime.chat_model,
        )
        return self.execution_runtime.execute_stream(
            user_id=user.id,
            provider_source=runtime.source,
            model_config_id=runtime.config_id,
            model_name=runtime.chat_model,
            call=lambda: self.provider.chat_completion_stream(
                config=config,
                messages=messages,
                timeout_seconds=self.settings.model_request_timeout_seconds,
            ),
            timeout_seconds=self.settings.model_request_timeout_seconds,
        )

    def embedding_vectors(self, user: User, texts: list[str], dimensions: int = 1536) -> list[list[float]]:
        runtime = self.resolve_embedding_runtime_config(user)
        if not runtime.can_use_model or runtime.base_url is None or runtime.embedding_model is None:
            raise ModelNotConfiguredError("当前未配置可用向量模型。")
        config = OpenAICompatibleEmbeddingConfig(
            base_url=runtime.base_url,
            api_key=runtime.api_key or LOCAL_PLACEHOLDER_API_KEY,
            embedding_model=runtime.embedding_model,
        )
        vectors = self.execution_runtime.execute(
            user_id=user.id,
            provider_source=runtime.source,
            model_config_id=runtime.config_id,
            model_name=runtime.embedding_model,
            operation="embedding",
            call=lambda: self.provider.embed_texts(
                config=config,
                texts=texts,
                timeout_seconds=self.settings.model_request_timeout_seconds,
                dimensions=dimensions,
            ),
            timeout_seconds=self.settings.model_request_timeout_seconds,
        )
        if len(vectors) != len(texts) or any(len(vector) != dimensions for vector in vectors):
            raise ModelProviderError("模型服务返回了不匹配的向量维度。")
        return vectors

    def test_connection(
        self,
        user: User,
        operation: ModelConnectionOperation = "chat",
    ) -> ModelConnectionTestResponse:
        runtime = (
            self.resolve_embedding_runtime_config(user)
            if operation == "embedding"
            else self.resolve_runtime_config(user)
        )
        return self._test_runtime(runtime, user_id=user.id, operation=operation)

    def test_config_connection(
        self,
        user: User,
        config_id: int,
        operation: ModelConnectionOperation = "chat",
    ) -> ModelConnectionTestResponse:
        setting = self._get_user_setting_or_raise(user, config_id)
        runtime = (
            self._embedding_runtime_from_user_setting(setting)
            if operation == "embedding"
            else self._runtime_from_user_setting(setting)
        )
        result = self._test_runtime(runtime, user_id=user.id, operation=operation)
        tests = dict(setting.connection_test_json or {})
        tests[operation] = ModelConnectionTestSnapshot(
            operation=operation,
            ok=result.ok,
            model=result.model,
            message=result.message,
            code=result.code,
            retryable=result.retryable,
            tested_at=result.tested_at,
        ).model_dump(mode="json")
        setting.connection_test_json = tests
        if operation == "chat":
            setting.last_test_ok = result.ok
            setting.last_test_message = result.message
            setting.last_tested_at = result.tested_at
        self._save_and_commit(setting)
        return result

    def _test_runtime(
        self,
        runtime: RuntimeModelConfig,
        *,
        user_id: int,
        operation: ModelConnectionOperation,
    ) -> ModelConnectionTestResponse:
        tested_at = datetime.now(UTC)
        model = runtime.embedding_model if operation == "embedding" else runtime.chat_model
        if not runtime.can_use_model or model is None:
            label = "向量模型" if operation == "embedding" else "回答模型"
            return ModelConnectionTestResponse(
                ok=False,
                source=runtime.source,
                chat_model=runtime.chat_model,
                message=f"当前未配置可用{label}。",
                config_id=runtime.config_id,
                operation=operation,
                model=model,
                code="not_configured",
                tested_at=tested_at,
            )

        try:
            with model_execution_scope(ModelExecutionContext(purpose="connection_test")):
                if operation == "embedding":
                    embedding_config = OpenAICompatibleEmbeddingConfig(
                        base_url=runtime.base_url or "",
                        api_key=runtime.api_key or LOCAL_PLACEHOLDER_API_KEY,
                        embedding_model=runtime.embedding_model or "",
                    )
                    self.execution_runtime.execute(
                        user_id=user_id,
                        provider_source=runtime.source,
                        model_config_id=runtime.config_id,
                        model_name=model,
                        operation="embedding",
                        call=lambda: self.provider.embed_texts(
                            config=embedding_config,
                            texts=["EduNova 向量连接测试"],
                            timeout_seconds=self.settings.model_request_timeout_seconds,
                            dimensions=1536,
                        ),
                        timeout_seconds=self.settings.model_request_timeout_seconds,
                        max_attempts=1,
                        bypass_circuit=True,
                    )
                else:
                    chat_config = OpenAICompatibleConfig(
                        base_url=runtime.base_url or "",
                        api_key=runtime.api_key or LOCAL_PLACEHOLDER_API_KEY,
                        chat_model=runtime.chat_model or "",
                    )
                    self.execution_runtime.execute(
                        user_id=user_id,
                        provider_source=runtime.source,
                        model_config_id=runtime.config_id,
                        model_name=model,
                        operation="chat",
                        call=lambda: self.provider.chat_completion(
                            config=chat_config,
                            messages=[
                                {"role": "system", "content": "你是 EduNova 的模型连通性检查器。"},
                                {"role": "user", "content": "请只回复 ok。"},
                            ],
                            timeout_seconds=self.settings.model_request_timeout_seconds,
                        ),
                        timeout_seconds=self.settings.model_request_timeout_seconds,
                        max_attempts=1,
                        bypass_circuit=True,
                    )
        except ModelProviderError as exc:
            return ModelConnectionTestResponse(
                ok=False,
                source=runtime.source,
                chat_model=runtime.chat_model,
                message=str(exc),
                config_id=runtime.config_id,
                operation=operation,
                model=model,
                code=exc.code,
                retryable=exc.retryable,
                tested_at=tested_at,
            )
        except Exception:
            return ModelConnectionTestResponse(
                ok=False,
                source=runtime.source,
                chat_model=runtime.chat_model,
                message="连接测试失败，请稍后重试。",
                config_id=runtime.config_id,
                operation=operation,
                model=model,
                code="internal_error",
                tested_at=tested_at,
            )

        return ModelConnectionTestResponse(
            ok=True,
            source=runtime.source,
            chat_model=runtime.chat_model,
            message="向量模型连接成功。" if operation == "embedding" else "模型连接成功。",
            config_id=runtime.config_id,
            operation=operation,
            model=model,
            tested_at=tested_at,
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

    def _embedding_runtime_from_user_setting(self, setting: ModelSetting) -> RuntimeModelConfig:
        api_key = self._decrypt_api_key(setting.api_key_ciphertext)
        return RuntimeModelConfig(
            source="user",
            provider=self._normalize_provider(setting.provider),
            base_url=setting.base_url,
            api_key=api_key,
            chat_model=setting.chat_model,
            embedding_model=setting.embedding_model,
            can_use_model=self._can_use_embedding_model(
                provider=setting.provider,
                base_url=setting.base_url,
                api_key=api_key,
                embedding_model=setting.embedding_model,
            ),
            config_id=setting.id,
        )

    def _embedding_runtime_from_system_settings(self) -> RuntimeModelConfig:
        api_key = self.settings.system_model_api_key.strip()
        return RuntimeModelConfig(
            source="system",
            provider=self._normalize_provider(self.settings.system_model_provider),
            base_url=self.settings.system_model_base_url.strip() or None,
            api_key=api_key or None,
            chat_model=self.settings.system_chat_model.strip() or None,
            embedding_model=self.settings.system_embedding_model.strip() or None,
            can_use_model=self._can_use_embedding_model(
                provider=self.settings.system_model_provider,
                base_url=self.settings.system_model_base_url,
                api_key=api_key,
                embedding_model=self.settings.system_embedding_model,
            ),
        )

    def _config_summary(self, setting: ModelSetting) -> ModelConfigSummary:
        runtime = self._runtime_from_user_setting(setting)
        embedding_runtime = self._embedding_runtime_from_user_setting(setting)
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
            can_use_embedding_model=embedding_runtime.can_use_model,
            is_default=setting.is_default,
            is_embedding_default=setting.is_embedding_default,
            last_test_ok=setting.last_test_ok,
            last_test_message=setting.last_test_message,
            last_tested_at=setting.last_tested_at,
            connection_tests=self._parse_connection_tests(setting.connection_test_json),
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
            can_use_embedding_model=self._can_use_embedding_model(
                provider=runtime.provider,
                base_url=runtime.base_url,
                api_key=runtime.api_key,
                embedding_model=runtime.embedding_model,
            ),
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
            can_use_embedding_model=False,
        )

    def _apply_settings_payload(self, setting: ModelSetting, payload: SaveModelSettingsRequest) -> None:
        setting.provider = self._normalize_provider(payload.provider)
        setting.base_url = payload.base_url
        setting.chat_model = payload.chat_model or None
        setting.embedding_model = payload.embedding_model or None
        if isinstance(payload, SaveModelConfigRequest):
            setting.display_name = payload.display_name
            setting.preset_id = payload.preset_id or None
        if payload.api_key:
            setting.api_key_ciphertext = self._encrypt_api_key(payload.api_key)

    def _clear_changed_connection_tests(
        self,
        setting: ModelSetting,
        payload: SaveModelSettingsRequest | UpdateModelConfigRequest,
    ) -> None:
        current_key = self._decrypt_api_key(setting.api_key_ciphertext)
        shared_changed = (
            (payload.provider is not None and self._normalize_provider(payload.provider) != setting.provider)
            or (payload.base_url is not None and payload.base_url != setting.base_url)
            or (bool(payload.api_key) and payload.api_key != current_key)
        )
        chat_changed = shared_changed or (payload.chat_model is not None and payload.chat_model != setting.chat_model)
        embedding_changed = shared_changed or (
            payload.embedding_model is not None and (payload.embedding_model or None) != setting.embedding_model
        )
        tests = dict(setting.connection_test_json or {})
        if chat_changed:
            tests.pop("chat", None)
            setting.last_test_ok = None
            setting.last_test_message = None
            setting.last_tested_at = None
        if embedding_changed:
            tests.pop("embedding", None)
        setting.connection_test_json = tests

    @staticmethod
    def _parse_connection_tests(raw_tests: dict | None) -> dict[str, ModelConnectionTestSnapshot]:
        parsed: dict[str, ModelConnectionTestSnapshot] = {}
        for operation in ("chat", "embedding"):
            value = (raw_tests or {}).get(operation)
            if not isinstance(value, dict):
                continue
            try:
                parsed[operation] = ModelConnectionTestSnapshot.model_validate(value)
            except ValueError:
                continue
        return parsed

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

    @classmethod
    def _can_use_embedding_model(
        cls,
        provider: str | None,
        base_url: str | None,
        api_key: str | None,
        embedding_model: str | None,
    ) -> bool:
        return (
            cls._normalize_provider(provider or "") == "openai_compatible"
            and cls._is_real_value(base_url)
            and (cls._is_real_api_key(api_key) or cls._allows_empty_api_key(base_url))
            and cls._is_real_value(embedding_model)
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

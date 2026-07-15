from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from io import BytesIO
from typing import Iterator, Literal, Protocol

from cryptography.fernet import Fernet, InvalidToken
from PIL import Image, ImageDraw
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
    NativeWebSearchResult,
)
from backend.app.providers.capabilities import provider_capabilities
from backend.app.providers.retrieval import (
    EmbeddingRequestConfig,
    HttpRerankProvider,
    RerankItem,
    RerankRequestConfig,
    XFYUN_EMBEDDING_DIMENSION,
    XfyunEmbeddingProvider,
)
from backend.app.services.model_execution import (
    ModelExecutionContext,
    ModelExecutionRuntime,
    model_execution_scope,
)


MODEL_NOT_CONFIGURED_MESSAGE = "已找到资料依据，但当前未配置可用模型。"
LOCAL_PLACEHOLDER_API_KEY = "local-dev-key"


def _vision_connection_test_image() -> str:
    image = Image.new("RGB", (512, 192), "white")
    ImageDraw.Draw(image).text((32, 72), "EduNova Vision 32", fill="black")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


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
    def get_rerank_default_for_user(self, user_id: int) -> ModelSetting | None: ...
    def get_vision_default_for_user(self, user_id: int) -> ModelSetting | None: ...
    def list_for_user(self, user_id: int) -> list[ModelSetting]: ...
    def get_by_id_for_user(self, setting_id: int, user_id: int) -> ModelSetting | None: ...
    def save(self, setting: ModelSetting) -> None: ...
    def delete(self, setting: ModelSetting) -> None: ...
    def unset_defaults_for_user(self, user_id: int, except_setting_id: int | None = None) -> None: ...
    def unset_embedding_defaults_for_user(self, user_id: int, except_setting_id: int | None = None) -> None: ...
    def unset_rerank_defaults_for_user(self, user_id: int, except_setting_id: int | None = None) -> None: ...
    def unset_vision_defaults_for_user(self, user_id: int, except_setting_id: int | None = None) -> None: ...
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

    def vision_completion(
        self,
        config: OpenAICompatibleConfig,
        *,
        prompt: str,
        image_data_urls: list[str],
        timeout_seconds: float,
    ) -> str: ...

    def embed_texts(
        self,
        config: OpenAICompatibleEmbeddingConfig,
        texts: list[str],
        timeout_seconds: float,
        dimensions: int | None = None,
    ) -> list[list[float]]: ...

    def native_web_search(
        self,
        config: OpenAICompatibleConfig,
        *,
        query: str,
        timeout_seconds: float,
        native_kind: str,
        deep: bool = False,
        force: bool = False,
    ) -> NativeWebSearchResult: ...


class SaveModelSettingsRequest(BaseModel):
    provider: Literal["openai_compatible"]
    base_url: str = Field(min_length=1, max_length=500)
    api_key: str | None = Field(default=None, max_length=500)
    chat_model: str | None = Field(default=None, max_length=120)
    embedding_provider: Literal["openai_compatible", "xfyun_embedding"] | None = None
    embedding_base_url: str | None = Field(default=None, max_length=500)
    embedding_api_key: str | None = Field(default=None, max_length=500)
    embedding_app_id: str | None = Field(default=None, max_length=500)
    embedding_api_secret: str | None = Field(default=None, max_length=500)
    embedding_model: str | None = Field(default=None, max_length=120)
    embedding_dimension: int | None = Field(default=None, ge=1, le=8192)
    rerank_provider: Literal["siliconflow_rerank", "bailian_rerank", "openai_compatible"] | None = None
    rerank_base_url: str | None = Field(default=None, max_length=500)
    rerank_api_key: str | None = Field(default=None, max_length=500)
    rerank_model: str | None = Field(default=None, max_length=120)
    rerank_workspace_id: str | None = Field(default=None, max_length=120)

    @field_validator(
        "base_url",
        "api_key",
        "chat_model",
        "embedding_base_url",
        "embedding_api_key",
        "embedding_app_id",
        "embedding_api_secret",
        "embedding_model",
        "rerank_base_url",
        "rerank_api_key",
        "rerank_model",
        "rerank_workspace_id",
        mode="before",
    )
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return str(value).strip()

    @model_validator(mode="after")
    def require_at_least_one_model(self) -> SaveModelSettingsRequest:
        if not self.chat_model and not self.embedding_model and not self.rerank_model:
            raise ValueError("回答、向量和重排序模型至少填写一项。")
        return self


class SaveModelConfigRequest(SaveModelSettingsRequest):
    display_name: str = Field(min_length=1, max_length=120)
    preset_id: str | None = Field(default=None, max_length=80)
    embedding_preset_id: str | None = Field(default=None, max_length=80)
    rerank_preset_id: str | None = Field(default=None, max_length=80)
    make_default: bool = False
    make_embedding_default: bool = False
    make_rerank_default: bool = False
    make_vision_default: bool = False

    @field_validator("display_name", "preset_id", "embedding_preset_id", "rerank_preset_id", mode="before")
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
    embedding_provider: Literal["openai_compatible", "xfyun_embedding"] | None = None
    embedding_preset_id: str | None = Field(default=None, max_length=80)
    embedding_base_url: str | None = Field(default=None, max_length=500)
    embedding_api_key: str | None = Field(default=None, max_length=500)
    embedding_app_id: str | None = Field(default=None, max_length=500)
    embedding_api_secret: str | None = Field(default=None, max_length=500)
    embedding_model: str | None = Field(default=None, max_length=120)
    embedding_dimension: int | None = Field(default=None, ge=1, le=8192)
    rerank_provider: Literal["siliconflow_rerank", "bailian_rerank", "openai_compatible"] | None = None
    rerank_preset_id: str | None = Field(default=None, max_length=80)
    rerank_base_url: str | None = Field(default=None, max_length=500)
    rerank_api_key: str | None = Field(default=None, max_length=500)
    rerank_model: str | None = Field(default=None, max_length=120)
    rerank_workspace_id: str | None = Field(default=None, max_length=120)
    make_default: bool | None = None
    make_embedding_default: bool | None = None
    make_rerank_default: bool | None = None
    make_vision_default: bool | None = None

    @field_validator(
        "display_name",
        "preset_id",
        "base_url",
        "api_key",
        "chat_model",
        "embedding_preset_id",
        "embedding_base_url",
        "embedding_api_key",
        "embedding_app_id",
        "embedding_api_secret",
        "embedding_model",
        "rerank_preset_id",
        "rerank_base_url",
        "rerank_api_key",
        "rerank_model",
        "rerank_workspace_id",
        mode="before",
    )
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return str(value).strip()


ModelConnectionOperation = Literal["chat", "embedding", "rerank", "vision"]


class ModelConnectionTestRequest(BaseModel):
    operation: ModelConnectionOperation = "chat"


class EmbeddingReindexRequest(BaseModel):
    config_id: int | None = None


class ModelConnectionTestSnapshot(BaseModel):
    operation: ModelConnectionOperation
    ok: bool
    model: str | None
    message: str
    code: str | None = None
    retryable: bool = False
    tested_at: datetime
    dimension: int | None = None


class ModelSettingsSummary(BaseModel):
    source: Literal["user", "system", "none"]
    provider: str
    base_url: str | None
    chat_model: str | None
    embedding_model: str | None
    embedding_provider: str | None = None
    embedding_base_url: str | None = None
    embedding_dimension: int | None = None
    has_api_key: bool
    api_key_masked: str | None
    has_embedding_api_key: bool = False
    embedding_api_key_masked: str | None = None
    has_embedding_app_id: bool = False
    embedding_app_id_masked: str | None = None
    has_embedding_api_secret: bool = False
    rerank_model: str | None = None
    rerank_provider: str | None = None
    rerank_base_url: str | None = None
    rerank_workspace_id: str | None = None
    has_rerank_api_key: bool = False
    rerank_api_key_masked: str | None = None
    can_use_model: bool
    can_use_embedding_model: bool
    can_use_rerank_model: bool = False


class ModelConfigSummary(BaseModel):
    id: int
    source: Literal["user"] = "user"
    display_name: str
    preset_id: str | None
    provider: str
    base_url: str | None
    chat_model: str | None
    embedding_model: str | None
    embedding_provider: str | None = None
    embedding_preset_id: str | None = None
    embedding_base_url: str | None = None
    embedding_dimension: int | None = None
    has_api_key: bool
    api_key_masked: str | None
    has_embedding_api_key: bool = False
    embedding_api_key_masked: str | None = None
    has_embedding_app_id: bool = False
    embedding_app_id_masked: str | None = None
    has_embedding_api_secret: bool = False
    rerank_model: str | None = None
    rerank_provider: str | None = None
    rerank_preset_id: str | None = None
    rerank_base_url: str | None = None
    rerank_workspace_id: str | None = None
    has_rerank_api_key: bool = False
    rerank_api_key_masked: str | None = None
    can_use_model: bool
    can_use_embedding_model: bool
    can_use_rerank_model: bool = False
    is_default: bool
    is_embedding_default: bool
    is_rerank_default: bool = False
    is_vision_default: bool = False
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
    default_rerank_config_id: int | None = None
    default_vision_config_id: int | None = None


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
    dimension: int | None = None


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
    preset_id: str | None = None
    app_id: str | None = None
    api_secret: str | None = None
    dimensions: int | None = None
    workspace_id: str | None = None

    @property
    def profile_hash(self) -> str:
        raw = "|".join(
            [self.provider, self.base_url or "", self.embedding_model or self.chat_model or "", str(self.dimensions or "")]
        )
        return sha256(raw.encode("utf-8")).hexdigest()


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

    def get_rerank_default_for_user(self, user_id: int) -> ModelSetting | None:
        return self.db.scalar(
            select(ModelSetting)
            .where(ModelSetting.user_id == user_id, ModelSetting.is_rerank_default.is_(True))
            .order_by(ModelSetting.updated_at.desc(), ModelSetting.id.desc())
        )

    def get_vision_default_for_user(self, user_id: int) -> ModelSetting | None:
        return self.db.scalar(
            select(ModelSetting)
            .where(ModelSetting.user_id == user_id, ModelSetting.is_vision_default.is_(True))
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
                    ModelSetting.is_rerank_default.desc(),
                    ModelSetting.is_vision_default.desc(),
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

    def unset_rerank_defaults_for_user(self, user_id: int, except_setting_id: int | None = None) -> None:
        statement = update(ModelSetting).where(ModelSetting.user_id == user_id)
        if except_setting_id is not None:
            statement = statement.where(ModelSetting.id != except_setting_id)
        self.db.execute(statement.values(is_rerank_default=False))

    def unset_vision_defaults_for_user(self, user_id: int, except_setting_id: int | None = None) -> None:
        statement = update(ModelSetting).where(ModelSetting.user_id == user_id)
        if except_setting_id is not None:
            statement = statement.where(ModelSetting.id != except_setting_id)
        self.db.execute(statement.values(is_vision_default=False))

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
        xfyun_embedding_provider: XfyunEmbeddingProvider | None = None,
        rerank_provider: HttpRerankProvider | None = None,
    ) -> None:
        self.repository = repository
        self.settings = settings
        self.provider = provider or OpenAICompatibleChatProvider()
        self.xfyun_embedding_provider = xfyun_embedding_provider or XfyunEmbeddingProvider()
        self.rerank_provider = rerank_provider or HttpRerankProvider()
        self.execution_runtime = execution_runtime or ModelExecutionRuntime(settings)

    def get_summary(self, user: User) -> ModelSettingsSummary:
        chat_runtime = self.resolve_runtime_config(user)
        embedding_runtime = self.resolve_embedding_runtime_config(user)
        rerank_runtime = self.resolve_rerank_runtime_config(user)
        if chat_runtime.source != "none" or embedding_runtime.source != "none" or rerank_runtime.source != "none":
            source = chat_runtime.source if chat_runtime.source != "none" else embedding_runtime.source
            if source == "none":
                source = rerank_runtime.source
            return self._summary_from_runtimes(chat_runtime, embedding_runtime, rerank_runtime, source=source)
        return self._empty_summary()

    def list_configs(self, user: User) -> ModelSettingsListResponse:
        configs = [self._config_summary(setting) for setting in self.repository.list_for_user(user.id)]
        default_chat_config = next((config for config in configs if config.is_default), None)
        default_embedding_config = next((config for config in configs if config.is_embedding_default), None)
        default_rerank_config = next((config for config in configs if config.is_rerank_default), None)
        default_vision_config = next((config for config in configs if config.is_vision_default), None)
        return ModelSettingsListResponse(
            configs=configs,
            system_summary=self._system_summary(),
            default_config_id=default_chat_config.id if default_chat_config else None,
            default_chat_config_id=default_chat_config.id if default_chat_config else None,
            default_embedding_config_id=default_embedding_config.id if default_embedding_config else None,
            default_rerank_config_id=default_rerank_config.id if default_rerank_config else None,
            default_vision_config_id=default_vision_config.id if default_vision_config else None,
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
        setting.is_rerank_default = bool(setting.rerank_model)
        if setting.is_rerank_default:
            self.repository.unset_rerank_defaults_for_user(user.id, except_setting_id=setting.id)
        self._save_and_commit(setting)
        return self.get_summary(user)

    def create_config(self, user: User, payload: SaveModelConfigRequest) -> ModelConfigSummary:
        existing_configs = self.repository.list_for_user(user.id)
        self._ensure_unique_display_name(user.id, payload.display_name)
        has_chat_default = any(candidate.is_default for candidate in existing_configs)
        has_embedding_default = any(candidate.is_embedding_default for candidate in existing_configs)
        has_rerank_default = any(candidate.is_rerank_default for candidate in existing_configs)
        capabilities = provider_capabilities(
            preset_id=payload.preset_id,
            base_url=payload.base_url,
        )
        setting = ModelSetting(
            user_id=user.id,
            display_name=payload.display_name,
            preset_id=payload.preset_id or None,
            provider="openai_compatible",
            is_default=bool(payload.chat_model)
            and (payload.make_default or (not has_chat_default and not capabilities.supports_image_input)),
            is_embedding_default=bool(payload.embedding_model)
            and (payload.make_embedding_default or not has_embedding_default),
            is_rerank_default=bool(payload.rerank_model)
            and (payload.make_rerank_default or not has_rerank_default),
            is_vision_default=bool(payload.chat_model) and payload.make_vision_default,
        )
        self._apply_settings_payload(setting, payload)
        if setting.is_vision_default and not capabilities.supports_image_input:
            raise ModelSettingsValidationError("该配置未声明图片理解能力。")
        if setting.is_default:
            self.repository.unset_defaults_for_user(user.id)
        if setting.is_embedding_default:
            self.repository.unset_embedding_defaults_for_user(user.id)
        if setting.is_rerank_default:
            self.repository.unset_rerank_defaults_for_user(user.id)
        if setting.is_vision_default:
            self.repository.unset_vision_defaults_for_user(user.id)
        self._save_and_commit(setting)
        return self._config_summary(setting)

    def update_config(self, user: User, config_id: int, payload: UpdateModelConfigRequest) -> ModelConfigSummary:
        setting = self._get_user_setting_or_raise(user, config_id)
        chat_connection_changed = (
            (
                payload.provider is not None
                and self._normalize_provider(payload.provider) != self._normalize_provider(setting.provider)
            )
            or (payload.base_url is not None and payload.base_url != setting.base_url)
        )
        embedding_connection_changed = (
            (
                payload.embedding_provider is not None
                and self._normalize_provider(payload.embedding_provider)
                != self._normalize_provider(setting.embedding_provider or setting.provider)
            )
            or (
                payload.embedding_base_url is not None
                and (payload.embedding_base_url or None) != setting.embedding_base_url
            )
        )
        rerank_connection_changed = (
            (payload.rerank_provider is not None and payload.rerank_provider != setting.rerank_provider)
            or (payload.rerank_base_url is not None and (payload.rerank_base_url or None) != setting.rerank_base_url)
        )
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
        if payload.embedding_provider is not None:
            setting.embedding_provider = self._normalize_provider(payload.embedding_provider)
        if payload.embedding_preset_id is not None:
            setting.embedding_preset_id = payload.embedding_preset_id or None
        if payload.embedding_base_url is not None:
            setting.embedding_base_url = payload.embedding_base_url or None
        if payload.embedding_model is not None:
            setting.embedding_model = payload.embedding_model or None
        if payload.embedding_dimension is not None:
            setting.embedding_dimension = payload.embedding_dimension
        if payload.rerank_provider is not None:
            setting.rerank_provider = payload.rerank_provider
        if payload.rerank_preset_id is not None:
            setting.rerank_preset_id = payload.rerank_preset_id or None
        if payload.rerank_base_url is not None:
            setting.rerank_base_url = payload.rerank_base_url or None
        if payload.rerank_model is not None:
            setting.rerank_model = payload.rerank_model or None
        if payload.rerank_workspace_id is not None:
            setting.rerank_workspace_id = payload.rerank_workspace_id or None
        if payload.api_key:
            setting.api_key_ciphertext = self._encrypt_api_key(payload.api_key)
        elif chat_connection_changed:
            setting.api_key_ciphertext = None
        if payload.embedding_api_key:
            setting.embedding_api_key_ciphertext = self._encrypt_api_key(payload.embedding_api_key)
        elif embedding_connection_changed:
            setting.embedding_api_key_ciphertext = None
        if payload.embedding_app_id:
            setting.embedding_app_id_ciphertext = self._encrypt_api_key(payload.embedding_app_id)
        elif embedding_connection_changed:
            setting.embedding_app_id_ciphertext = None
        if payload.embedding_api_secret:
            setting.embedding_api_secret_ciphertext = self._encrypt_api_key(payload.embedding_api_secret)
        elif embedding_connection_changed:
            setting.embedding_api_secret_ciphertext = None
        if payload.rerank_api_key:
            setting.rerank_api_key_ciphertext = self._encrypt_api_key(payload.rerank_api_key)
        elif rerank_connection_changed:
            setting.rerank_api_key_ciphertext = None
        if setting.embedding_model:
            setting.embedding_provider = setting.embedding_provider or setting.provider
            setting.embedding_preset_id = setting.embedding_preset_id or setting.preset_id
            setting.embedding_base_url = setting.embedding_base_url or setting.base_url
            connections_match = (
                self._normalize_provider(setting.embedding_provider)
                == self._normalize_provider(setting.provider)
                and setting.embedding_base_url == setting.base_url
            )
            if setting.embedding_api_key_ciphertext is None and connections_match:
                setting.embedding_api_key_ciphertext = setting.api_key_ciphertext
        elif payload.embedding_model is not None:
            setting.embedding_provider = None
            setting.embedding_preset_id = None
            setting.embedding_base_url = None
            setting.embedding_api_key_ciphertext = None
            setting.embedding_app_id_ciphertext = None
            setting.embedding_api_secret_ciphertext = None
            setting.embedding_dimension = None
        if payload.rerank_model is not None and not setting.rerank_model:
            setting.rerank_provider = None
            setting.rerank_preset_id = None
            setting.rerank_base_url = None
            setting.rerank_api_key_ciphertext = None
            setting.rerank_workspace_id = None
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
        if payload.make_rerank_default:
            if not setting.rerank_model:
                raise ModelSettingsValidationError("该配置没有重排序模型，不能设为重排序默认。")
            self.repository.unset_rerank_defaults_for_user(user.id, except_setting_id=config_id)
            setting.is_rerank_default = True
        if payload.make_vision_default:
            if not setting.chat_model:
                raise ModelSettingsValidationError("该配置没有模型，不能设为图片理解默认。")
            capabilities = provider_capabilities(preset_id=setting.preset_id, base_url=setting.base_url)
            if not capabilities.supports_image_input:
                raise ModelSettingsValidationError("该配置未声明图片理解能力。")
            self.repository.unset_vision_defaults_for_user(user.id, except_setting_id=config_id)
            setting.is_vision_default = True
        if not setting.chat_model and not setting.embedding_model and not setting.rerank_model:
            raise ModelSettingsValidationError("回答、向量和重排序模型至少填写一项。")
        if setting.is_default and not setting.chat_model:
            raise ModelSettingsValidationError("回答默认配置不能清空回答模型。")
        if setting.is_embedding_default and not setting.embedding_model:
            raise ModelSettingsValidationError("向量默认配置不能清空向量模型。")
        if setting.is_rerank_default and not setting.rerank_model:
            raise ModelSettingsValidationError("重排序默认配置不能清空重排序模型。")
        self._save_and_commit(setting)
        return self._config_summary(setting)

    def delete_config(self, user: User, config_id: int) -> ModelSettingsListResponse:
        setting = self._get_user_setting_or_raise(user, config_id)
        was_default = setting.is_default
        was_embedding_default = setting.is_embedding_default
        was_rerank_default = setting.is_rerank_default
        was_vision_default = setting.is_vision_default
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
            if was_rerank_default:
                remaining = [candidate for candidate in self.repository.list_for_user(user.id) if candidate.id != config_id]
                next_rerank = next((candidate for candidate in remaining if candidate.rerank_model), None)
                if next_rerank:
                    next_rerank.is_rerank_default = True
                    self.repository.save(next_rerank)
            if was_vision_default:
                remaining = [candidate for candidate in self.repository.list_for_user(user.id) if candidate.id != config_id]
                next_vision = next(
                    (
                        candidate
                        for candidate in remaining
                        if candidate.chat_model
                        and provider_capabilities(
                            preset_id=candidate.preset_id,
                            base_url=candidate.base_url,
                        ).supports_image_input
                    ),
                    None,
                )
                if next_vision:
                    next_vision.is_vision_default = True
                    self.repository.save(next_vision)
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

    def set_rerank_default_config(self, user: User, config_id: int) -> ModelSettingsListResponse:
        setting = self._get_user_setting_or_raise(user, config_id)
        if not setting.rerank_model:
            raise ModelSettingsValidationError("该配置没有重排序模型，不能设为重排序默认。")
        setting.is_rerank_default = True
        self.repository.unset_rerank_defaults_for_user(user.id, except_setting_id=config_id)
        self._save_and_commit(setting)
        return self.list_configs(user)

    def set_vision_default_config(self, user: User, config_id: int) -> ModelSettingsListResponse:
        setting = self._get_user_setting_or_raise(user, config_id)
        if not setting.chat_model:
            raise ModelSettingsValidationError("该配置没有模型，不能设为图片理解默认。")
        capabilities = provider_capabilities(preset_id=setting.preset_id, base_url=setting.base_url)
        if not capabilities.supports_image_input:
            raise ModelSettingsValidationError("该配置未声明图片理解能力。")
        setting.is_vision_default = True
        self.repository.unset_vision_defaults_for_user(user.id, except_setting_id=config_id)
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

    def resolve_rerank_runtime_config(self, user: User) -> RuntimeModelConfig:
        get_default = getattr(self.repository, "get_rerank_default_for_user", None)
        user_setting = get_default(user.id) if callable(get_default) else None
        if user_setting is not None:
            runtime = self._rerank_runtime_from_user_setting(user_setting)
            if runtime.can_use_model:
                return runtime
        runtime = self._rerank_runtime_from_system_settings()
        if runtime.can_use_model:
            return runtime
        return RuntimeModelConfig(
            source="none",
            provider="openai_compatible",
            base_url=None,
            api_key=None,
            chat_model=None,
            embedding_model=None,
            can_use_model=False,
        )

    def resolve_vision_runtime_config(self, user: User) -> RuntimeModelConfig:
        setting = self.repository.get_vision_default_for_user(user.id)
        if setting is None:
            return RuntimeModelConfig(
                source="none",
                provider="openai_compatible",
                base_url=None,
                api_key=None,
                chat_model=None,
                embedding_model=None,
                can_use_model=False,
            )
        runtime = self._runtime_from_user_setting(setting)
        capabilities = provider_capabilities(preset_id=setting.preset_id, base_url=setting.base_url)
        if not capabilities.supports_image_input:
            return RuntimeModelConfig(
                source="none",
                provider="openai_compatible",
                base_url=None,
                api_key=None,
                chat_model=None,
                embedding_model=None,
                can_use_model=False,
            )
        return runtime

    def vision_completion(self, user: User, *, prompt: str, image_data_urls: list[str]) -> str:
        runtime = self.resolve_vision_runtime_config(user)
        if not runtime.can_use_model or runtime.base_url is None or runtime.chat_model is None:
            raise ModelNotConfiguredError("当前未配置可用图片理解模型。")
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
            operation="vision",
            call=lambda: self.provider.vision_completion(
                config,
                prompt=prompt,
                image_data_urls=image_data_urls[:3],
                timeout_seconds=self.settings.model_request_timeout_seconds,
            ),
            timeout_seconds=self.settings.model_request_timeout_seconds,
        )

    def chat_completion_with_timeout(
        self,
        user: User,
        messages: list[dict[str, str]],
        timeout_seconds: float,
        thinking_type: str = "disabled",
    ) -> str:
        runtime = self.resolve_runtime_config(user)
        if not runtime.can_use_model or runtime.base_url is None or runtime.chat_model is None:
            raise ModelNotConfiguredError(MODEL_NOT_CONFIGURED_MESSAGE)
        config = OpenAICompatibleConfig(
            base_url=runtime.base_url,
            api_key=runtime.api_key or LOCAL_PLACEHOLDER_API_KEY,
            chat_model=runtime.chat_model,
            thinking_type=thinking_type if runtime.preset_id == "spark" else None,
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

    def chat_completion(self, user: User, messages: list[dict[str, str]], thinking_type: str = "disabled") -> str:
        return self.chat_completion_with_timeout(
            user,
            messages,
            timeout_seconds=self.settings.model_request_timeout_seconds,
            thinking_type=thinking_type,
        )

    def chat_completion_stream(
        self,
        user: User,
        messages: list[dict[str, str]],
        thinking_type: str = "disabled",
    ) -> Iterator[str]:
        runtime = self.resolve_runtime_config(user)
        if not runtime.can_use_model or runtime.base_url is None or runtime.chat_model is None:
            raise ModelNotConfiguredError(MODEL_NOT_CONFIGURED_MESSAGE)
        config = OpenAICompatibleConfig(
            base_url=runtime.base_url,
            api_key=runtime.api_key or LOCAL_PLACEHOLDER_API_KEY,
            chat_model=runtime.chat_model,
            thinking_type=thinking_type if runtime.preset_id == "spark" else None,
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

    def native_web_search(
        self,
        user: User,
        query: str,
        *,
        reasoning_mode: str = "auto",
        force: bool = False,
    ) -> NativeWebSearchResult:
        runtime = self.resolve_runtime_config(user)
        if not runtime.can_use_model or runtime.base_url is None or runtime.chat_model is None:
            return NativeWebSearchResult([], "none", "当前未配置可用模型。")
        capabilities = provider_capabilities(preset_id=runtime.preset_id, base_url=runtime.base_url)
        if capabilities.native_search == "none":
            return NativeWebSearchResult([], "none", "当前模型不提供厂商原生联网搜索。")
        config = OpenAICompatibleConfig(
            base_url=runtime.base_url,
            api_key=runtime.api_key or LOCAL_PLACEHOLDER_API_KEY,
            chat_model=runtime.chat_model,
            thinking_type=("enabled" if reasoning_mode == "deep" else "auto")
            if capabilities.supports_thinking_control
            else None,
        )
        return self.execution_runtime.execute(
            user_id=user.id,
            provider_source=runtime.source,
            model_config_id=runtime.config_id,
            model_name=runtime.chat_model,
            operation="web_search",
            call=lambda: self.provider.native_web_search(
                config,
                query=query,
                timeout_seconds=self.settings.model_request_timeout_seconds,
                native_kind=capabilities.native_search,
                deep=reasoning_mode == "deep",
                force=force,
            ),
            timeout_seconds=self.settings.model_request_timeout_seconds,
        )

    def embedding_vectors(
        self,
        user: User,
        texts: list[str],
        dimensions: int | None = None,
        *,
        input_type: Literal["document", "query"] = "document",
    ) -> list[list[float]]:
        runtime = self.resolve_embedding_runtime_config(user)
        if not runtime.can_use_model or runtime.base_url is None or runtime.embedding_model is None:
            raise ModelNotConfiguredError("当前未配置可用向量模型。")
        requested_dimensions = dimensions or runtime.dimensions
        def call_provider() -> list[list[float]]:
            if runtime.provider == "xfyun_embedding":
                config = EmbeddingRequestConfig(
                    provider=runtime.provider,
                    base_url=runtime.base_url or "",
                    api_key=runtime.api_key or "",
                    model=runtime.embedding_model or "llm-embedding",
                    dimensions=XFYUN_EMBEDDING_DIMENSION,
                    app_id=runtime.app_id,
                    api_secret=runtime.api_secret,
                )
                if input_type == "query":
                    return [self.xfyun_embedding_provider.embed_query(config, text, self.settings.model_request_timeout_seconds) for text in texts]
                return self.xfyun_embedding_provider.embed_documents(config, texts, self.settings.model_request_timeout_seconds)
            config = OpenAICompatibleEmbeddingConfig(
                base_url=runtime.base_url or "",
                api_key=runtime.api_key or LOCAL_PLACEHOLDER_API_KEY,
                embedding_model=runtime.embedding_model or "",
            )
            return self.provider.embed_texts(
                config=config,
                texts=texts,
                timeout_seconds=self.settings.model_request_timeout_seconds,
                dimensions=requested_dimensions,
            )
        vectors = self.execution_runtime.execute(
            user_id=user.id,
            provider_source=runtime.source,
            model_config_id=runtime.config_id,
            model_name=runtime.embedding_model,
            operation="embedding",
            call=call_provider,
            timeout_seconds=self.settings.model_request_timeout_seconds,
        )
        actual_dimensions = {len(vector) for vector in vectors}
        if len(vectors) != len(texts) or len(actual_dimensions) != 1 or 0 in actual_dimensions:
            raise ModelProviderError("模型服务返回了不匹配的向量维度。")
        if requested_dimensions is not None and actual_dimensions != {requested_dimensions}:
            raise ModelProviderError("模型服务返回了不匹配的向量维度。")
        return vectors

    def rerank_documents(
        self,
        user: User,
        query: str,
        documents: list[str],
        top_n: int = 5,
    ) -> list[RerankItem]:
        runtime = self.resolve_rerank_runtime_config(user)
        if not runtime.can_use_model or runtime.base_url is None or runtime.embedding_model is None:
            raise ModelNotConfiguredError("当前未配置可用重排序模型。")
        config = RerankRequestConfig(
            provider=runtime.provider,
            base_url=runtime.base_url,
            api_key=runtime.api_key or "",
            model=runtime.embedding_model,
            workspace_id=runtime.workspace_id,
        )
        return self.execution_runtime.execute(
            user_id=user.id,
            provider_source=runtime.source,
            model_config_id=runtime.config_id,
            model_name=runtime.embedding_model,
            operation="rerank",
            call=lambda: self.rerank_provider.rerank(
                config,
                query,
                documents[:20],
                max(1, min(top_n, 20)),
                self.settings.model_request_timeout_seconds,
            ),
            timeout_seconds=self.settings.model_request_timeout_seconds,
        )

    def test_connection(
        self,
        user: User,
        operation: ModelConnectionOperation = "chat",
    ) -> ModelConnectionTestResponse:
        runtime = self._runtime_for_operation(user, operation)
        return self._test_runtime(runtime, user_id=user.id, operation=operation)

    def test_config_connection(
        self,
        user: User,
        config_id: int,
        operation: ModelConnectionOperation = "chat",
    ) -> ModelConnectionTestResponse:
        setting = self._get_user_setting_or_raise(user, config_id)
        runtime = self._runtime_for_setting(setting, operation)
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
            dimension=result.dimension,
        ).model_dump(mode="json")
        setting.connection_test_json = tests
        if operation == "chat":
            setting.last_test_ok = result.ok
            setting.last_test_message = result.message
            setting.last_tested_at = result.tested_at
        elif operation == "embedding" and result.ok and result.dimension:
            setting.embedding_dimension = result.dimension
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
        model = runtime.chat_model if operation in {"chat", "vision"} else runtime.embedding_model
        if not runtime.can_use_model or model is None:
            label = {
                "chat": "回答模型",
                "embedding": "向量模型",
                "rerank": "重排序模型",
                "vision": "图片理解模型",
            }[operation]
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
            actual_dimension: int | None = None
            with model_execution_scope(ModelExecutionContext(purpose="connection_test")):
                if operation == "embedding":
                    def test_embedding() -> list[list[float]]:
                        if runtime.provider == "xfyun_embedding":
                            config = EmbeddingRequestConfig(
                                provider=runtime.provider,
                                base_url=runtime.base_url or "",
                                api_key=runtime.api_key or "",
                                model=runtime.embedding_model or "llm-embedding",
                                dimensions=XFYUN_EMBEDDING_DIMENSION,
                                app_id=runtime.app_id,
                                api_secret=runtime.api_secret,
                            )
                            return self.xfyun_embedding_provider.embed_documents(
                                config,
                                ["EduNova 向量连接测试"],
                                self.settings.model_request_timeout_seconds,
                            )
                        embedding_config = OpenAICompatibleEmbeddingConfig(
                            base_url=runtime.base_url or "",
                            api_key=runtime.api_key or LOCAL_PLACEHOLDER_API_KEY,
                            embedding_model=runtime.embedding_model or "",
                        )
                        return self.provider.embed_texts(
                            config=embedding_config,
                            texts=["EduNova 向量连接测试"],
                            timeout_seconds=self.settings.model_request_timeout_seconds,
                            dimensions=runtime.dimensions,
                        )
                    vectors = self.execution_runtime.execute(
                        user_id=user_id,
                        provider_source=runtime.source,
                        model_config_id=runtime.config_id,
                        model_name=model,
                        operation="embedding",
                        call=test_embedding,
                        timeout_seconds=self.settings.model_request_timeout_seconds,
                        max_attempts=1,
                        bypass_circuit=True,
                    )
                    actual_dimension = len(vectors[0]) if vectors and vectors[0] else None
                elif operation == "rerank":
                    rerank_config = RerankRequestConfig(
                        provider=runtime.provider,
                        base_url=runtime.base_url or "",
                        api_key=runtime.api_key or "",
                        model=runtime.embedding_model or "",
                        workspace_id=runtime.workspace_id,
                    )
                    self.execution_runtime.execute(
                        user_id=user_id,
                        provider_source=runtime.source,
                        model_config_id=runtime.config_id,
                        model_name=model,
                        operation="rerank",
                        call=lambda: self.rerank_provider.rerank(
                            rerank_config,
                            "机器学习",
                            ["机器学习通过数据学习规律。", "天气晴朗。"],
                            1,
                            self.settings.model_request_timeout_seconds,
                        ),
                        timeout_seconds=self.settings.model_request_timeout_seconds,
                        max_attempts=1,
                        bypass_circuit=True,
                    )
                elif operation == "vision":
                    capabilities = provider_capabilities(preset_id=runtime.preset_id, base_url=runtime.base_url)
                    if not capabilities.supports_image_input:
                        raise ModelProviderError("该配置未声明图片理解能力。", code="not_configured")
                    visual_config = OpenAICompatibleConfig(
                        base_url=runtime.base_url or "",
                        api_key=runtime.api_key or LOCAL_PLACEHOLDER_API_KEY,
                        chat_model=runtime.chat_model or "",
                    )
                    self.execution_runtime.execute(
                        user_id=user_id,
                        provider_source=runtime.source,
                        model_config_id=runtime.config_id,
                        model_name=model,
                        operation="vision",
                        call=lambda: self.provider.vision_completion(
                            visual_config,
                            prompt="请读取图片中的文字，并简短回复。",
                            image_data_urls=[_vision_connection_test_image()],
                            timeout_seconds=self.settings.model_request_timeout_seconds,
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
                        thinking_type="disabled" if runtime.preset_id == "spark" else None,
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
                message="连接验证失败，请稍后重试。",
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
            message=(
                "向量服务连接正常。"
                if operation == "embedding"
                else "图片理解服务连接正常。"
                if operation == "vision"
                else "AI 服务连接正常。"
            ),
            config_id=runtime.config_id,
            operation=operation,
            model=model,
            tested_at=tested_at,
            dimension=actual_dimension,
        )

    def _runtime_for_operation(self, user: User, operation: ModelConnectionOperation) -> RuntimeModelConfig:
        if operation == "embedding":
            return self.resolve_embedding_runtime_config(user)
        if operation == "rerank":
            return self.resolve_rerank_runtime_config(user)
        if operation == "vision":
            return self.resolve_vision_runtime_config(user)
        return self.resolve_runtime_config(user)

    def _runtime_for_setting(self, setting: ModelSetting, operation: ModelConnectionOperation) -> RuntimeModelConfig:
        if operation == "embedding":
            return self._embedding_runtime_from_user_setting(setting)
        if operation == "rerank":
            return self._rerank_runtime_from_user_setting(setting)
        runtime = self._runtime_from_user_setting(setting)
        if operation == "vision":
            capabilities = provider_capabilities(preset_id=setting.preset_id, base_url=setting.base_url)
            if not capabilities.supports_image_input:
                return RuntimeModelConfig(
                    source=runtime.source,
                    provider=runtime.provider,
                    base_url=runtime.base_url,
                    api_key=runtime.api_key,
                    chat_model=runtime.chat_model,
                    embedding_model=runtime.embedding_model,
                    can_use_model=False,
                    config_id=runtime.config_id,
                    preset_id=runtime.preset_id,
                )
        return runtime

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
            preset_id=setting.preset_id,
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
            preset_id="spark" if "spark-api-open.xf-yun.com" in self.settings.system_model_base_url else None,
        )

    def _embedding_runtime_from_user_setting(self, setting: ModelSetting) -> RuntimeModelConfig:
        uses_separate_connection = bool(setting.embedding_base_url or setting.embedding_provider)
        provider = setting.embedding_provider or setting.provider
        base_url = setting.embedding_base_url or setting.base_url
        api_key = self._decrypt_api_key(
            setting.embedding_api_key_ciphertext
            if uses_separate_connection
            else setting.api_key_ciphertext
        )
        app_id = self._decrypt_api_key(setting.embedding_app_id_ciphertext)
        api_secret = self._decrypt_api_key(setting.embedding_api_secret_ciphertext)
        return RuntimeModelConfig(
            source="user",
            provider=self._normalize_provider(provider),
            base_url=base_url,
            api_key=api_key,
            chat_model=None,
            embedding_model=setting.embedding_model,
            can_use_model=self._can_use_embedding_model(
                provider=provider,
                base_url=base_url,
                api_key=api_key,
                embedding_model=setting.embedding_model,
                app_id=app_id,
                api_secret=api_secret,
            ),
            config_id=setting.id,
            preset_id=setting.embedding_preset_id,
            app_id=app_id,
            api_secret=api_secret,
            dimensions=setting.embedding_dimension or (XFYUN_EMBEDDING_DIMENSION if provider == "xfyun_embedding" else None),
        )

    def _embedding_runtime_from_system_settings(self) -> RuntimeModelConfig:
        has_separate_connection = bool(self.settings.system_embedding_base_url.strip())
        provider = self.settings.system_embedding_provider.strip() or self.settings.system_model_provider
        base_url = self.settings.system_embedding_base_url.strip() or self.settings.system_model_base_url.strip()
        api_key = (
            self.settings.system_embedding_api_key.strip()
            if has_separate_connection
            else self.settings.system_model_api_key.strip()
        )
        app_id = self.settings.system_embedding_app_id.strip() or None
        api_secret = self.settings.system_embedding_api_secret.strip() or None
        return RuntimeModelConfig(
            source="system",
            provider=self._normalize_provider(provider),
            base_url=base_url or None,
            api_key=api_key or None,
            chat_model=None,
            embedding_model=self.settings.system_embedding_model.strip() or None,
            can_use_model=self._can_use_embedding_model(
                provider=provider,
                base_url=base_url,
                api_key=api_key,
                embedding_model=self.settings.system_embedding_model,
                app_id=app_id,
                api_secret=api_secret,
            ),
            app_id=app_id,
            api_secret=api_secret,
            dimensions=(
                XFYUN_EMBEDDING_DIMENSION
                if self._normalize_provider(provider) == "xfyun_embedding"
                else self.settings.system_embedding_dimension
            ),
        )

    def _rerank_runtime_from_user_setting(self, setting: ModelSetting) -> RuntimeModelConfig:
        api_key = self._decrypt_api_key(setting.rerank_api_key_ciphertext)
        return RuntimeModelConfig(
            source="user",
            provider=setting.rerank_provider or "openai_compatible",
            base_url=setting.rerank_base_url,
            api_key=api_key,
            chat_model=None,
            embedding_model=setting.rerank_model,
            can_use_model=self._can_use_rerank_model(
                setting.rerank_provider,
                setting.rerank_base_url,
                api_key,
                setting.rerank_model,
                setting.rerank_workspace_id,
            ),
            config_id=setting.id,
            preset_id=setting.rerank_preset_id,
            workspace_id=setting.rerank_workspace_id,
        )

    def _rerank_runtime_from_system_settings(self) -> RuntimeModelConfig:
        provider = self.settings.system_rerank_provider.strip()
        base_url = self.settings.system_rerank_base_url.strip() or None
        api_key = self.settings.system_rerank_api_key.strip() or None
        model = self.settings.system_rerank_model.strip() or None
        workspace_id = self.settings.system_rerank_workspace_id.strip() or None
        return RuntimeModelConfig(
            source="system",
            provider=provider or "openai_compatible",
            base_url=base_url,
            api_key=api_key,
            chat_model=None,
            embedding_model=model,
            can_use_model=self._can_use_rerank_model(provider, base_url, api_key, model, workspace_id),
            workspace_id=workspace_id,
        )

    def _config_summary(self, setting: ModelSetting) -> ModelConfigSummary:
        runtime = self._runtime_from_user_setting(setting)
        embedding_runtime = self._embedding_runtime_from_user_setting(setting)
        rerank_runtime = self._rerank_runtime_from_user_setting(setting)
        has_embedding = bool(setting.embedding_model)
        has_rerank = bool(setting.rerank_model)
        return ModelConfigSummary(
            id=setting.id,
            display_name=setting.display_name,
            preset_id=setting.preset_id,
            provider=runtime.provider,
            base_url=runtime.base_url,
            chat_model=runtime.chat_model,
            embedding_model=runtime.embedding_model,
            embedding_provider=embedding_runtime.provider if has_embedding else None,
            embedding_preset_id=setting.embedding_preset_id if has_embedding else None,
            embedding_base_url=embedding_runtime.base_url if has_embedding else None,
            embedding_dimension=embedding_runtime.dimensions if has_embedding else None,
            has_api_key=bool(runtime.api_key),
            api_key_masked=self._mask_api_key(runtime.api_key),
            has_embedding_api_key=has_embedding and bool(embedding_runtime.api_key),
            embedding_api_key_masked=self._mask_api_key(embedding_runtime.api_key) if has_embedding else None,
            has_embedding_app_id=has_embedding and bool(embedding_runtime.app_id),
            embedding_app_id_masked=self._mask_api_key(embedding_runtime.app_id) if has_embedding else None,
            has_embedding_api_secret=has_embedding and bool(embedding_runtime.api_secret),
            rerank_model=rerank_runtime.embedding_model if has_rerank else None,
            rerank_provider=rerank_runtime.provider if has_rerank else None,
            rerank_preset_id=setting.rerank_preset_id if has_rerank else None,
            rerank_base_url=rerank_runtime.base_url if has_rerank else None,
            rerank_workspace_id=rerank_runtime.workspace_id if has_rerank else None,
            has_rerank_api_key=has_rerank and bool(rerank_runtime.api_key),
            rerank_api_key_masked=self._mask_api_key(rerank_runtime.api_key) if has_rerank else None,
            can_use_model=runtime.can_use_model,
            can_use_embedding_model=embedding_runtime.can_use_model,
            can_use_rerank_model=rerank_runtime.can_use_model,
            is_default=setting.is_default,
            is_embedding_default=setting.is_embedding_default,
            is_rerank_default=setting.is_rerank_default,
            is_vision_default=bool(getattr(setting, "is_vision_default", False)),
            last_test_ok=setting.last_test_ok,
            last_test_message=setting.last_test_message,
            last_tested_at=setting.last_tested_at,
            connection_tests=self._parse_connection_tests(setting.connection_test_json),
        )

    def _summary_from_runtimes(
        self,
        runtime: RuntimeModelConfig,
        embedding_runtime: RuntimeModelConfig,
        rerank_runtime: RuntimeModelConfig,
        source: Literal["user", "system"],
    ) -> ModelSettingsSummary:
        return ModelSettingsSummary(
            source=source,
            provider=runtime.provider,
            base_url=runtime.base_url,
            chat_model=runtime.chat_model,
            embedding_model=embedding_runtime.embedding_model,
            embedding_provider=embedding_runtime.provider,
            embedding_base_url=embedding_runtime.base_url,
            embedding_dimension=embedding_runtime.dimensions,
            has_api_key=bool(runtime.api_key),
            api_key_masked=self._mask_api_key(runtime.api_key),
            has_embedding_api_key=bool(embedding_runtime.api_key),
            embedding_api_key_masked=self._mask_api_key(embedding_runtime.api_key),
            has_embedding_app_id=bool(embedding_runtime.app_id),
            embedding_app_id_masked=self._mask_api_key(embedding_runtime.app_id),
            has_embedding_api_secret=bool(embedding_runtime.api_secret),
            rerank_model=rerank_runtime.embedding_model,
            rerank_provider=rerank_runtime.provider,
            rerank_base_url=rerank_runtime.base_url,
            rerank_workspace_id=rerank_runtime.workspace_id,
            has_rerank_api_key=bool(rerank_runtime.api_key),
            rerank_api_key_masked=self._mask_api_key(rerank_runtime.api_key),
            can_use_model=runtime.can_use_model,
            can_use_embedding_model=embedding_runtime.can_use_model,
            can_use_rerank_model=rerank_runtime.can_use_model,
        )

    def _system_summary(self) -> ModelSettingsSummary:
        system_runtime = self._runtime_from_system_settings()
        embedding_runtime = self._embedding_runtime_from_system_settings()
        rerank_runtime = self._rerank_runtime_from_system_settings()
        if system_runtime.base_url or system_runtime.chat_model or embedding_runtime.embedding_model or rerank_runtime.embedding_model:
            return self._summary_from_runtimes(system_runtime, embedding_runtime, rerank_runtime, source="system")
        return self._empty_summary()

    @staticmethod
    def _empty_summary() -> ModelSettingsSummary:
        return ModelSettingsSummary(
            source="none",
            provider="openai_compatible",
            base_url=None,
            chat_model=None,
            embedding_model=None,
            embedding_provider=None,
            embedding_base_url=None,
            embedding_dimension=None,
            has_api_key=False,
            api_key_masked=None,
            has_embedding_api_key=False,
            embedding_api_key_masked=None,
            rerank_model=None,
            rerank_provider=None,
            rerank_base_url=None,
            rerank_workspace_id=None,
            has_rerank_api_key=False,
            rerank_api_key_masked=None,
            can_use_model=False,
            can_use_embedding_model=False,
            can_use_rerank_model=False,
        )

    def _apply_settings_payload(self, setting: ModelSetting, payload: SaveModelSettingsRequest) -> None:
        setting.provider = self._normalize_provider(payload.provider)
        setting.base_url = payload.base_url
        setting.chat_model = payload.chat_model or None
        setting.embedding_model = payload.embedding_model or None
        setting.embedding_dimension = payload.embedding_dimension
        setting.embedding_provider = (
            self._normalize_provider(payload.embedding_provider or payload.provider)
            if setting.embedding_model
            else None
        )
        setting.embedding_base_url = (payload.embedding_base_url or payload.base_url) if setting.embedding_model else None
        setting.rerank_model = payload.rerank_model or None
        setting.rerank_provider = payload.rerank_provider if setting.rerank_model else None
        setting.rerank_base_url = payload.rerank_base_url if setting.rerank_model else None
        setting.rerank_workspace_id = payload.rerank_workspace_id if setting.rerank_model else None
        if isinstance(payload, SaveModelConfigRequest):
            setting.display_name = payload.display_name
            setting.preset_id = payload.preset_id or None
            setting.embedding_preset_id = (
                (payload.embedding_preset_id or payload.preset_id or None)
                if setting.embedding_model else None
            )
            setting.rerank_preset_id = payload.rerank_preset_id if setting.rerank_model else None
        if payload.api_key:
            setting.api_key_ciphertext = self._encrypt_api_key(payload.api_key)
        if setting.embedding_model:
            if payload.embedding_api_key:
                setting.embedding_api_key_ciphertext = self._encrypt_api_key(payload.embedding_api_key)
            elif not (payload.embedding_base_url or payload.embedding_provider):
                setting.embedding_api_key_ciphertext = setting.api_key_ciphertext
            elif (
                not setting.embedding_api_key_ciphertext
                and setting.embedding_provider == setting.provider
                and setting.embedding_base_url == setting.base_url
            ):
                setting.embedding_api_key_ciphertext = setting.api_key_ciphertext
            if payload.embedding_app_id:
                setting.embedding_app_id_ciphertext = self._encrypt_api_key(payload.embedding_app_id)
            if payload.embedding_api_secret:
                setting.embedding_api_secret_ciphertext = self._encrypt_api_key(payload.embedding_api_secret)
        else:
            setting.embedding_api_key_ciphertext = None
            setting.embedding_app_id_ciphertext = None
            setting.embedding_api_secret_ciphertext = None
            setting.embedding_dimension = None
        if setting.rerank_model and payload.rerank_api_key:
            setting.rerank_api_key_ciphertext = self._encrypt_api_key(payload.rerank_api_key)
        elif not setting.rerank_model:
            setting.rerank_api_key_ciphertext = None

    def _clear_changed_connection_tests(
        self,
        setting: ModelSetting,
        payload: SaveModelSettingsRequest | UpdateModelConfigRequest,
    ) -> None:
        current_key = self._decrypt_api_key(setting.api_key_ciphertext)
        current_embedding_key = self._decrypt_api_key(setting.embedding_api_key_ciphertext)
        current_embedding_app_id = self._decrypt_api_key(setting.embedding_app_id_ciphertext)
        current_embedding_secret = self._decrypt_api_key(setting.embedding_api_secret_ciphertext)
        current_rerank_key = self._decrypt_api_key(setting.rerank_api_key_ciphertext)
        preset_changed = (
            isinstance(payload, (SaveModelConfigRequest, UpdateModelConfigRequest))
            and payload.preset_id is not None
            and payload.preset_id != setting.preset_id
        )
        chat_changed = (
            preset_changed
            or (
                payload.provider is not None
                and self._normalize_provider(payload.provider) != self._normalize_provider(setting.provider)
            )
            or (payload.base_url is not None and payload.base_url != setting.base_url)
            or (bool(payload.api_key) and payload.api_key != current_key)
            or (payload.chat_model is not None and payload.chat_model != setting.chat_model)
        )
        embedding_changed = (
            (
                payload.embedding_provider is not None
                and self._normalize_provider(payload.embedding_provider)
                != self._normalize_provider(setting.embedding_provider or setting.provider)
            )
            or (
                isinstance(payload, (SaveModelConfigRequest, UpdateModelConfigRequest))
                and payload.embedding_preset_id is not None
                and (payload.embedding_preset_id or None) != setting.embedding_preset_id
            )
            or (payload.embedding_base_url is not None and (payload.embedding_base_url or None) != setting.embedding_base_url)
            or (bool(payload.embedding_api_key) and payload.embedding_api_key != current_embedding_key)
            or (bool(payload.embedding_app_id) and payload.embedding_app_id != current_embedding_app_id)
            or (bool(payload.embedding_api_secret) and payload.embedding_api_secret != current_embedding_secret)
            or (payload.embedding_model is not None and (payload.embedding_model or None) != setting.embedding_model)
            or (payload.embedding_dimension is not None and payload.embedding_dimension != setting.embedding_dimension)
        )
        rerank_changed = (
            (payload.rerank_provider is not None and payload.rerank_provider != setting.rerank_provider)
            or (
                isinstance(payload, (SaveModelConfigRequest, UpdateModelConfigRequest))
                and payload.rerank_preset_id is not None
                and (payload.rerank_preset_id or None) != setting.rerank_preset_id
            )
            or (payload.rerank_base_url is not None and (payload.rerank_base_url or None) != setting.rerank_base_url)
            or (bool(payload.rerank_api_key) and payload.rerank_api_key != current_rerank_key)
            or (payload.rerank_model is not None and (payload.rerank_model or None) != setting.rerank_model)
            or (payload.rerank_workspace_id is not None and (payload.rerank_workspace_id or None) != setting.rerank_workspace_id)
        )
        tests = dict(setting.connection_test_json or {})
        if chat_changed:
            tests.pop("chat", None)
            tests.pop("vision", None)
            setting.last_test_ok = None
            setting.last_test_message = None
            setting.last_tested_at = None
        if embedding_changed:
            tests.pop("embedding", None)
        if rerank_changed:
            tests.pop("rerank", None)
        setting.connection_test_json = tests

    @staticmethod
    def _parse_connection_tests(raw_tests: dict | None) -> dict[str, ModelConnectionTestSnapshot]:
        parsed: dict[str, ModelConnectionTestSnapshot] = {}
        for operation in ("chat", "embedding", "rerank", "vision"):
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
        app_id: str | None = None,
        api_secret: str | None = None,
    ) -> bool:
        normalized = cls._normalize_provider(provider or "")
        if normalized == "xfyun_embedding":
            return (
                cls._is_real_value(base_url)
                and cls._is_real_api_key(api_key)
                and cls._is_real_api_key(app_id)
                and cls._is_real_api_key(api_secret)
                and cls._is_real_value(embedding_model)
            )
        return (
            normalized == "openai_compatible"
            and cls._is_real_value(base_url)
            and (cls._is_real_api_key(api_key) or cls._allows_empty_api_key(base_url))
            and cls._is_real_value(embedding_model)
        )

    @classmethod
    def _can_use_rerank_model(
        cls,
        provider: str | None,
        base_url: str | None,
        api_key: str | None,
        model: str | None,
        workspace_id: str | None = None,
    ) -> bool:
        normalized = cls._normalize_provider(provider or "")
        if normalized not in {"siliconflow_rerank", "bailian_rerank", "openai_compatible"}:
            return False
        if normalized == "bailian_rerank" and not cls._is_real_value(workspace_id):
            return False
        return cls._is_real_value(base_url) and cls._is_real_api_key(api_key) and cls._is_real_value(model)

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

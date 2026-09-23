from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from typing import Iterator, Literal, Protocol

from pydantic import BaseModel, Field, field_validator, model_validator

from backend.app.models import ModelSetting
from backend.app.providers.openai_compatible import (
    NativeWebSearchResult,
    OpenAICompatibleConfig,
    OpenAICompatibleEmbeddingConfig,
)


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
    def get_generation_default_for_user(self, user_id: int) -> ModelSetting | None: ...
    def get_embedding_default_for_user(self, user_id: int) -> ModelSetting | None: ...
    def get_rerank_default_for_user(self, user_id: int) -> ModelSetting | None: ...
    def get_vision_default_for_user(self, user_id: int) -> ModelSetting | None: ...
    def list_for_user(self, user_id: int) -> list[ModelSetting]: ...
    def get_by_id_for_user(self, setting_id: int, user_id: int) -> ModelSetting | None: ...
    def save(self, setting: ModelSetting) -> None: ...
    def delete(self, setting: ModelSetting) -> None: ...
    def unset_defaults_for_user(self, user_id: int, except_setting_id: int | None = None) -> None: ...
    def unset_generation_defaults_for_user(self, user_id: int, except_setting_id: int | None = None) -> None: ...
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
    make_generation_default: bool = False
    make_embedding_default: bool = False
    make_rerank_default: bool = False

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
    make_generation_default: bool = False
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


ModelConnectionOperation = Literal["chat", "structured", "embedding", "rerank", "vision"]


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
    latency_ms: int | None = None
    reasoning_tokens: int | None = None


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
    vision_model: str | None = None
    vision_provider: str | None = None
    vision_base_url: str | None = None
    can_use_vision_model: bool = False
    vision_status: Literal["not_configured", "unverified", "verified", "unavailable"] = "not_configured"
    supports_structured_output: bool = False
    supports_reasoning_control: bool = False


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
    is_generation_default: bool = False
    is_embedding_default: bool
    is_rerank_default: bool = False
    last_test_ok: bool | None
    last_test_message: str | None
    last_tested_at: datetime | None
    connection_tests: dict[str, ModelConnectionTestSnapshot] = Field(default_factory=dict)
    supports_structured_output: bool = False
    supports_reasoning_control: bool = False
    structured_output_verified: bool = False


class ModelSettingsListResponse(BaseModel):
    configs: list[ModelConfigSummary]
    system_summary: ModelSettingsSummary
    default_config_id: int | None
    default_chat_config_id: int | None
    default_generation_config_id: int | None = None
    default_embedding_config_id: int | None
    default_rerank_config_id: int | None = None


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
    latency_ms: int | None = None
    reasoning_tokens: int | None = None


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

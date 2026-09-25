from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from typing import Iterator, Literal
from urllib.parse import urlparse

from cryptography.fernet import Fernet, InvalidToken

from backend.app.core.config import Settings
from backend.app.models import ModelSetting, User
from backend.app.providers.openai_compatible import (
    ModelProviderError,
    ModelCompletion,
    OpenAICompatibleChatProvider,
    OpenAICompatibleConfig,
    OpenAICompatibleEmbeddingConfig,
    NativeWebSearchResult,
)
from backend.app.providers.capabilities import provider_capabilities
from backend.app.providers.model_tasks import ModelTaskProfile
from backend.app.providers.retrieval import (
    EmbeddingRequestConfig,
    HttpRerankProvider,
    RerankItem,
    RerankRequestConfig,
    XFYUN_EMBEDDING_DIMENSION,
    XfyunEmbeddingProvider,
)
from backend.app.services.vision_probe_state import VisionProbeState
from backend.app.services.model_execution import (
    ModelExecutionRuntime,
    current_model_execution_context,
)
from backend.app.services.model_connection_testing import ModelConnectionTester
from backend.app.services.model_runtime_config import ModelRuntimeConfigBuilder
from backend.app.services.model_settings_presenter import (
    build_model_config_summary,
    build_model_settings_summary,
    empty_model_settings_summary,
)
from backend.app.services.model_settings_contracts import (
    EmbeddingReindexRequest as EmbeddingReindexRequest,
    ModelChatProvider as ModelChatProvider,
    ModelConfigSummary as ModelConfigSummary,
    ModelConnectionOperation as ModelConnectionOperation,
    ModelConnectionTestRequest as ModelConnectionTestRequest,
    ModelConnectionTestResponse as ModelConnectionTestResponse,
    ModelConnectionTestSnapshot as ModelConnectionTestSnapshot,
    ModelNotConfiguredError as ModelNotConfiguredError,
    ModelSettingsConfigurationError as ModelSettingsConfigurationError,
    ModelSettingsListResponse as ModelSettingsListResponse,
    ModelSettingsNotFoundError as ModelSettingsNotFoundError,
    ModelSettingsRepository as ModelSettingsRepository,
    ModelSettingsSummary as ModelSettingsSummary,
    ModelSettingsValidationError as ModelSettingsValidationError,
    RuntimeModelConfig as RuntimeModelConfig,
    SaveModelConfigRequest as SaveModelConfigRequest,
    SaveModelSettingsRequest as SaveModelSettingsRequest,
    UpdateModelConfigRequest as UpdateModelConfigRequest,
)
from backend.app.services.model_settings_repository import (
    SqlAlchemyModelSettingsRepository as SqlAlchemyModelSettingsRepository,
)


MODEL_NOT_CONFIGURED_MESSAGE = "已找到资料依据，但当前未配置可用模型。"
LOCAL_PLACEHOLDER_API_KEY = "local-dev-key"
GENERATION_TASK_PREFIXES = ("resource_", "path_", "practice_", "report_")


def _uses_generation_runtime(task_type: str) -> bool:
    """Keep normal tutoring and recognition on the answer-model route."""
    return task_type.startswith(GENERATION_TASK_PREFIXES)


class ModelSettingsService:
    def __init__(
        self,
        repository: ModelSettingsRepository,
        settings: Settings,
        provider: ModelChatProvider | None = None,
        execution_runtime: ModelExecutionRuntime | None = None,
        xfyun_embedding_provider: XfyunEmbeddingProvider | None = None,
        rerank_provider: HttpRerankProvider | None = None,
        vision_probe_state: VisionProbeState | None = None,
    ) -> None:
        self.repository = repository
        self.settings = settings
        self.provider = provider or OpenAICompatibleChatProvider()
        self.xfyun_embedding_provider = xfyun_embedding_provider or XfyunEmbeddingProvider()
        self.rerank_provider = rerank_provider or HttpRerankProvider()
        self.vision_probe_state = vision_probe_state or VisionProbeState(settings.redis_url)
        self.execution_runtime = execution_runtime or ModelExecutionRuntime(settings)
        self.runtime_config_builder = ModelRuntimeConfigBuilder(
            settings=self.settings,
            decrypt_api_key=self._decrypt_api_key,
            normalize_provider=self._normalize_provider,
            can_use_model=self._can_use_model,
            can_use_embedding_model=self._can_use_embedding_model,
            can_use_rerank_model=self._can_use_rerank_model,
        )
        self.connection_tester = ModelConnectionTester(
            settings=self.settings,
            provider=self.provider,
            execution_runtime=self.execution_runtime,
            xfyun_embedding_provider=self.xfyun_embedding_provider,
            rerank_provider=self.rerank_provider,
        )

    def get_summary(self, user: User) -> ModelSettingsSummary:
        chat_runtime = self.resolve_runtime_config(user)
        embedding_runtime = self.resolve_embedding_runtime_config(user)
        rerank_runtime = self.resolve_rerank_runtime_config(user)
        if chat_runtime.source != "none" or embedding_runtime.source != "none" or rerank_runtime.source != "none":
            source = chat_runtime.source if chat_runtime.source != "none" else embedding_runtime.source
            if source == "none":
                source = rerank_runtime.source
            summary = build_model_settings_summary(
                runtime=chat_runtime,
                embedding_runtime=embedding_runtime,
                rerank_runtime=rerank_runtime,
                source=source,
                mask_secret=self._mask_api_key,
            )
        else:
            summary = empty_model_settings_summary()
        vision = self.resolve_vision_runtime_config(user)
        return summary.model_copy(update={
            "vision_model": vision.chat_model,
            "vision_provider": vision.provider,
            "vision_base_url": vision.base_url,
            "can_use_vision_model": vision.can_use_model,
            "vision_status": self._vision_status(user),
        })

    def list_configs(self, user: User) -> ModelSettingsListResponse:
        configs = [self._config_summary(setting) for setting in self.repository.list_for_user(user.id)]
        default_chat_config = next((config for config in configs if config.is_default), None)
        default_generation_config = next((config for config in configs if config.is_generation_default), None)
        return ModelSettingsListResponse(
            configs=configs,
            system_summary=self._system_summary(),
            default_config_id=default_chat_config.id if default_chat_config else None,
            default_chat_config_id=default_chat_config.id if default_chat_config else None,
            default_generation_config_id=default_generation_config.id if default_generation_config else None,
            default_embedding_config_id=None,
            default_rerank_config_id=None,
        )

    def save(self, user: User, payload: SaveModelSettingsRequest) -> ModelSettingsSummary:
        if not payload.chat_model:
            raise ModelSettingsValidationError("兼容设置接口必须填写回答模型。")
        existing = self.repository.get_default_for_user(user.id)
        address_changed = existing is not None and (existing.base_url or "").rstrip("/") != payload.base_url.rstrip("/")
        if address_changed and not payload.api_key:
            if not self._allows_empty_api_key(payload.base_url):
                raise ModelSettingsValidationError("更换服务地址必须填写新的 API Key，不能复用原服务商密钥。")
            existing.api_key_ciphertext = None
        setting = existing or ModelSetting(
            user_id=user.id,
            provider="openai_compatible",
            display_name="默认模型配置",
            is_default=True,
        )
        self._clear_changed_connection_tests(setting, payload)
        self._apply_settings_payload(setting, payload)
        setting.is_default = True
        # Answers and generation share this connection. Image use requires an
        # explicit probe; embedding and reranking remain server-managed.
        setting.is_generation_default = False
        setting.is_embedding_default = False
        setting.is_rerank_default = False
        setting.is_vision_default = False
        setting.vision_app_id_ciphertext = None
        setting.vision_api_key_ciphertext = None
        setting.vision_api_secret_ciphertext = None
        self.repository.unset_defaults_for_user(user.id, except_setting_id=setting.id)
        self.repository.unset_generation_defaults_for_user(user.id)
        self.repository.unset_embedding_defaults_for_user(user.id)
        self.repository.unset_rerank_defaults_for_user(user.id)
        self.repository.unset_vision_defaults_for_user(user.id)
        self._save_and_commit(setting)
        return self.get_summary(user)

    def create_config(self, user: User, payload: SaveModelConfigRequest) -> ModelConfigSummary:
        existing_configs = self.repository.list_for_user(user.id)
        self._ensure_unique_display_name(user.id, payload.display_name)
        has_chat_default = any(candidate.is_default for candidate in existing_configs)
        has_generation_default = any(candidate.is_generation_default for candidate in existing_configs)
        setting = ModelSetting(
            user_id=user.id,
            display_name=payload.display_name,
            preset_id=payload.preset_id or None,
            provider="openai_compatible",
            is_default=bool(payload.chat_model)
            and (payload.make_default or not has_chat_default),
            is_generation_default=bool(payload.chat_model)
            and (payload.make_generation_default or not has_generation_default),
            is_embedding_default=False,
            is_rerank_default=False,
            is_vision_default=False,
        )
        self._apply_settings_payload(setting, payload)
        if setting.is_default:
            self.repository.unset_defaults_for_user(user.id)
        if setting.is_generation_default:
            self.repository.unset_generation_defaults_for_user(user.id)
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
        if payload.make_generation_default:
            if not setting.chat_model:
                raise ModelSettingsValidationError("该配置没有回答模型，不能设为生成任务默认。")
            self.repository.unset_generation_defaults_for_user(user.id, except_setting_id=config_id)
            setting.is_generation_default = True
        if payload.make_embedding_default:
            raise ModelSettingsValidationError("向量模型由系统统一配置，不能设置用户级默认。")
        if payload.make_rerank_default:
            raise ModelSettingsValidationError("重排序模型由系统统一配置，不能设置用户级默认。")
        if not setting.chat_model and not setting.embedding_model and not setting.rerank_model:
            raise ModelSettingsValidationError("回答、向量和重排序模型至少填写一项。")
        if setting.is_default and not setting.chat_model:
            raise ModelSettingsValidationError("回答默认配置不能清空回答模型。")
        if setting.is_generation_default and not setting.chat_model:
            raise ModelSettingsValidationError("生成任务默认配置不能清空回答模型。")
        if setting.is_embedding_default and not setting.embedding_model:
            raise ModelSettingsValidationError("向量默认配置不能清空向量模型。")
        if setting.is_rerank_default and not setting.rerank_model:
            raise ModelSettingsValidationError("重排序默认配置不能清空重排序模型。")
        self._save_and_commit(setting)
        return self._config_summary(setting)

    def delete_config(self, user: User, config_id: int) -> ModelSettingsListResponse:
        setting = self._get_user_setting_or_raise(user, config_id)
        was_default = setting.is_default
        was_generation_default = setting.is_generation_default
        was_embedding_default = setting.is_embedding_default
        was_rerank_default = setting.is_rerank_default
        try:
            self.repository.delete(setting)
            if was_default:
                remaining = [candidate for candidate in self.repository.list_for_user(user.id) if candidate.id != config_id]
                next_chat = next((candidate for candidate in remaining if candidate.chat_model), None)
                if next_chat:
                    next_chat.is_default = True
                    self.repository.save(next_chat)
            if was_generation_default:
                remaining = [candidate for candidate in self.repository.list_for_user(user.id) if candidate.id != config_id]
                next_generation = next((candidate for candidate in remaining if candidate.chat_model), None)
                if next_generation:
                    next_generation.is_generation_default = True
                    self.repository.save(next_generation)
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

    def set_generation_default_config(self, user: User, config_id: int) -> ModelSettingsListResponse:
        setting = self._get_user_setting_or_raise(user, config_id)
        if not setting.chat_model:
            raise ModelSettingsValidationError("该配置没有回答模型，不能设为生成任务默认。")
        setting.is_generation_default = True
        self.repository.unset_generation_defaults_for_user(user.id, except_setting_id=config_id)
        self._save_and_commit(setting)
        return self.list_configs(user)

    def set_embedding_default_config(self, user: User, config_id: int) -> ModelSettingsListResponse:
        del user, config_id
        raise ModelSettingsValidationError("向量模型由系统统一配置，不能设置用户级默认。")

    def set_rerank_default_config(self, user: User, config_id: int) -> ModelSettingsListResponse:
        del user, config_id
        raise ModelSettingsValidationError("重排序模型由系统统一配置，不能设置用户级默认。")

    def resolve_runtime_config(self, user: User) -> RuntimeModelConfig:
        user_setting = self.repository.get_default_for_user(user.id)
        if user_setting is not None:
            user_runtime = self._runtime_from_user_setting(user_setting)
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

    def resolve_generation_runtime_config(self, user: User) -> RuntimeModelConfig:
        user_runtime = self.resolve_runtime_config(user)
        if user_runtime.source == "user":
            return user_runtime
        system_runtime = self._generation_runtime_from_system_settings()
        if system_runtime.can_use_model:
            return system_runtime
        return user_runtime

    def resolve_embedding_runtime_config(self, user: User) -> RuntimeModelConfig:
        system_runtime = self._embedding_runtime_from_system_settings()
        if system_runtime.can_use_model or system_runtime.provider == "fastembed_local":
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
        runtime = self.resolve_runtime_config(user)
        return replace(runtime, can_use_model=runtime.can_use_model and self._vision_status(user) == "verified")

    def _vision_status(self, user: User) -> str:
        runtime = self.resolve_runtime_config(user)
        if not runtime.can_use_model:
            return "not_configured"
        fingerprint = self._vision_connection_fingerprint(runtime)
        setting = self.repository.get_default_for_user(user.id)
        if setting is None:
            return self.vision_probe_state.status(user.id, fingerprint)
        snapshot = self._parse_connection_tests(setting.connection_test_json).get("vision")
        raw = (setting.connection_test_json or {}).get("vision", {})
        if (
            snapshot is None or snapshot.model != runtime.chat_model
            or raw.get("connection_fingerprint") != fingerprint
        ):
            return "unverified"
        return "verified" if snapshot.ok else "unavailable"

    @staticmethod
    def _vision_connection_fingerprint(runtime: RuntimeModelConfig) -> str:
        # Stored internally only, never exposed as part of the API snapshot.
        identity = [runtime.provider, runtime.base_url, runtime.chat_model, runtime.api_key, runtime.app_id, runtime.api_secret]
        return hashlib.sha256(json.dumps(identity).encode("utf-8")).hexdigest()

    def vision_completion(self, user: User, *, prompt: str, image_data_urls: list[str]) -> str:
        runtime = self.resolve_vision_runtime_config(user)
        if not runtime.can_use_model or runtime.base_url is None or runtime.chat_model is None:
            raise ModelNotConfiguredError("当前主模型尚未通过图片验证，请先在设置中验证图片能力。")
        capabilities = provider_capabilities(preset_id=runtime.preset_id, base_url=runtime.base_url)
        vision_profile = ModelTaskProfile(
            task_type="vision_understanding",
            reasoning="disabled",
            output_mode=("json_object" if capabilities.structured_output == "json_object" else "text"),
            creativity="stable",
            timeout_seconds=self.settings.vision_request_timeout_seconds,
            max_attempts=1,
        )
        visual_config = OpenAICompatibleConfig(
            base_url=runtime.base_url,
            api_key=runtime.api_key or LOCAL_PLACEHOLDER_API_KEY,
            chat_model=runtime.chat_model,
            reasoning_protocol=capabilities.reasoning_protocol,
            task_profile=vision_profile,
        )
        def call() -> str:
            return self.provider.vision_completion(
                visual_config,
                prompt=prompt,
                image_data_urls=image_data_urls[:3],
                timeout_seconds=self.settings.vision_request_timeout_seconds,
            )
        return self.execution_runtime.execute(
            user_id=user.id,
            provider_source=runtime.source,
            model_config_id=runtime.config_id,
            model_name=runtime.chat_model,
            operation="vision",
            call=call,
            timeout_seconds=self.settings.vision_request_timeout_seconds,
        )

    def chat_completion_with_timeout(
        self,
        user: User,
        messages: list[dict[str, str]],
        timeout_seconds: float,
        thinking_type: str = "disabled",
        max_attempts: int | None = None,
    ) -> str:
        runtime = self.resolve_runtime_config(user)
        if not runtime.can_use_model or runtime.base_url is None or runtime.chat_model is None:
            raise ModelNotConfiguredError(MODEL_NOT_CONFIGURED_MESSAGE)
        capabilities = provider_capabilities(preset_id=runtime.preset_id, base_url=runtime.base_url)
        config = OpenAICompatibleConfig(
            base_url=runtime.base_url,
            api_key=runtime.api_key or LOCAL_PLACEHOLDER_API_KEY,
            chat_model=runtime.chat_model,
            reasoning_protocol=capabilities.reasoning_protocol,
            thinking_type=thinking_type if runtime.preset_id in {"spark", "qwen"} else None,
        )
        return self.execution_runtime.execute(
            user_id=user.id,
            provider_source=runtime.source,
            model_config_id=runtime.config_id,
            model_name=runtime.chat_model,
            operation="chat",
            call=lambda: self.provider.chat_completion(config=config, messages=messages, timeout_seconds=timeout_seconds),
            timeout_seconds=timeout_seconds,
            max_attempts=max_attempts,
        )

    def chat_completion(self, user: User, messages: list[dict[str, str]], thinking_type: str = "disabled") -> str:
        return self.chat_completion_with_timeout(
            user,
            messages,
            timeout_seconds=self.settings.model_request_timeout_seconds,
            thinking_type=thinking_type,
        )

    def chat_completion_for_task(
        self,
        user: User,
        messages: list[dict[str, str]],
        profile: ModelTaskProfile,
        *,
        require_verified: bool = True,
    ) -> str:
        return self.chat_completion_result_for_task(
            user,
            messages,
            profile,
            require_verified=require_verified,
        ).content

    def chat_completion_result_for_task(
        self,
        user: User,
        messages: list[dict[str, str]],
        profile: ModelTaskProfile,
        *,
        require_verified: bool = True,
    ) -> ModelCompletion:
        runtime = self.resolve_generation_runtime_config(user) if _uses_generation_runtime(profile.task_type) else self.resolve_runtime_config(user)
        if not runtime.can_use_model or runtime.base_url is None or runtime.chat_model is None:
            raise ModelNotConfiguredError(MODEL_NOT_CONFIGURED_MESSAGE)
        capabilities = provider_capabilities(preset_id=runtime.preset_id, base_url=runtime.base_url)
        if profile.output_mode == "json_object" and runtime.source == "user" and require_verified:
            setting = self.repository.get_by_id_for_user(int(runtime.config_id or 0), user.id)
            test = (setting.connection_test_json or {}).get("structured") if setting is not None else None
            if not isinstance(test, dict) or test.get("ok") is not True:
                raise ModelNotConfiguredError("当前个人模型尚未通过结构化能力测试，请先在设置中完成测试。")
        effective_profile = profile
        if profile.output_mode == "json_object" and capabilities.structured_output != "json_object":
            effective_profile = replace(profile, output_mode="text")
        config = OpenAICompatibleConfig(
            base_url=runtime.base_url,
            api_key=runtime.api_key or LOCAL_PLACEHOLDER_API_KEY,
            chat_model=runtime.chat_model,
            reasoning_protocol=capabilities.reasoning_protocol,
            task_profile=effective_profile,
        )
        completion = self.execution_runtime.execute(
            user_id=user.id,
            provider_source=runtime.source,
            model_config_id=runtime.config_id,
            model_name=runtime.chat_model,
            operation=f"chat:{profile.task_type}"[:30],
            call=lambda: self.provider.chat_completion_result(
                config=config,
                messages=messages,
                timeout_seconds=profile.timeout_seconds,
            ),
            timeout_seconds=profile.timeout_seconds,
            max_attempts=profile.max_attempts,
        )
        context = current_model_execution_context()
        if context.usage_recorder is not None:
            context.usage_recorder(
                {
                    "task_type": profile.task_type,
                    "input_tokens": completion.input_tokens,
                    "output_tokens": completion.output_tokens,
                    "reasoning_tokens": completion.reasoning_tokens,
                    "first_token_ms": completion.first_token_ms,
                    "total_latency_ms": completion.total_latency_ms,
                }
            )
        return completion

    def chat_completion_stream(
        self,
        user: User,
        messages: list[dict[str, str]],
        thinking_type: str = "disabled",
    ) -> Iterator[str]:
        runtime = self.resolve_runtime_config(user)
        if not runtime.can_use_model or runtime.base_url is None or runtime.chat_model is None:
            raise ModelNotConfiguredError(MODEL_NOT_CONFIGURED_MESSAGE)
        capabilities = provider_capabilities(preset_id=runtime.preset_id, base_url=runtime.base_url)
        config = OpenAICompatibleConfig(
            base_url=runtime.base_url,
            api_key=runtime.api_key or LOCAL_PLACEHOLDER_API_KEY,
            chat_model=runtime.chat_model,
            reasoning_protocol=capabilities.reasoning_protocol,
            thinking_type=thinking_type if runtime.preset_id in {"spark", "qwen"} else None,
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
        if not runtime.can_use_model or runtime.embedding_model is None:
            raise ModelNotConfiguredError("当前未配置可用向量模型。")
        requested_dimensions = dimensions or runtime.dimensions
        def call_provider() -> list[list[float]]:
            if runtime.provider == "fastembed_local":
                from backend.app.providers.local_embeddings import LocalEmbeddingProvider

                return LocalEmbeddingProvider().embed(
                    texts, model_path=self.settings.local_embedding_model_dir,
                    threads=self.settings.local_embedding_threads, input_type=input_type,
                )
            if runtime.base_url is None:
                raise ModelNotConfiguredError("当前未配置可用向量服务地址。")
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
        if operation == "vision":
            setting = self.repository.get_default_for_user(user.id)
            if setting is not None:
                return self.test_config_connection(user, setting.id, operation)
        runtime = self.resolve_runtime_config(user) if operation == "vision" else self._runtime_for_operation(user, operation)
        result = self._test_runtime(runtime, user_id=user.id, operation=operation)
        if operation == "vision" and runtime.can_use_model:
            recorded = self.vision_probe_state.record(user.id, self._vision_connection_fingerprint(runtime), result.ok)
            if not recorded:
                return result.model_copy(update={
                    "ok": False, "code": "provider_error", "retryable": True,
                    "message": "图片测试已结束，但验证状态未能保存，请检查 Redis 后重试。",
                })
        return result

    def test_config_connection(
        self,
        user: User,
        config_id: int,
        operation: ModelConnectionOperation = "chat",
    ) -> ModelConnectionTestResponse:
        setting = self._get_user_setting_or_raise(user, config_id)
        vision_fingerprint = self._vision_connection_fingerprint(self._runtime_from_user_setting(setting))
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
            latency_ms=result.latency_ms,
            reasoning_tokens=result.reasoning_tokens,
        ).model_dump(mode="json")
        if operation == "vision":
            tests[operation]["connection_fingerprint"] = vision_fingerprint
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
        return self.connection_tester.test(runtime, user_id=user_id, operation=operation)
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
        return self._runtime_from_user_setting(setting)

    def _runtime_from_user_setting(self, setting: ModelSetting) -> RuntimeModelConfig:
        return self.runtime_config_builder._runtime_from_user_setting(setting)

    def _runtime_from_system_settings(self) -> RuntimeModelConfig:
        return self.runtime_config_builder._runtime_from_system_settings()

    def _generation_runtime_from_system_settings(self) -> RuntimeModelConfig:
        return self.runtime_config_builder._generation_runtime_from_system_settings()

    def _embedding_runtime_from_user_setting(self, setting: ModelSetting) -> RuntimeModelConfig:
        return self.runtime_config_builder._embedding_runtime_from_user_setting(setting)

    def _embedding_runtime_from_system_settings(self) -> RuntimeModelConfig:
        return self.runtime_config_builder._embedding_runtime_from_system_settings()

    def _rerank_runtime_from_user_setting(self, setting: ModelSetting) -> RuntimeModelConfig:
        return self.runtime_config_builder._rerank_runtime_from_user_setting(setting)

    def _rerank_runtime_from_system_settings(self) -> RuntimeModelConfig:
        return self.runtime_config_builder._rerank_runtime_from_system_settings()

    def _config_summary(self, setting: ModelSetting) -> ModelConfigSummary:
        runtime = self._runtime_from_user_setting(setting)
        connection_tests = self._parse_connection_tests(setting.connection_test_json)
        embedding_runtime = self._embedding_runtime_from_user_setting(setting)
        rerank_runtime = self._rerank_runtime_from_user_setting(setting)
        return build_model_config_summary(
            setting=setting,
            runtime=runtime,
            embedding_runtime=embedding_runtime,
            rerank_runtime=rerank_runtime,
            connection_tests=connection_tests,
            mask_secret=self._mask_api_key,
        )

    def _system_summary(self) -> ModelSettingsSummary:
        system_runtime = self._runtime_from_system_settings()
        embedding_runtime = self._embedding_runtime_from_system_settings()
        rerank_runtime = self._rerank_runtime_from_system_settings()
        if (
            system_runtime.base_url
            or system_runtime.chat_model
            or embedding_runtime.embedding_model
            or rerank_runtime.embedding_model
        ):
            summary = build_model_settings_summary(
                runtime=system_runtime,
                embedding_runtime=embedding_runtime,
                rerank_runtime=rerank_runtime,
                source="system",
                mask_secret=self._mask_api_key,
            )
            return summary
        return empty_model_settings_summary()

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
        vision_changed = chat_changed
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
            tests.pop("structured", None)
            setting.last_test_ok = None
            setting.last_test_message = None
            setting.last_tested_at = None
        if vision_changed:
            tests.pop("vision", None)
        if embedding_changed:
            tests.pop("embedding", None)
        if rerank_changed:
            tests.pop("rerank", None)
        setting.connection_test_json = tests

    @staticmethod
    def _parse_connection_tests(raw_tests: dict | None) -> dict[str, ModelConnectionTestSnapshot]:
        parsed: dict[str, ModelConnectionTestSnapshot] = {}
        for operation in ("chat", "structured", "embedding", "rerank", "vision"):
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
            parsed = urlparse((base_url or "").strip())
            if parsed.hostname not in {"dashscope.aliyuncs.com", "dashscope-intl.aliyuncs.com"}:
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
        return bool(cleaned) and cleaned not in {
            "replace-with-your-own-key",
            "replace-with-your-bailian-api-key",
            "example-key",
        }

    @staticmethod
    def _allows_empty_api_key(base_url: str | None) -> bool:
        parsed = urlparse((base_url or "").strip())
        return parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "host.docker.internal", "0.0.0.0"}

    @staticmethod
    def _mask_api_key(api_key: str | None) -> str | None:
        if not api_key:
            return None
        if len(api_key) <= 8:
            return f"{api_key[:2]}...{api_key[-2:]}"
        return f"{api_key[:4]}...{api_key[-4:]}"

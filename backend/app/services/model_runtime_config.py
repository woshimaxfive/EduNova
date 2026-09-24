from __future__ import annotations

from collections.abc import Callable

from backend.app.core.config import Settings
from backend.app.models import ModelSetting
from backend.app.providers.retrieval import XFYUN_EMBEDDING_DIMENSION
from backend.app.services.model_settings_contracts import RuntimeModelConfig


class ModelRuntimeConfigBuilder:
    def __init__(
        self,
        *,
        settings: Settings,
        decrypt_api_key: Callable[[str | None], str | None],
        normalize_provider: Callable[[str], str],
        can_use_model: Callable[[str | None, str | None, str | None, str | None], bool],
        can_use_embedding_model: Callable[
            [str | None, str | None, str | None, str | None, str | None, str | None],
            bool,
        ],
        can_use_rerank_model: Callable[
            [str | None, str | None, str | None, str | None, str | None],
            bool,
        ],
    ) -> None:
        self.settings = settings
        self._decrypt_api_key = decrypt_api_key
        self._normalize_provider = normalize_provider
        self._can_use_model = can_use_model
        self._can_use_embedding_model = can_use_embedding_model
        self._can_use_rerank_model = can_use_rerank_model

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
        base_url = self.settings.system_model_base_url.strip()
        lowered_url = base_url.lower()
        preset_id = (
            "spark"
            if "spark-api-open.xf-yun.com" in lowered_url
            else "qwen"
            if "dashscope.aliyuncs.com" in lowered_url
            else "openai"
            if "api.openai.com" in lowered_url
            else None
        )
        return RuntimeModelConfig(
            source="system",
            provider=self._normalize_provider(self.settings.system_model_provider),
            base_url=base_url or None,
            api_key=api_key or None,
            chat_model=self.settings.system_chat_model.strip() or None,
            embedding_model=self.settings.system_embedding_model.strip() or None,
            can_use_model=self._can_use_model(
                provider=self.settings.system_model_provider,
                base_url=self.settings.system_model_base_url,
                api_key=api_key,
                chat_model=self.settings.system_chat_model,
            ),
            preset_id=preset_id,
        )

    def _generation_runtime_from_system_settings(self) -> RuntimeModelConfig:
        api_key = self.settings.system_generation_api_key.strip()
        base_url = self.settings.system_generation_base_url.strip()
        model = self.settings.system_generation_model.strip()
        provider = self.settings.system_generation_provider.strip() or "openai_compatible"
        lowered_url = base_url.lower()
        preset_id = "qwen" if "dashscope.aliyuncs.com" in lowered_url else "custom"
        return RuntimeModelConfig(
            source="system",
            provider=self._normalize_provider(provider),
            base_url=base_url or None,
            api_key=api_key or None,
            chat_model=model or None,
            embedding_model=None,
            can_use_model=self._can_use_model(provider, base_url, api_key, model),
            preset_id=preset_id,
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
        if self.settings.system_embedding_provider.strip() == "fastembed_local":
            from importlib.util import find_spec
            from backend.app.providers.local_embeddings import LocalEmbeddingProvider, MODEL_NAME, MODEL_DIMENSION, MODEL_REVISION

            return RuntimeModelConfig(
                source="system", provider="fastembed_local", base_url=None, api_key=None,
                chat_model=None, embedding_model=f"{MODEL_NAME}@{MODEL_REVISION}",
                can_use_model=(find_spec("fastembed") is not None
                               and LocalEmbeddingProvider.prepared(self.settings.local_embedding_model_dir)),
                dimensions=MODEL_DIMENSION,
            )
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
        if self.settings.system_embedding_provider.strip() == "fastembed_local":
            return RuntimeModelConfig(source="none", provider="fastembed_local", base_url=None,
                                      api_key=None, chat_model=None, embedding_model=None, can_use_model=False)
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

from __future__ import annotations

from typing import Callable, Literal

from backend.app.models import ModelSetting
from backend.app.providers.capabilities import provider_capabilities
from backend.app.services.model_settings_contracts import (
    ModelConfigSummary,
    ModelConnectionTestSnapshot,
    ModelSettingsSummary,
    RuntimeModelConfig,
)


MaskSecret = Callable[[str | None], str | None]


def build_model_config_summary(
    *,
    setting: ModelSetting,
    runtime: RuntimeModelConfig,
    embedding_runtime: RuntimeModelConfig,
    rerank_runtime: RuntimeModelConfig,
    connection_tests: dict[str, ModelConnectionTestSnapshot],
    mask_secret: MaskSecret,
) -> ModelConfigSummary:
    capabilities = provider_capabilities(preset_id=setting.preset_id, base_url=setting.base_url)
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
        api_key_masked=mask_secret(runtime.api_key),
        has_embedding_api_key=has_embedding and bool(embedding_runtime.api_key),
        embedding_api_key_masked=mask_secret(embedding_runtime.api_key) if has_embedding else None,
        has_embedding_app_id=has_embedding and bool(embedding_runtime.app_id),
        embedding_app_id_masked=mask_secret(embedding_runtime.app_id) if has_embedding else None,
        has_embedding_api_secret=has_embedding and bool(embedding_runtime.api_secret),
        rerank_model=rerank_runtime.embedding_model if has_rerank else None,
        rerank_provider=rerank_runtime.provider if has_rerank else None,
        rerank_preset_id=setting.rerank_preset_id if has_rerank else None,
        rerank_base_url=rerank_runtime.base_url if has_rerank else None,
        rerank_workspace_id=rerank_runtime.workspace_id if has_rerank else None,
        has_rerank_api_key=has_rerank and bool(rerank_runtime.api_key),
        rerank_api_key_masked=mask_secret(rerank_runtime.api_key) if has_rerank else None,
        can_use_model=runtime.can_use_model,
        can_use_embedding_model=embedding_runtime.can_use_model,
        can_use_rerank_model=rerank_runtime.can_use_model,
        is_default=setting.is_default,
        is_generation_default=setting.is_generation_default,
        is_embedding_default=setting.is_embedding_default,
        is_rerank_default=setting.is_rerank_default,
        last_test_ok=setting.last_test_ok,
        last_test_message=setting.last_test_message,
        last_tested_at=setting.last_tested_at,
        connection_tests=connection_tests,
        supports_structured_output=capabilities.structured_output == "json_object",
        supports_reasoning_control=capabilities.supports_thinking_control,
        structured_output_verified=bool(connection_tests.get("structured") and connection_tests["structured"].ok),
    )


def build_model_settings_summary(
    *,
    runtime: RuntimeModelConfig,
    embedding_runtime: RuntimeModelConfig,
    rerank_runtime: RuntimeModelConfig,
    source: Literal["user", "system"],
    mask_secret: MaskSecret,
) -> ModelSettingsSummary:
    capabilities = provider_capabilities(preset_id=runtime.preset_id, base_url=runtime.base_url)
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
        api_key_masked=mask_secret(runtime.api_key),
        has_embedding_api_key=bool(embedding_runtime.api_key),
        embedding_api_key_masked=mask_secret(embedding_runtime.api_key),
        has_embedding_app_id=bool(embedding_runtime.app_id),
        embedding_app_id_masked=mask_secret(embedding_runtime.app_id),
        has_embedding_api_secret=bool(embedding_runtime.api_secret),
        rerank_model=rerank_runtime.embedding_model,
        rerank_provider=rerank_runtime.provider,
        rerank_base_url=rerank_runtime.base_url,
        rerank_workspace_id=rerank_runtime.workspace_id,
        has_rerank_api_key=bool(rerank_runtime.api_key),
        rerank_api_key_masked=mask_secret(rerank_runtime.api_key),
        can_use_model=runtime.can_use_model,
        can_use_embedding_model=embedding_runtime.can_use_model,
        can_use_rerank_model=rerank_runtime.can_use_model,
        supports_structured_output=capabilities.structured_output == "json_object",
        supports_reasoning_control=capabilities.supports_thinking_control,
    )


def empty_model_settings_summary() -> ModelSettingsSummary:
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
        vision_model=None,
        vision_provider=None,
        vision_base_url=None,
        can_use_vision_model=False,
    )

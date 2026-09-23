from __future__ import annotations

import json

import pytest

from backend.app.providers.openai_compatible import ModelProviderError
from backend.app.services.model_settings import ModelNotConfiguredError, ModelSettingsService, SaveModelSettingsRequest
from backend.tests.test_model_settings import (
    FakeModelSettingsRepository, FakeProvider, ImmediateExecutionRuntime, make_settings, make_user,
)


def personal_service():
    provider = FakeProvider(content=json.dumps({
        "standalone_query": "识别文字", "visual_summary": "白底黑字", "extracted_text": "EduNova Vision 32",
        "observations": ["可见文字"], "uncertainties": [], "intent": "visual_learning",
        "search_required": False, "reasoning_mode": "auto", "confidence": 0.9,
    }))
    repository = FakeModelSettingsRepository({})
    service = ModelSettingsService(
        repository, make_settings(system_model_base_url="https://server.example/v1",
                                  system_chat_model="server-main", system_model_api_key="sk-server-secret"),
        provider=provider, execution_runtime=ImmediateExecutionRuntime(),
    )
    service.save(make_user(), SaveModelSettingsRequest(
        provider="openai_compatible", base_url="https://personal.example/v1",
        api_key="sk-personal-secret", chat_model="personal-model",
    ))
    return service, repository, provider


def test_personal_model_requires_probe_and_never_uses_server_vision():
    service, _, provider = personal_service()
    assert service.get_summary(make_user()).vision_status == "unverified"
    with pytest.raises(ModelNotConfiguredError):
        service.vision_completion(make_user(), prompt="识图", image_data_urls=["data:image/png;base64,test"])
    assert not provider.calls
    result = service.test_connection(make_user(), "vision")
    assert result.ok and result.model == "personal-model"
    assert service.get_summary(make_user()).vision_status == "verified"
    service.vision_completion(make_user(), prompt="识图", image_data_urls=["data:image/png;base64,test"])
    assert all(call["config"].api_key == "sk-personal-secret" for call in provider.calls)
    assert service.resolve_generation_runtime_config(make_user()).chat_model == "personal-model"
    assert service.resolve_vision_runtime_config(make_user(2)).chat_model == "server-main"


@pytest.mark.parametrize("field,value", [
    ("chat_model", "another-model"), ("base_url", "https://another.example/v1"), ("api_key", "sk-new-secret"),
])
def test_changing_connection_invalidates_vision_probe(field, value):
    service, _, _ = personal_service()
    assert service.test_connection(make_user(), "vision").ok
    payload = dict(provider="openai_compatible", base_url="https://personal.example/v1", chat_model="personal-model")
    payload[field] = value
    service.save(make_user(), SaveModelSettingsRequest(**payload))
    assert service.get_summary(make_user()).vision_status == "unverified"
    assert not service.resolve_vision_runtime_config(make_user()).can_use_model


def test_timeout_is_retryable_not_a_permanent_text_only_classification():
    service, _, provider = personal_service()
    provider.should_raise = ModelProviderError("超时", code="timeout", retryable=True)
    result = service.test_connection(make_user(), "vision")
    assert not result.ok and result.retryable
    assert service.get_summary(make_user()).vision_status == "unavailable"
    provider.should_raise = None
    assert service.test_connection(make_user(), "vision").ok
    assert service.get_summary(make_user()).vision_status == "verified"


def test_schema_only_response_does_not_prove_image_understanding():
    service, _, provider = personal_service()
    payload = json.loads(provider.content)
    payload["extracted_text"] = ""
    provider.content = json.dumps(payload)
    assert not service.test_connection(make_user(), "vision").ok
    assert not service.resolve_vision_runtime_config(make_user()).can_use_model


def test_stale_probe_fingerprint_and_invalid_personal_key_do_not_fall_back():
    service, repository, _ = personal_service()
    assert service.test_connection(make_user(), "vision").ok
    setting = repository.get_default_for_user(make_user().id)
    setting.base_url = "https://changed.example/v1"
    assert service.get_summary(make_user()).vision_status == "unverified"
    setting.api_key_ciphertext = None
    for runtime in (service.resolve_runtime_config(make_user()), service.resolve_generation_runtime_config(make_user())):
        assert runtime.source == "user" and not runtime.can_use_model


class MemoryProbeState:
    def __init__(self):
        self.values = {}
        self.writable = True

    def status(self, user_id, fingerprint):
        return self.values.get((user_id, fingerprint), "unverified")

    def record(self, user_id, fingerprint, ok):
        if not self.writable:
            return False
        self.values[user_id, fingerprint] = "verified" if ok else "unavailable"
        return True


def system_service():
    personal, _, provider = personal_service()
    state = MemoryProbeState()
    service = ModelSettingsService(
        FakeModelSettingsRepository({}), personal.settings, provider=provider,
        execution_runtime=ImmediateExecutionRuntime(), vision_probe_state=state,
    )
    return service, state, provider


def test_system_vision_uses_main_credentials_only_after_probe():
    service, state, provider = system_service()
    user = make_user()
    assert service.get_summary(user).vision_status == "unverified"
    assert not service.resolve_vision_runtime_config(user).can_use_model
    assert service.test_connection(user, "vision").ok
    assert service.get_summary(user).vision_status == "verified"
    service.vision_completion(user, prompt="识图", image_data_urls=["data:image/png;base64,test"])
    assert all(call["config"].chat_model == "server-main" for call in provider.calls)
    assert all(call["config"].api_key == "sk-server-secret" for call in provider.calls)
    # Another worker sees shared proof, but a different user does not.
    worker = ModelSettingsService(
        service.repository, service.settings, vision_probe_state=state,
        execution_runtime=ImmediateExecutionRuntime(),
    )
    assert worker.resolve_vision_runtime_config(user).can_use_model
    assert not worker.resolve_vision_runtime_config(make_user(2)).can_use_model
    service.settings.system_model_api_key = "sk-rotated"
    assert service.get_summary(user).vision_status == "unverified"


def test_failed_system_probe_and_lost_state_disable_images_not_text():
    service, state, provider = system_service()
    user = make_user()
    provider.should_raise = ModelProviderError("该模型不支持图片", code="invalid_response")
    assert not service.test_connection(user, "vision").ok
    assert service.get_summary(user).vision_status == "unavailable"
    assert service.resolve_runtime_config(user).can_use_model
    provider.should_raise = None
    assert service.test_connection(user, "vision").ok
    state.values.clear()
    assert not service.resolve_vision_runtime_config(user).can_use_model
    state.writable = False
    result = service.test_connection(user, "vision")
    assert not result.ok and result.retryable
    assert "Redis" in result.message


def test_legacy_independent_vision_environment_is_ignored():
    service, _, _ = system_service()
    service.settings.system_model_api_key = ""
    service.settings = make_settings(
        system_model_api_key="", system_model_base_url="", system_chat_model="",
        system_vision_api_key="sk-old", system_vision_model="old-vision",
    )
    service.runtime_config_builder.settings = service.settings
    assert service.get_summary(make_user()).vision_status == "not_configured"
    assert not service.resolve_vision_runtime_config(make_user()).can_use_model


def test_vision_default_route_and_separate_credentials_are_removed():
    from backend.app.main import app
    from backend.app.services.model_settings_contracts import SaveModelConfigRequest

    assert not any("vision-default" in route.path for route in app.routes if hasattr(route, "path"))
    assert "make_vision_default" not in SaveModelConfigRequest.model_fields
    assert "vision_api_key" not in SaveModelConfigRequest.model_fields


def test_probe_cache_uses_expiring_scoped_keys_and_fails_closed():
    from redis.exceptions import ConnectionError
    from backend.app.services.vision_probe_state import VisionProbeState

    class RedisDouble:
        def __init__(self):
            self.values = {}
            self.expiry = None
            self.fail = False

        def set(self, key, value, ex):
            if self.fail:
                raise ConnectionError()
            self.values[key] = value
            self.expiry = ex
            return True

        def get(self, key):
            if self.fail:
                raise ConnectionError()
            return self.values.get(key)

    cache = VisionProbeState("redis://localhost:6379/0")
    cache.redis = RedisDouble()
    assert cache.record(1, "fingerprint", True)
    assert cache.redis.expiry == 604800
    assert cache.status(1, "fingerprint") == "verified"
    assert cache.status(2, "fingerprint") == "unverified"
    assert cache.record(1, "fingerprint", False)
    assert cache.redis.expiry == 3600
    assert cache.status(1, "fingerprint") == "unavailable"
    cache.redis.fail = True
    assert not cache.record(1, "fingerprint", True)
    assert cache.status(1, "fingerprint") == "unverified"

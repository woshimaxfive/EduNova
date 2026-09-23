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
        repository, make_settings(system_vision_provider="openai_compatible",
                                  system_vision_base_url="https://server.example/v1",
                                  system_vision_model="server-vision", system_vision_api_key="sk-server-secret"),
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
    assert service.resolve_vision_runtime_config(make_user(2)).chat_model == "server-vision"


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

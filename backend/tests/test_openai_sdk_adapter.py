from __future__ import annotations

import httpx
import json
import pytest

from backend.app.providers.model_tasks import ModelTaskProfile
from backend.app.providers.openai_compatible import (
    ModelProviderError,
    OpenAICompatibleChatProvider,
    OpenAICompatibleConfig,
)


def config() -> OpenAICompatibleConfig:
    return OpenAICompatibleConfig("https://model.example/v1", "test-key", "test-model")


def test_sdk_adapter_disables_internal_retries() -> None:
    provider = OpenAICompatibleChatProvider(httpx.MockTransport(lambda _request: httpx.Response(200, json={})))
    client = provider._client(config().base_url, config().api_key, 3)
    try:
        assert client.max_retries == 0
    finally:
        client.close()


def test_sdk_adapter_preserves_retry_after() -> None:
    provider = OpenAICompatibleChatProvider(
        httpx.MockTransport(lambda _request: httpx.Response(429, headers={"Retry-After": "2.5"}, json={"error": {"message": "busy"}}))
    )
    with pytest.raises(ModelProviderError) as raised:
        provider.chat_completion(config(), [{"role": "user", "content": "问题"}], 3)
    assert raised.value.code == "rate_limited"
    assert raised.value.retry_after_seconds == 2.5


class InterruptingStream(httpx.SyncByteStream):
    def __iter__(self):
        yield 'data: {"choices":[{"delta":{"content":"第一段"}}]}\n\n'.encode()
        raise httpx.ReadError("stream closed")


def test_sdk_adapter_never_retries_after_first_stream_token() -> None:
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, stream=InterruptingStream())

    provider = OpenAICompatibleChatProvider(httpx.MockTransport(handler))
    stream = provider.chat_completion_stream(config(), [{"role": "user", "content": "问题"}], 3)
    assert next(stream) == "第一段"
    with pytest.raises(ModelProviderError) as raised:
        next(stream)
    assert raised.value.code == "stream_interrupted"
    assert raised.value.retryable is False
    assert calls == 1


def test_openai_native_search_uses_responses_and_returns_verifiable_sources() -> None:
    bodies: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content))
        assert request.url.path.endswith("/responses")
        return httpx.Response(200, json={
            "id": "resp_test",
            "object": "response",
            "created_at": 1,
            "status": "completed",
            "model": "test-model",
            "output": [{
                "id": "ws_1",
                "type": "web_search_call",
                "status": "completed",
                "action": {"type": "search", "query": "测试", "sources": [{
                    "type": "url",
                    "url": "https://example.test/current",
                    "title": "可验证来源",
                }]},
            }],
        })

    result = OpenAICompatibleChatProvider(httpx.MockTransport(handler)).native_web_search(
        config(), query="请联网核实", timeout_seconds=3, native_kind="openai", force=True
    )

    assert bodies[0]["tools"] == [{"type": "web_search"}]
    assert result.backend == "native_openai"
    assert result.citations[0]["url"] == "https://example.test/current"


def test_native_search_without_source_url_requires_external_fallback() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "id": "chatcmpl_test",
            "object": "chat.completion",
            "created": 1,
            "model": "test-model",
            "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": "没有来源"}}],
        })

    result = OpenAICompatibleChatProvider(httpx.MockTransport(handler)).native_web_search(
        config(), query="测试", timeout_seconds=3, native_kind="spark"
    )

    assert result.citations == []
    assert result.warning is not None


def test_qwen_structured_task_disables_thinking_and_uses_json_mode() -> None:
    bodies: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl_task",
                "object": "chat.completion",
                "created": 1,
                "model": "qwen3.7-plus",
                "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": '{"ok":true}'}}],
                "usage": {
                    "prompt_tokens": 12,
                    "completion_tokens": 5,
                },
            },
        )

    profile = ModelTaskProfile(task_type="path_planning", reasoning="disabled", output_mode="json_object")
    result = OpenAICompatibleChatProvider(httpx.MockTransport(handler)).chat_completion_result(
        OpenAICompatibleConfig(
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "test-key",
            "qwen3.7-plus",
            reasoning_protocol="qwen_enable_thinking",
            task_profile=profile,
        ),
        [{"role": "user", "content": "输出 JSON"}],
        3,
    )

    assert bodies[0]["enable_thinking"] is False
    assert bodies[0]["response_format"] == {"type": "json_object"}
    assert bodies[0]["temperature"] == 0.1
    assert result.reasoning_tokens == 0
    assert result.total_latency_ms is not None


def test_custom_provider_never_receives_unverified_qwen_private_parameter() -> None:
    bodies: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl_custom",
                "object": "chat.completion",
                "created": 1,
                "model": "custom-model",
                "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": "ok"}}],
            },
        )

    OpenAICompatibleChatProvider(httpx.MockTransport(handler)).chat_completion(
        OpenAICompatibleConfig(
            "https://custom.example/v1",
            "test-key",
            "custom-model",
            reasoning_protocol="none",
            task_profile=ModelTaskProfile(task_type="answer", reasoning="deep", output_mode="text"),
        ),
        [{"role": "user", "content": "分析"}],
        3,
    )

    assert "enable_thinking" not in bodies[0]
    assert "thinking" not in bodies[0]

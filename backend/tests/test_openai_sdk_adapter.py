from __future__ import annotations

import httpx
import pytest

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

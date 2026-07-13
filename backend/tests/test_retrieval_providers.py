from __future__ import annotations

import base64
import json
import math
import struct

import httpx
import pytest

from backend.app.providers.openai_compatible import ModelProviderError, OpenAICompatibleChatProvider, OpenAICompatibleConfig
from backend.app.providers.retrieval import (
    EmbeddingRequestConfig,
    HttpRerankProvider,
    RerankRequestConfig,
    XFYUN_EMBEDDING_DIMENSION,
    XfyunEmbeddingProvider,
    split_utf8_bytes,
)


def test_x2_flash_thinking_and_reasoning_content_are_isolated() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["authorization"] = request.headers.get("Authorization")
        captured["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": "最终答案",
                            "reasoning_content": "不应返回或持久化的推理内容",
                        }
                    }
                ]
            },
        )

    provider = OpenAICompatibleChatProvider(httpx.MockTransport(handler))
    content = provider.chat_completion(
        OpenAICompatibleConfig(
            base_url="https://spark-api-open.xf-yun.com/agent/v1/",
            api_key="test-password",
            chat_model="spark-x",
            thinking_type="disabled",
        ),
        [{"role": "user", "content": "什么是向量检索？"}],
        5,
    )

    assert content == "最终答案"
    assert captured["authorization"] == "Bearer test-password"
    assert captured["payload"] == {
        "model": "spark-x",
        "messages": [{"role": "user", "content": "什么是向量检索？"}],
        "temperature": 0.2,
        "thinking": {"type": "disabled"},
    }


def test_xfyun_embedding_splits_utf8_payload_and_pools_2560_dimensions() -> None:
    requests: list[dict[str, object]] = []
    raw_vector = struct.pack(f"<{XFYUN_EMBEDDING_DIMENSION}f", *([1.0] * XFYUN_EMBEDDING_DIMENSION))

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        requests.append(payload)
        encoded = payload["payload"]["messages"]["text"]
        decoded = json.loads(base64.b64decode(encoded).decode("utf-8"))
        assert len(decoded["messages"][0]["content"].encode("utf-8")) <= 2048
        assert request.url.params.get("authorization")
        return httpx.Response(
            200,
            json={
                "header": {"code": 0},
                "payload": {"feature": {"text": base64.b64encode(raw_vector).decode("ascii")}},
            },
        )

    provider = XfyunEmbeddingProvider(httpx.MockTransport(handler))
    text = "学习资料" * 600
    vector = provider.embed_documents(
        EmbeddingRequestConfig(
            provider="xfyun_embedding",
            base_url="https://emb-cn-huabei-1.xf-yun.com/",
            api_key="api-key",
            api_secret="api-secret",
            app_id="app-id",
            model="llm-embedding",
            dimensions=2560,
        ),
        [text],
        5,
    )[0]

    assert len(requests) > 1
    assert all(item["parameter"]["emb"]["domain"] == "para" for item in requests)
    assert len(vector) == XFYUN_EMBEDDING_DIMENSION
    assert math.isclose(sum(value * value for value in vector), 1.0, rel_tol=1e-6)


def test_xfyun_embedding_uses_query_domain_for_questions() -> None:
    domains: list[str] = []
    raw_vector = struct.pack(f"<{XFYUN_EMBEDDING_DIMENSION}f", *([1.0] * XFYUN_EMBEDDING_DIMENSION))

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        domains.append(payload["parameter"]["emb"]["domain"])
        return httpx.Response(
            200,
            json={"header": {"code": 0}, "payload": {"feature": {"text": base64.b64encode(raw_vector).decode("ascii")}}},
        )

    provider = XfyunEmbeddingProvider(httpx.MockTransport(handler))
    provider.embed_query(
        EmbeddingRequestConfig(
            provider="xfyun_embedding",
            base_url="https://emb-cn-huabei-1.xf-yun.com/",
            api_key="api-key",
            api_secret="api-secret",
            app_id="app-id",
            model="llm-embedding",
        ),
        "反向传播为什么需要链式法则？",
        5,
    )

    assert domains == ["query"]


def test_siliconflow_and_bailian_rerank_urls_and_order() -> None:
    urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        urls.append(str(request.url))
        payload = json.loads(request.content)
        assert payload["documents"] == ["文档一", "文档二", "文档三"]
        return httpx.Response(
            200,
            json={"results": [{"index": 1, "relevance_score": 0.91}, {"index": 0, "relevance_score": 0.73}]},
        )

    provider = HttpRerankProvider(httpx.MockTransport(handler))
    silicon_items = provider.rerank(
        RerankRequestConfig(
            provider="siliconflow_rerank",
            base_url="https://api.siliconflow.cn/v1",
            api_key="key",
            model="BAAI/bge-reranker-v2-m3",
        ),
        "查询",
        ["文档一", "文档二", "文档三"],
        2,
        5,
    )
    bailian_items = provider.rerank(
        RerankRequestConfig(
            provider="bailian_rerank",
            base_url="https://{workspace_id}.cn-beijing.maas.aliyuncs.com/compatible-api/v1",
            api_key="key",
            model="qwen3-rerank",
            workspace_id="ws-123",
        ),
        "查询",
        ["文档一", "文档二", "文档三"],
        2,
        5,
    )

    assert urls == [
        "https://api.siliconflow.cn/v1/rerank",
        "https://ws-123.cn-beijing.maas.aliyuncs.com/compatible-api/v1/reranks",
    ]
    assert [(item.index, item.score) for item in silicon_items] == [(1, 0.91), (0, 0.73)]
    assert bailian_items == silicon_items


def test_rerank_provider_uses_rerank_specific_safe_errors() -> None:
    provider = HttpRerankProvider(
        httpx.MockTransport(lambda request: httpx.Response(401, request=request))
    )

    with pytest.raises(ModelProviderError) as exc_info:
        provider.rerank(
            RerankRequestConfig(
                provider="siliconflow_rerank",
                base_url="https://api.siliconflow.cn/v1",
                api_key="secret",
                model="BAAI/bge-reranker-v2-m3",
            ),
            "反向传播",
            ["梯度通过链式法则逐层传播。"],
            1,
            5,
        )

    assert exc_info.value.code == "authentication_failed"
    assert "重排序" in str(exc_info.value)


def test_split_utf8_bytes_preserves_text_without_cutting_characters() -> None:
    text = "向量检索ABC" * 900
    parts = split_utf8_bytes(text, 2048)

    assert "".join(parts) == text
    assert all(len(part.encode("utf-8")) <= 2048 for part in parts)

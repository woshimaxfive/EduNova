from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import format_datetime
import hashlib
import hmac
import json
import math
import struct
from typing import Any, Protocol
from urllib.parse import urlencode, urlparse

import httpx

from backend.app.providers.openai_compatible import ModelProviderError


XFYUN_EMBEDDING_DIMENSION = 2560
XFYUN_MAX_INPUT_BYTES = 2048


@dataclass(frozen=True)
class EmbeddingRequestConfig:
    provider: str
    base_url: str
    api_key: str
    model: str
    dimensions: int | None = None
    app_id: str | None = None
    api_secret: str | None = None


@dataclass(frozen=True)
class RerankRequestConfig:
    provider: str
    base_url: str
    api_key: str
    model: str
    workspace_id: str | None = None


@dataclass(frozen=True)
class RerankItem:
    index: int
    score: float


class EmbeddingProvider(Protocol):
    def embed_documents(
        self,
        config: EmbeddingRequestConfig,
        texts: list[str],
        timeout_seconds: float,
    ) -> list[list[float]]: ...

    def embed_query(
        self,
        config: EmbeddingRequestConfig,
        text: str,
        timeout_seconds: float,
    ) -> list[float]: ...


class RerankProvider(Protocol):
    def rerank(
        self,
        config: RerankRequestConfig,
        query: str,
        documents: list[str],
        top_n: int,
        timeout_seconds: float,
    ) -> list[RerankItem]: ...


class XfyunEmbeddingProvider:
    def __init__(self, transport: httpx.BaseTransport | None = None) -> None:
        self.transport = transport

    def embed_documents(
        self,
        config: EmbeddingRequestConfig,
        texts: list[str],
        timeout_seconds: float,
    ) -> list[list[float]]:
        return [self._embed_with_pooling(config, text, "para", timeout_seconds) for text in texts]

    def embed_query(
        self,
        config: EmbeddingRequestConfig,
        text: str,
        timeout_seconds: float,
    ) -> list[float]:
        return self._embed_with_pooling(config, text, "query", timeout_seconds)

    def _embed_with_pooling(
        self,
        config: EmbeddingRequestConfig,
        text: str,
        domain: str,
        timeout_seconds: float,
    ) -> list[float]:
        segments = split_utf8_bytes(text, XFYUN_MAX_INPUT_BYTES)
        if not segments:
            raise ModelProviderError("向量输入不能为空。", code="invalid_request")
        vectors = [self._embed_one(config, segment, domain, timeout_seconds) for segment in segments]
        pooled = [sum(values) / len(vectors) for values in zip(*vectors, strict=True)]
        return normalize_vector(pooled)

    def _embed_one(
        self,
        config: EmbeddingRequestConfig,
        text: str,
        domain: str,
        timeout_seconds: float,
    ) -> list[float]:
        if not config.app_id or not config.api_key or not config.api_secret:
            raise ModelProviderError("讯飞向量凭证不完整。", code="not_configured")
        url, headers = self._signed_request(config)
        message = json.dumps(
            {"messages": [{"role": "user", "content": text}]},
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        payload = {
            "header": {"app_id": config.app_id, "status": 3},
            "parameter": {"emb": {"domain": domain, "feature": {"encoding": "utf8", "compress": "raw", "format": "plain"}}},
            "payload": {"messages": {"encoding": "utf8", "compress": "raw", "format": "json", "status": 3, "text": base64.b64encode(message).decode("ascii")}},
        }
        response = self._post(url, headers, payload, timeout_seconds)
        if response.status_code >= 400:
            raise self._response_error(response)
        try:
            data = response.json()
            header = data.get("header") if isinstance(data, dict) else None
            code = int((header or {}).get("code", -1))
            if code != 0:
                raise ModelProviderError("讯飞向量服务拒绝了本次请求。", code="invalid_request")
            encoded = data["payload"]["feature"]["text"]
            raw = base64.b64decode(encoded, validate=True)
            if len(raw) != XFYUN_EMBEDDING_DIMENSION * 4:
                raise ValueError("unexpected vector bytes")
            vector = list(struct.unpack(f"<{XFYUN_EMBEDDING_DIMENSION}f", raw))
        except ModelProviderError:
            raise
        except (KeyError, TypeError, ValueError, struct.error) as exc:
            raise ModelProviderError("讯飞向量服务返回了无法解析的响应。", code="invalid_response", retryable=True) from exc
        return normalize_vector(vector)

    @staticmethod
    def _signed_request(config: EmbeddingRequestConfig) -> tuple[str, dict[str, str]]:
        parsed = urlparse(config.base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ModelProviderError("讯飞向量地址无效。", code="invalid_request")
        path = parsed.path or "/"
        date = format_datetime(datetime.now(UTC), usegmt=True)
        signature_origin = f"host: {parsed.netloc}\ndate: {date}\nPOST {path} HTTP/1.1"
        signature = base64.b64encode(
            hmac.new(config.api_secret.encode("utf-8"), signature_origin.encode("utf-8"), hashlib.sha256).digest()
        ).decode("ascii")
        authorization_origin = (
            f'api_key="{config.api_key}", algorithm="hmac-sha256", '
            f'headers="host date request-line", signature="{signature}"'
        )
        authorization = base64.b64encode(authorization_origin.encode("utf-8")).decode("ascii")
        query = urlencode({"host": parsed.netloc, "date": date, "authorization": authorization})
        return f"{parsed.scheme}://{parsed.netloc}{path}?{query}", {"Content-Type": "application/json"}

    def _post(self, url: str, headers: dict[str, str], payload: dict[str, Any], timeout_seconds: float) -> httpx.Response:
        kwargs: dict[str, Any] = {"timeout": timeout_seconds}
        if self.transport is not None:
            kwargs["transport"] = self.transport
        try:
            with httpx.Client(**kwargs) as client:
                return client.post(url, headers=headers, json=payload)
        except httpx.TimeoutException as exc:
            raise ModelProviderError("向量服务请求超时。", code="timeout", retryable=True) from exc
        except httpx.HTTPError as exc:
            raise ModelProviderError("向量服务暂不可用。", code="network_error", retryable=True) from exc

    @staticmethod
    def _response_error(response: httpx.Response) -> ModelProviderError:
        if response.status_code in {401, 403}:
            return ModelProviderError("向量服务认证失败。", code="authentication_failed")
        if response.status_code == 429:
            return ModelProviderError("向量服务请求过于频繁。", code="rate_limited", retryable=True)
        if response.status_code >= 500:
            return ModelProviderError("向量服务暂不可用。", code="provider_unavailable", retryable=True)
        return ModelProviderError("向量服务拒绝了本次请求。", code="invalid_request")


class HttpRerankProvider:
    def __init__(self, transport: httpx.BaseTransport | None = None) -> None:
        self.transport = transport

    def rerank(
        self,
        config: RerankRequestConfig,
        query: str,
        documents: list[str],
        top_n: int,
        timeout_seconds: float,
    ) -> list[RerankItem]:
        limited = documents[:20]
        if not limited:
            return []
        url = self._url(config)
        payload = {"model": config.model, "query": query, "documents": limited, "top_n": min(top_n, len(limited)), "return_documents": False}
        headers = {"Authorization": f"Bearer {config.api_key}", "Content-Type": "application/json"}
        kwargs: dict[str, Any] = {"timeout": timeout_seconds}
        if self.transport is not None:
            kwargs["transport"] = self.transport
        try:
            with httpx.Client(**kwargs) as client:
                response = client.post(url, headers=headers, json=payload)
        except httpx.TimeoutException as exc:
            raise ModelProviderError("重排序服务请求超时。", code="timeout", retryable=True) from exc
        except httpx.HTTPError as exc:
            raise ModelProviderError("重排序服务暂不可用。", code="network_error", retryable=True) from exc
        if response.status_code >= 400:
            raise self._response_error(response)
        try:
            data = response.json()
            raw_results = data.get("results") or data.get("data")
            items = [
                RerankItem(index=int(item["index"]), score=float(item.get("relevance_score", item.get("score"))))
                for item in raw_results
                if isinstance(item, dict)
            ]
        except (AttributeError, KeyError, TypeError, ValueError) as exc:
            raise ModelProviderError("重排序服务返回了无法解析的响应。", code="invalid_response", retryable=True) from exc
        if any(item.index < 0 or item.index >= len(limited) for item in items):
            raise ModelProviderError("重排序服务返回了无效索引。", code="invalid_response", retryable=True)
        return sorted(items, key=lambda item: (-item.score, item.index))[:top_n]

    @staticmethod
    def _url(config: RerankRequestConfig) -> str:
        base = config.base_url.rstrip("/")
        if config.provider == "bailian_rerank":
            parsed = urlparse(base)
            is_public_dashscope = parsed.hostname in {"dashscope.aliyuncs.com", "dashscope-intl.aliyuncs.com"}
            if "{workspace_id}" in base and not config.workspace_id:
                raise ModelProviderError("百炼重排序缺少 Workspace ID。", code="not_configured")
            if "{workspace_id}" in base:
                base = base.replace("{workspace_id}", config.workspace_id)
            elif not config.workspace_id and not is_public_dashscope:
                raise ModelProviderError("百炼重排序缺少 Workspace ID。", code="not_configured")
            return f"{base}/reranks"
        return f"{base}/rerank"

    @staticmethod
    def _response_error(response: httpx.Response) -> ModelProviderError:
        if response.status_code in {401, 403}:
            return ModelProviderError("重排序服务认证失败。", code="authentication_failed")
        if response.status_code == 429:
            return ModelProviderError("重排序服务请求过于频繁。", code="rate_limited", retryable=True)
        if response.status_code >= 500:
            return ModelProviderError("重排序服务暂不可用。", code="provider_unavailable", retryable=True)
        return ModelProviderError("重排序服务拒绝了本次请求。", code="invalid_request")


def split_utf8_bytes(text: str, max_bytes: int) -> list[str]:
    cleaned = text.strip()
    if not cleaned:
        return []
    chunks: list[str] = []
    current: list[str] = []
    current_size = 0
    for char in cleaned:
        encoded_size = len(char.encode("utf-8"))
        if current and current_size + encoded_size > max_bytes:
            chunks.append("".join(current))
            current = []
            current_size = 0
        current.append(char)
        current_size += encoded_size
    if current:
        chunks.append("".join(current))
    return chunks


def normalize_vector(vector: list[float]) -> list[float]:
    magnitude = math.sqrt(sum(value * value for value in vector))
    if not math.isfinite(magnitude) or magnitude <= 0:
        raise ModelProviderError("向量服务返回了无效向量。", code="invalid_response", retryable=True)
    return [float(value / magnitude) for value in vector]

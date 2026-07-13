from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Iterator

import httpx


class ModelProviderError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        code: str = "provider_unavailable",
        retryable: bool = False,
        retry_after_seconds: float | None = None,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable
        self.retry_after_seconds = retry_after_seconds
        self.status_code = status_code


@dataclass(frozen=True)
class OpenAICompatibleConfig:
    base_url: str
    api_key: str
    chat_model: str
    thinking_type: str | None = None


@dataclass(frozen=True)
class OpenAICompatibleEmbeddingConfig:
    base_url: str
    api_key: str
    embedding_model: str


class OpenAICompatibleChatProvider:
    def __init__(self, transport: httpx.BaseTransport | None = None) -> None:
        self.transport = transport

    def chat_completion(
        self,
        config: OpenAICompatibleConfig,
        messages: list[dict[str, str]],
        timeout_seconds: float,
    ) -> str:
        url = f"{config.base_url.rstrip('/')}/chat/completions"
        payload: dict[str, Any] = {
            "model": config.chat_model,
            "messages": messages,
            "temperature": 0.2,
        }
        if config.thinking_type in {"enabled", "disabled", "auto"}:
            payload["thinking"] = {"type": config.thinking_type}
        headers = {
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        }
        client_kwargs: dict[str, Any] = {"timeout": timeout_seconds}
        if self.transport is not None:
            client_kwargs["transport"] = self.transport

        try:
            with httpx.Client(**client_kwargs) as client:
                response = client.post(url, headers=headers, json=payload)
        except httpx.TimeoutException as exc:
            raise ModelProviderError("模型服务请求超时。", code="timeout", retryable=True) from exc
        except httpx.HTTPError as exc:
            raise ModelProviderError("模型服务暂不可用。", code="network_error", retryable=True) from exc

        if response.status_code >= 400:
            raise self._response_error(response)

        try:
            data = response.json()
        except ValueError as exc:
            raise ModelProviderError("模型服务返回了无法解析的响应。", code="invalid_response", retryable=True) from exc

        content = self._extract_content(data)
        if not content:
            raise ModelProviderError("模型服务没有返回可用内容。", code="invalid_response", retryable=True)
        return content

    def chat_completion_stream(
        self,
        config: OpenAICompatibleConfig,
        messages: list[dict[str, str]],
        timeout_seconds: float,
    ) -> Iterator[str]:
        url = f"{config.base_url.rstrip('/')}/chat/completions"
        payload: dict[str, Any] = {
            "model": config.chat_model,
            "messages": messages,
            "temperature": 0.2,
            "stream": True,
        }
        if config.thinking_type in {"enabled", "disabled", "auto"}:
            payload["thinking"] = {"type": config.thinking_type}
        headers = {
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        }
        client_kwargs: dict[str, Any] = {"timeout": timeout_seconds}
        if self.transport is not None:
            client_kwargs["transport"] = self.transport

        def generate() -> Iterator[str]:
            yielded_content = False
            try:
                with httpx.Client(**client_kwargs) as client:
                    with client.stream("POST", url, headers=headers, json=payload) as response:
                        if response.status_code >= 400:
                            raise self._response_error(response)

                        for line in response.iter_lines():
                            token = self._extract_stream_token(line)
                            if token is None:
                                continue
                            if token == "[DONE]":
                                break
                            yielded_content = True
                            yield token
            except httpx.TimeoutException as exc:
                code = "stream_interrupted" if yielded_content else "timeout"
                raise ModelProviderError(
                    "模型流式输出中断。" if yielded_content else "模型服务请求超时。",
                    code=code,
                    retryable=not yielded_content,
                ) from exc
            except httpx.HTTPError as exc:
                code = "stream_interrupted" if yielded_content else "network_error"
                raise ModelProviderError(
                    "模型流式输出中断。" if yielded_content else "模型服务暂不可用。",
                    code=code,
                    retryable=not yielded_content,
                ) from exc
            except ModelProviderError as exc:
                if yielded_content and exc.code != "stream_interrupted":
                    raise ModelProviderError("模型流式输出中断。", code="stream_interrupted", retryable=False) from exc
                raise

            if not yielded_content:
                raise ModelProviderError("模型服务没有返回可用内容。", code="invalid_response", retryable=True)

        return generate()

    def embed_texts(
        self,
        config: OpenAICompatibleEmbeddingConfig,
        texts: list[str],
        timeout_seconds: float,
        dimensions: int | None = None,
    ) -> list[list[float]]:
        url = f"{config.base_url.rstrip('/')}/embeddings"
        payload: dict[str, Any] = {
            "model": config.embedding_model,
            "input": texts,
        }
        if dimensions is not None:
            payload["dimensions"] = dimensions
        headers = {
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        }
        response = self._post_embedding_request(url, headers, payload, timeout_seconds)
        if response.status_code == 400:
            retry_payload = {key: value for key, value in payload.items() if key != "dimensions"}
            response = self._post_embedding_request(url, headers, retry_payload, timeout_seconds)

        if response.status_code >= 400:
            raise self._response_error(response)

        try:
            data = response.json()
        except ValueError as exc:
            raise ModelProviderError("模型服务返回了无法解析的响应。", code="invalid_response", retryable=True) from exc

        vectors = self._extract_embeddings(data)
        if not vectors:
            raise ModelProviderError("模型服务没有返回可用向量。", code="invalid_response", retryable=True)
        if len(vectors) != len(texts):
            raise ModelProviderError("模型服务返回了不匹配的向量维度。", code="invalid_response", retryable=True)
        actual_dimensions = {len(vector) for vector in vectors}
        if len(actual_dimensions) != 1 or 0 in actual_dimensions:
            raise ModelProviderError("模型服务返回了不一致的向量维度。", code="invalid_response", retryable=True)
        if dimensions is not None and actual_dimensions != {dimensions}:
            raise ModelProviderError("模型服务返回了不匹配的向量维度。", code="invalid_response", retryable=True)
        return vectors

    def _post_embedding_request(
        self,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        timeout_seconds: float,
    ) -> httpx.Response:
        client_kwargs: dict[str, Any] = {"timeout": timeout_seconds}
        if self.transport is not None:
            client_kwargs["transport"] = self.transport

        try:
            with httpx.Client(**client_kwargs) as client:
                return client.post(url, headers=headers, json=payload)
        except httpx.TimeoutException as exc:
            raise ModelProviderError("模型服务请求超时。", code="timeout", retryable=True) from exc
        except httpx.HTTPError as exc:
            raise ModelProviderError("模型服务暂不可用。", code="network_error", retryable=True) from exc

    @classmethod
    def _response_error(cls, response: httpx.Response) -> ModelProviderError:
        status_code = response.status_code
        if status_code in {401, 403}:
            return ModelProviderError("模型服务认证失败。", code="authentication_failed", status_code=status_code)
        if status_code == 429:
            return ModelProviderError(
                "模型服务请求过于频繁。",
                code="rate_limited",
                retryable=True,
                retry_after_seconds=cls._retry_after(response),
                status_code=status_code,
            )
        if status_code in {408, 504}:
            return ModelProviderError("模型服务请求超时。", code="timeout", retryable=True, status_code=status_code)
        if status_code >= 500:
            return ModelProviderError("模型服务暂不可用。", code="provider_unavailable", retryable=True, status_code=status_code)
        code = "context_too_long" if cls._is_context_error(response) else "invalid_request"
        message = "本次会话内容过长，请缩短问题或新建会话。" if code == "context_too_long" else "模型服务拒绝了本次请求。"
        return ModelProviderError(message, code=code, status_code=status_code)

    @staticmethod
    def _retry_after(response: httpx.Response) -> float | None:
        raw = response.headers.get("Retry-After")
        if not raw:
            return None
        try:
            return max(0.0, float(raw))
        except ValueError:
            return None

    @staticmethod
    def _is_context_error(response: httpx.Response) -> bool:
        try:
            payload = response.json()
            error = payload.get("error") if isinstance(payload, dict) else None
            text = json.dumps(error, ensure_ascii=False).lower()
        except ValueError:
            return False
        markers = ("context_length", "context window", "too many tokens", "maximum context", "上下文")
        return any(marker in text for marker in markers)

    @staticmethod
    def _extract_content(data: Any) -> str:
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            return ""
        if not isinstance(content, str):
            return ""
        return content.strip()

    @staticmethod
    def _extract_stream_token(line: str) -> str | None:
        stripped = line.strip()
        if not stripped or not stripped.startswith("data:"):
            return None
        raw_data = stripped.removeprefix("data:").strip()
        if raw_data == "[DONE]":
            return "[DONE]"

        try:
            data = json.loads(raw_data)
            content = data["choices"][0]["delta"].get("content")
        except (json.JSONDecodeError, KeyError, IndexError, TypeError, AttributeError) as exc:
            raise ModelProviderError("模型服务返回了无法解析的响应。", code="invalid_response", retryable=True) from exc
        if not isinstance(content, str):
            return None
        return content

    @staticmethod
    def _extract_embeddings(data: Any) -> list[list[float]]:
        try:
            items = data["data"]
        except (KeyError, TypeError):
            return []
        if not isinstance(items, list):
            return []

        indexed_vectors: list[tuple[int, list[float]]] = []
        for fallback_index, item in enumerate(items):
            if not isinstance(item, dict):
                return []
            raw_embedding = item.get("embedding")
            if not isinstance(raw_embedding, list):
                return []
            vector: list[float] = []
            for value in raw_embedding:
                if not isinstance(value, (int, float)):
                    return []
                vector.append(float(value))
            raw_index = item.get("index", fallback_index)
            try:
                index = int(raw_index)
            except (TypeError, ValueError):
                return []
            indexed_vectors.append((index, vector))

        indexed_vectors.sort(key=lambda item: item[0])
        return [vector for _index, vector in indexed_vectors]

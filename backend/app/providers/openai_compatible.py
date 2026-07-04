from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Iterator

import httpx


class ModelProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class OpenAICompatibleConfig:
    base_url: str
    api_key: str
    chat_model: str


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
            raise ModelProviderError("模型服务请求超时。") from exc
        except httpx.HTTPError as exc:
            raise ModelProviderError("模型服务暂不可用。") from exc

        if response.status_code in {401, 403}:
            raise ModelProviderError("模型服务认证失败。")
        if response.status_code >= 400:
            raise ModelProviderError("模型服务返回错误。")

        try:
            data = response.json()
        except ValueError as exc:
            raise ModelProviderError("模型服务返回了无法解析的响应。") from exc

        content = self._extract_content(data)
        if not content:
            raise ModelProviderError("模型服务没有返回可用内容。")
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
                        if response.status_code in {401, 403}:
                            raise ModelProviderError("模型服务认证失败。")
                        if response.status_code >= 400:
                            raise ModelProviderError("模型服务返回错误。")

                        for line in response.iter_lines():
                            token = self._extract_stream_token(line)
                            if token is None:
                                continue
                            if token == "[DONE]":
                                break
                            yielded_content = True
                            yield token
            except httpx.TimeoutException as exc:
                raise ModelProviderError("模型服务请求超时。") from exc
            except httpx.HTTPError as exc:
                raise ModelProviderError("模型服务暂不可用。") from exc

            if not yielded_content:
                raise ModelProviderError("模型服务没有返回可用内容。")

        return generate()

    def embed_texts(
        self,
        config: OpenAICompatibleEmbeddingConfig,
        texts: list[str],
        timeout_seconds: float,
        dimensions: int = 1536,
    ) -> list[list[float]]:
        url = f"{config.base_url.rstrip('/')}/embeddings"
        payload: dict[str, Any] = {
            "model": config.embedding_model,
            "input": texts,
            "dimensions": dimensions,
        }
        headers = {
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        }
        response = self._post_embedding_request(url, headers, payload, timeout_seconds)
        if response.status_code == 400:
            retry_payload = {key: value for key, value in payload.items() if key != "dimensions"}
            response = self._post_embedding_request(url, headers, retry_payload, timeout_seconds)

        if response.status_code in {401, 403}:
            raise ModelProviderError("模型服务认证失败。")
        if response.status_code >= 400:
            raise ModelProviderError("模型服务返回错误。")

        try:
            data = response.json()
        except ValueError as exc:
            raise ModelProviderError("模型服务返回了无法解析的响应。") from exc

        vectors = self._extract_embeddings(data)
        if not vectors:
            raise ModelProviderError("模型服务没有返回可用向量。")
        if len(vectors) != len(texts) or any(len(vector) != dimensions for vector in vectors):
            raise ModelProviderError("模型服务返回了不匹配的向量维度。")
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
            raise ModelProviderError("模型服务请求超时。") from exc
        except httpx.HTTPError as exc:
            raise ModelProviderError("模型服务暂不可用。") from exc

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
            raise ModelProviderError("模型服务返回了无法解析的响应。") from exc
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

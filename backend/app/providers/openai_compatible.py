from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
import re
from time import perf_counter
from typing import Any, Iterator

import httpx
from openai import (
    APIConnectionError,
    APIError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    OpenAI,
    RateLimitError,
)

from backend.app.providers.model_tasks import ModelTaskProfile


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
    reasoning_protocol: str = "none"
    task_profile: ModelTaskProfile | None = None


@dataclass(frozen=True)
class ModelCompletion:
    content: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    reasoning_tokens: int | None = None
    first_token_ms: int | None = None
    total_latency_ms: int | None = None


@dataclass(frozen=True)
class OpenAICompatibleEmbeddingConfig:
    base_url: str
    api_key: str
    embedding_model: str


@dataclass(frozen=True)
class NativeWebSearchResult:
    citations: list[dict[str, Any]]
    backend: str
    warning: str | None = None


class OpenAICompatibleChatProvider:
    """OpenAI-compatible adapter; EduNova remains responsible for runtime policy."""

    def __init__(self, transport: httpx.BaseTransport | None = None) -> None:
        self.transport = transport

    def chat_completion(
        self,
        config: OpenAICompatibleConfig,
        messages: list[dict[str, str]],
        timeout_seconds: float,
    ) -> str:
        return self.chat_completion_result(config, messages, timeout_seconds).content

    def chat_completion_result(
        self,
        config: OpenAICompatibleConfig,
        messages: list[dict[str, str]],
        timeout_seconds: float,
    ) -> ModelCompletion:
        started = perf_counter()
        try:
            with self._client(config.base_url, config.api_key, timeout_seconds) as client:
                request: dict[str, Any] = {
                    "model": config.chat_model,
                    "messages": messages,
                    "temperature": config.task_profile.temperature if config.task_profile else 0.2,
                }
                extra_body = self._thinking_body(config)
                if extra_body:
                    request["extra_body"] = extra_body
                if config.task_profile and config.task_profile.output_mode == "json_object":
                    request["response_format"] = {"type": "json_object"}
                response = client.chat.completions.create(
                    **request,  # type: ignore[arg-type]
                )
        except APIError as exc:
            raise self._sdk_error(exc) from exc

        if not hasattr(response, "choices"):
            raise ModelProviderError("模型服务返回了无法解析的响应。", code="invalid_response", retryable=True)
        content = response.choices[0].message.content if response.choices else None
        if not isinstance(content, str) or not content.strip():
            raise ModelProviderError("模型服务没有返回可用内容。", code="invalid_response", retryable=True)
        usage = getattr(response, "usage", None)
        details = getattr(usage, "completion_tokens_details", None) if usage is not None else None
        reasoning_tokens = getattr(details, "reasoning_tokens", None)
        if (
            reasoning_tokens is None
            and config.reasoning_protocol == "qwen_enable_thinking"
            and config.task_profile is not None
            and config.task_profile.reasoning == "disabled"
        ):
            reasoning_tokens = 0
        return ModelCompletion(
            content=content.strip(),
            input_tokens=getattr(usage, "prompt_tokens", None),
            output_tokens=getattr(usage, "completion_tokens", None),
            reasoning_tokens=reasoning_tokens,
            total_latency_ms=max(0, int((perf_counter() - started) * 1000)),
        )

    def vision_completion(
        self,
        config: OpenAICompatibleConfig,
        *,
        prompt: str,
        image_data_urls: list[str],
        timeout_seconds: float,
    ) -> str:
        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        content.extend(
            {
                "type": "image_url",
                "image_url": {"url": data_url},
            }
            for data_url in image_data_urls
        )
        try:
            with self._client(config.base_url, config.api_key, timeout_seconds) as client:
                request: dict[str, Any] = {
                    "model": config.chat_model,
                    "messages": [{"role": "user", "content": content}],
                    "temperature": config.task_profile.temperature if config.task_profile else 0.1,
                }
                extra_body = self._thinking_body(config)
                if extra_body:
                    request["extra_body"] = extra_body
                if config.task_profile and config.task_profile.output_mode == "json_object":
                    request["response_format"] = {"type": "json_object"}
                response = client.chat.completions.create(**request)  # type: ignore[arg-type]
        except APIError as exc:
            raise self._sdk_error(exc) from exc
        text = response.choices[0].message.content if response.choices else None
        if not isinstance(text, str) or not text.strip():
            raise ModelProviderError("图片理解服务没有返回可用内容。", code="invalid_response", retryable=True)
        return text.strip()

    def chat_completion_stream(
        self,
        config: OpenAICompatibleConfig,
        messages: list[dict[str, str]],
        timeout_seconds: float,
    ) -> Iterator[str]:
        def generate() -> Iterator[str]:
            yielded_content = False
            try:
                with self._client(config.base_url, config.api_key, timeout_seconds) as client:
                    stream = client.chat.completions.create(
                        model=config.chat_model,
                        messages=messages,  # type: ignore[arg-type]
                        temperature=0.2,
                        stream=True,
                        extra_body=self._thinking_body(config),
                    )
                    for chunk in stream:
                        token = chunk.choices[0].delta.content if chunk.choices else None
                        if not isinstance(token, str) or not token:
                            continue
                        yielded_content = True
                        yield token
            except APIError as exc:
                if yielded_content:
                    raise ModelProviderError("模型流式输出中断。", code="stream_interrupted", retryable=False) from exc
                raise self._sdk_error(exc) from exc
            except httpx.HTTPError as exc:
                if yielded_content:
                    raise ModelProviderError("模型流式输出中断。", code="stream_interrupted", retryable=False) from exc
                raise ModelProviderError("模型服务暂不可用。", code="network_error", retryable=True) from exc

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
        try:
            with self._client(config.base_url, config.api_key, timeout_seconds) as client:
                try:
                    response = client.embeddings.create(
                        model=config.embedding_model,
                        input=texts,
                        dimensions=dimensions,
                    )
                except BadRequestError:
                    if dimensions is None:
                        raise
                    response = client.embeddings.create(model=config.embedding_model, input=texts)
        except APIError as exc:
            raise self._sdk_error(exc) from exc

        vectors = [list(map(float, item.embedding)) for item in sorted(response.data, key=lambda item: item.index)]
        if not vectors or len(vectors) != len(texts):
            raise ModelProviderError("模型服务返回了不匹配的向量维度。", code="invalid_response", retryable=True)
        actual_dimensions = {len(vector) for vector in vectors}
        if len(actual_dimensions) != 1 or 0 in actual_dimensions:
            raise ModelProviderError("模型服务返回了不一致的向量维度。", code="invalid_response", retryable=True)
        if dimensions is not None and actual_dimensions != {dimensions}:
            raise ModelProviderError("模型服务返回了不匹配的向量维度。", code="invalid_response", retryable=True)
        return vectors

    def native_web_search(
        self,
        config: OpenAICompatibleConfig,
        *,
        query: str,
        timeout_seconds: float,
        native_kind: str,
        deep: bool = False,
        force: bool = False,
    ) -> NativeWebSearchResult:
        cleaned_query = " ".join(query.split())[:300]
        if not cleaned_query:
            return NativeWebSearchResult([], f"native_{native_kind}", "联网搜索问题为空。")
        try:
            with self._client(config.base_url, config.api_key, timeout_seconds) as client:
                if native_kind == "openai":
                    response = client.responses.create(
                        model=config.chat_model,
                        input=cleaned_query,
                        tools=[{"type": "web_search"}],  # type: ignore[list-item]
                        tool_choice="required" if force else "auto",
                        include=["web_search_call.action.sources"],
                    )
                elif native_kind == "spark":
                    response = client.chat.completions.create(
                        model=config.chat_model,
                        messages=[{"role": "user", "content": cleaned_query}],
                        temperature=0.2,
                        extra_body={
                            "tools": [
                                {
                                    "type": "web_search",
                                    "web_search": {"enable": True, "search_mode": "deep" if deep else "normal"},
                                }
                            ],
                            "tool_choice": "required" if force else "auto",
                            **(self._thinking_body(config) or {}),
                        },
                    )
                else:
                    return NativeWebSearchResult([], "none", "当前模型不支持厂商原生联网搜索。")
        except APIError as exc:
            error = self._sdk_error(exc)
            return NativeWebSearchResult([], f"native_{native_kind}", str(error))

        payload = response.model_dump(mode="json") if hasattr(response, "model_dump") else {}
        citations = self._native_search_citations(payload, backend=f"native_{native_kind}")
        if not citations:
            return NativeWebSearchResult(
                [],
                f"native_{native_kind}",
                "厂商原生搜索未返回可验证来源，已尝试外部搜索回退。",
            )
        return NativeWebSearchResult(citations, f"native_{native_kind}")

    def _client(self, base_url: str, api_key: str, timeout_seconds: float) -> OpenAI:
        http_client = httpx.Client(transport=self.transport, timeout=timeout_seconds)
        return OpenAI(
            base_url=f"{base_url.rstrip('/')}/",
            api_key=api_key,
            timeout=timeout_seconds,
            max_retries=0,
            http_client=http_client,
        )

    @classmethod
    def _native_search_citations(cls, payload: Any, *, backend: str) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []

        def visit(value: Any) -> None:
            if isinstance(value, dict):
                url = value.get("url") or value.get("source_url")
                if isinstance(url, str) and cls._is_http_url(url):
                    candidates.append(value)
                for child in value.values():
                    visit(child)
            elif isinstance(value, list):
                for child in value:
                    visit(child)

        visit(payload)
        seen: set[str] = set()
        citations: list[dict[str, Any]] = []
        for item in candidates:
            url = str(item.get("url") or item.get("source_url") or "").strip()
            if url in seen:
                continue
            seen.add(url)
            title = cls._clean_source_text(item.get("title") or item.get("name") or "联网来源", 120)
            snippet = cls._clean_source_text(
                item.get("snippet") or item.get("description") or item.get("text") or "",
                240,
            )
            citations.append(
                {
                    "source_type": "web",
                    "title": title,
                    "url": url[:500],
                    "snippet": snippet,
                    "search_backend": backend,
                    "evidence_role": "external_supplement",
                    "retrieved_at": datetime.now(UTC).isoformat(),
                }
            )
            if len(citations) >= 8:
                break
        return citations

    @staticmethod
    def _is_http_url(value: str) -> bool:
        return bool(re.match(r"^https?://[^\s]+$", value.strip(), flags=re.IGNORECASE))

    @staticmethod
    def _clean_source_text(value: Any, limit: int) -> str:
        return " ".join(str(value or "").split())[:limit]

    @staticmethod
    def _thinking_body(config: OpenAICompatibleConfig) -> dict[str, Any] | None:
        profile = config.task_profile
        if config.reasoning_protocol == "qwen_enable_thinking":
            if profile is not None:
                if profile.reasoning == "disabled":
                    return {"enable_thinking": False}
                if profile.reasoning == "deep":
                    return {"enable_thinking": True}
                return None
            # The tutoring stream uses ``auto`` for a normal (non-deep) turn.
            # Qwen's server default may enable thinking in that case, which
            # adds several seconds before the first visible token.  EduNova's
            # explicit deep-thinking switch is the product policy boundary:
            # only ``enabled`` opts into Qwen thinking; ``auto`` and
            # ``disabled`` keep routine chat fast and deterministic.
            if config.thinking_type in {"enabled", "disabled", "auto"}:
                return {"enable_thinking": config.thinking_type == "enabled"}
            return None
        if config.reasoning_protocol == "spark_thinking" and profile is not None:
            spark_type = "enabled" if profile.reasoning == "deep" else "disabled" if profile.reasoning == "disabled" else "auto"
            return {"thinking": {"type": spark_type}}
        if config.thinking_type in {"enabled", "disabled", "auto"}:
            return {"thinking": {"type": config.thinking_type}}
        return None

    @classmethod
    def _sdk_error(cls, exc: APIError) -> ModelProviderError:
        if isinstance(exc, APITimeoutError):
            return ModelProviderError("模型服务请求超时。", code="timeout", retryable=True)
        if isinstance(exc, APIConnectionError):
            return ModelProviderError("模型服务暂不可用。", code="network_error", retryable=True)
        status_code = exc.status_code if isinstance(exc, APIStatusError) else None
        if isinstance(exc, AuthenticationError) or status_code in {401, 403}:
            return ModelProviderError("模型服务认证失败。", code="authentication_failed", status_code=status_code)
        if isinstance(exc, RateLimitError) or status_code == 429:
            return ModelProviderError(
                "模型服务请求过于频繁。",
                code="rate_limited",
                retryable=True,
                retry_after_seconds=cls._retry_after(exc),
                status_code=status_code,
            )
        if status_code in {408, 504}:
            return ModelProviderError("模型服务请求超时。", code="timeout", retryable=True, status_code=status_code)
        if status_code is not None and status_code >= 500:
            return ModelProviderError("模型服务暂不可用。", code="provider_unavailable", retryable=True, status_code=status_code)
        if isinstance(exc, BadRequestError) and cls._is_context_error(exc):
            return ModelProviderError(
                "本次会话内容过长，请缩短问题或新建会话。",
                code="context_too_long",
                status_code=status_code,
            )
        if status_code is not None and status_code < 500:
            return ModelProviderError("模型服务拒绝了本次请求。", code="invalid_request", status_code=status_code)
        return ModelProviderError("模型服务返回了无法解析的响应。", code="invalid_response", retryable=True)

    @staticmethod
    def _retry_after(exc: APIError) -> float | None:
        response = getattr(exc, "response", None)
        raw = response.headers.get("Retry-After") if response is not None else None
        if not raw:
            return None
        try:
            return max(0.0, float(raw))
        except ValueError:
            return None

    @staticmethod
    def _is_context_error(exc: APIError) -> bool:
        text = json.dumps(getattr(exc, "body", None), ensure_ascii=False).lower()
        markers = ("context_length", "context window", "too many tokens", "maximum context", "上下文")
        return any(marker in text for marker in markers)

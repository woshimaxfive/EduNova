from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


class ModelProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class OpenAICompatibleConfig:
    base_url: str
    api_key: str
    chat_model: str


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

    @staticmethod
    def _extract_content(data: Any) -> str:
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            return ""
        if not isinstance(content, str):
            return ""
        return content.strip()

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlparse


NativeSearchKind = Literal["spark", "openai", "none"]
ToolSearchKind = Literal["native", "external_function"]
ReasoningProtocol = Literal["qwen_enable_thinking", "spark_thinking", "none"]
StructuredOutputKind = Literal["json_object", "prompt_only"]


@dataclass(frozen=True)
class ProviderCapabilities:
    native_search: NativeSearchKind = "none"
    search_tool: ToolSearchKind = "external_function"
    supports_thinking_control: bool = False
    reasoning_protocol: ReasoningProtocol = "none"
    structured_output: StructuredOutputKind = "prompt_only"
    verified_structured_output: bool = False
    supports_image_input: bool = False
    vision_protocol: Literal["openai_chat_completions", "none"] = "none"
    verified_vision: bool = False
    vision_mime_types: tuple[str, ...] = ()
    vision_max_images: int = 0
    vision_max_image_bytes: int = 0


def provider_capabilities(*, preset_id: str | None, base_url: str | None) -> ProviderCapabilities:
    preset = (preset_id or "").strip().lower()
    host = (urlparse(base_url or "").hostname or "").lower()
    if preset == "openai-vision":
        return ProviderCapabilities(
            native_search="openai",
            search_tool="native",
            supports_image_input=True,
            vision_protocol="openai_chat_completions",
            verified_vision=True,
            vision_mime_types=("image/png", "image/jpeg"),
            vision_max_images=3,
            vision_max_image_bytes=4 * 1024 * 1024,
        )
    if preset == "qwen" or host == "dashscope.aliyuncs.com":
        return ProviderCapabilities(
            supports_thinking_control=True,
            reasoning_protocol="qwen_enable_thinking",
            structured_output="json_object",
            verified_structured_output=True,
            supports_image_input=True,
            vision_protocol="openai_chat_completions",
            verified_vision=True,
            vision_mime_types=("image/png", "image/jpeg"),
            vision_max_images=3,
            vision_max_image_bytes=4 * 1024 * 1024,
        )
    if preset in {"hunyuan-vision", "custom-vision"}:
        return ProviderCapabilities(
            supports_image_input=True,
            vision_protocol="openai_chat_completions",
            verified_vision=False,
            vision_mime_types=("image/png", "image/jpeg"),
            vision_max_images=3,
            vision_max_image_bytes=4 * 1024 * 1024,
        )
    if preset == "spark" or host.endswith("spark-api-open.xf-yun.com"):
        return ProviderCapabilities(
            native_search="spark",
            search_tool="native",
            supports_thinking_control=True,
            reasoning_protocol="spark_thinking",
        )
    if preset == "openai" or host in {"api.openai.com", "openai.com"}:
        return ProviderCapabilities(
            native_search="openai",
            search_tool="native",
            structured_output="json_object",
            verified_structured_output=True,
        )
    return ProviderCapabilities()

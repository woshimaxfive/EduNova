from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlparse


NativeSearchKind = Literal["spark", "openai", "none"]
ToolSearchKind = Literal["native", "external_function"]


@dataclass(frozen=True)
class ProviderCapabilities:
    native_search: NativeSearchKind = "none"
    search_tool: ToolSearchKind = "external_function"
    supports_thinking_control: bool = False


def provider_capabilities(*, preset_id: str | None, base_url: str | None) -> ProviderCapabilities:
    preset = (preset_id or "").strip().lower()
    host = (urlparse(base_url or "").hostname or "").lower()
    if preset == "spark" or host.endswith("xf-yun.com"):
        return ProviderCapabilities(native_search="spark", search_tool="native", supports_thinking_control=True)
    if preset == "openai" or host in {"api.openai.com", "openai.com"}:
        return ProviderCapabilities(native_search="openai", search_tool="native")
    return ProviderCapabilities()

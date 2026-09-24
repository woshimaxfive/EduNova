from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit

import httpx

from backend.app.core.config import Settings, get_settings


@dataclass(frozen=True)
class WebSearchResult:
    citations: list[dict[str, Any]] = field(default_factory=list)
    warning: str | None = None


class WebSearchService:
    def __init__(self, settings: Settings | None = None, client: httpx.Client | None = None) -> None:
        self.settings = settings or get_settings()
        self.client = client

    @property
    def prefer_external_search(self) -> bool:
        # A local search selection must not silently invoke a billed model tool.
        return self.settings.web_search_provider.strip().lower() == "searxng"

    def search(self, query: str, max_results: int | None = None) -> WebSearchResult:
        cleaned_query = " ".join(query.split())
        if not cleaned_query:
            return WebSearchResult(warning="联网搜索问题为空。")
        provider = self.settings.web_search_provider.strip().lower()
        if provider not in {"tavily", "searxng"}:
            return WebSearchResult(warning="联网搜索提供方不受支持。")
        if provider == "tavily" and not self.settings.web_search_api_key.strip():
            return WebSearchResult(warning="联网搜索未配置。")

        limit = max(1, min(max_results or self.settings.web_search_max_results, 8))
        payload = {
            "api_key": self.settings.web_search_api_key,
            "query": cleaned_query,
            "max_results": limit,
            "include_answer": False,
        }

        try:
            response = self._searxng(cleaned_query) if provider == "searxng" else self._post(payload)
            response.raise_for_status()
            data = response.json()
        except Exception:
            return WebSearchResult(warning="联网搜索暂不可用。")

        citations = self._parse_results(data, limit)
        if not citations:
            return WebSearchResult(warning="联网搜索没有返回可用来源。")
        for citation in citations:
            citation["search_backend"] = provider
        warning = "部分搜索引擎暂不可用，以下来源可能不完整。" if (
            provider == "searxng" and isinstance(data, dict) and data.get("unresponsive_engines")
        ) else None
        return WebSearchResult(citations=citations, warning=warning)

    def _searxng(self, query: str) -> httpx.Response:
        # Endpoint is server configuration, never supplied by a user/model tool.
        payload = {"q": query[:2000], "format": "json", "categories": "general"}
        if self.client is not None:
            return self.client.post(self.settings.web_search_endpoint, data=payload, timeout=10,
                                    follow_redirects=False)
        with httpx.Client(timeout=10, follow_redirects=False) as client:
            return client.post(self.settings.web_search_endpoint, data=payload)

    def _post(self, payload: dict[str, Any]) -> httpx.Response:
        if self.client is not None:
            return self.client.post(self.settings.web_search_endpoint, json=payload, timeout=10)
        with httpx.Client(timeout=10) as client:
            return client.post(self.settings.web_search_endpoint, json=payload)

    @staticmethod
    def _parse_results(data: Any, limit: int) -> list[dict[str, str]]:
        if not isinstance(data, dict):
            return []
        raw_results = data.get("results")
        if not isinstance(raw_results, list):
            return []

        citations: list[dict[str, str]] = []
        seen: set[str] = set()
        for item in raw_results[:100]:
            if not isinstance(item, dict):
                continue
            title = WebSearchService._safe_text(item.get("title"), 120)
            url = WebSearchService._safe_text(item.get("url"), 300)
            try:
                parsed = urlsplit(url)
                if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
                    continue
            except ValueError:
                continue
            if url in seen:
                continue
            snippet = WebSearchService._safe_text(item.get("content") or item.get("snippet"), 240)
            if not title and not snippet:
                continue
            citations.append(
                {
                    "source_type": "web",
                    "title": title or url or "联网来源",
                    "url": url,
                    "snippet": snippet,
                    "search_backend": "external",
                    "evidence_role": "external_supplement",
                    "retrieved_at": datetime.now(UTC).isoformat(),
                }
            )
            seen.add(url)
            if len(citations) >= limit:
                break
        return citations

    @staticmethod
    def _safe_text(value: Any, limit: int) -> str:
        if value is None:
            return ""
        cleaned = " ".join(str(value).split())
        return cleaned[:limit]

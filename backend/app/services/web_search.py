from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx

from backend.app.core.config import Settings, get_settings


@dataclass(frozen=True)
class WebSearchResult:
    citations: list[dict[str, str]] = field(default_factory=list)
    warning: str | None = None


class WebSearchService:
    def __init__(self, settings: Settings | None = None, client: httpx.Client | None = None) -> None:
        self.settings = settings or get_settings()
        self.client = client

    def search(self, query: str, max_results: int | None = None) -> WebSearchResult:
        cleaned_query = " ".join(query.split())
        if not cleaned_query:
            return WebSearchResult(warning="联网搜索问题为空。")
        if not self.settings.web_search_api_key.strip():
            return WebSearchResult(warning="联网搜索未配置。")

        limit = max(1, min(max_results or self.settings.web_search_max_results, 8))
        payload = {
            "api_key": self.settings.web_search_api_key,
            "query": cleaned_query,
            "max_results": limit,
            "include_answer": False,
        }

        try:
            response = self._post(payload)
            response.raise_for_status()
            data = response.json()
        except Exception:
            return WebSearchResult(warning="联网搜索暂不可用。")

        citations = self._parse_results(data, limit)
        if not citations:
            return WebSearchResult(warning="联网搜索没有返回可用来源。")
        return WebSearchResult(citations=citations)

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
        for item in raw_results[:limit]:
            if not isinstance(item, dict):
                continue
            title = WebSearchService._safe_text(item.get("title"), 120)
            url = WebSearchService._safe_text(item.get("url"), 300)
            snippet = WebSearchService._safe_text(item.get("content") or item.get("snippet"), 240)
            if not title and not snippet:
                continue
            citations.append(
                {
                    "source_type": "web",
                    "title": title or url or "联网来源",
                    "url": url,
                    "snippet": snippet,
                }
            )
        return citations

    @staticmethod
    def _safe_text(value: Any, limit: int) -> str:
        if value is None:
            return ""
        cleaned = " ".join(str(value).split())
        return cleaned[:limit]

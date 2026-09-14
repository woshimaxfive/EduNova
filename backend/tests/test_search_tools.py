from __future__ import annotations

from backend.app.agents.search_tools import SearchToolExecutor
from backend.app.providers.capabilities import provider_capabilities
from backend.app.services.web_search import WebSearchResult


class FakeSearchService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int | None]] = []

    def search(self, query: str, max_results: int | None = None) -> WebSearchResult:
        self.calls.append((query, max_results))
        return WebSearchResult(citations=[{"title": "来源", "url": "https://example.test/source"}])


def test_provider_capability_registry_is_conservative_for_compatible_endpoints() -> None:
    assert provider_capabilities(preset_id="spark", base_url="https://spark-api-open.xf-yun.com/v1").native_search == "spark"
    assert provider_capabilities(preset_id="openai", base_url="https://api.openai.com/v1").native_search == "openai"
    assert provider_capabilities(preset_id="deepseek", base_url="https://api.deepseek.com/v1").native_search == "none"
    assert provider_capabilities(preset_id=None, base_url="https://compatible.example/v1").native_search == "none"


def test_external_search_runs_through_langgraph_tool_node_once() -> None:
    service = FakeSearchService()

    result = SearchToolExecutor(service).search("最新课程资料", max_results=5)

    assert service.calls == [("最新课程资料", 5)]
    assert result["warning"] is None
    assert result["citations"][0]["url"] == "https://example.test/source"


def test_invalid_search_input_does_not_call_external_service_or_invent_evidence() -> None:
    service = FakeSearchService()
    result = SearchToolExecutor(service).search("")
    assert not service.calls
    assert result["citations"] == [] and result["warning"]

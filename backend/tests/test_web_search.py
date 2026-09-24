from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest

from backend.app.core.config import Settings
from backend.app.services.web_search import WebSearchService
from backend.app.services.tutor_context import TutorContextMixin


def service(handler, **kwargs):
    return WebSearchService(Settings(_env_file=None, web_search_provider="searxng",
                                    web_search_endpoint="http://searxng:8080/search", **kwargs),
                            httpx.Client(transport=httpx.MockTransport(handler)))


def test_searxng_never_sends_key_and_filters_invalid_duplicate_sources():
    def handler(request):
        assert request.method == "POST" and request.url.host == "searxng"
        assert b"format=json" in request.content and b"synthetic-secret" not in request.content
        return httpx.Response(200, json={"results": [
            {"title": "bad", "url": "javascript:alert(1)"},
            {"title": "good", "url": "https://docs.python.org/3/", "content": "文档"},
            {"title": "duplicate", "url": "https://docs.python.org/3/"},
            {"title": "other", "url": "https://example.org/"},
        ], "unresponsive_engines": [["test", "timeout"]]})
    result = service(handler, web_search_api_key="synthetic-secret").search("学习 Python", 2)
    assert len(result.citations) == 2 and result.warning
    assert all(c["search_backend"] == "searxng" for c in result.citations)
    assert all(c["evidence_role"] == "external_supplement" for c in result.citations)


@pytest.mark.parametrize("response", [httpx.Response(403), httpx.Response(200, text="not-json"),
                                     httpx.Response(200, json={"results": []})])
def test_searxng_failure_is_visible_without_paid_fallback(response):
    calls = []
    def handler(request):
        calls.append(request)
        return response
    result = service(handler).search("测试")
    assert result.warning and not result.citations and len(calls) == 1


def test_tutor_local_selection_does_not_invoke_native_model_search():
    native = Mock()
    context = SimpleNamespace(native_web_search_provider=native,
                              web_search_service=service(lambda _: httpx.Response(503)))
    warnings = []
    assert TutorContextMixin._web_search_citations(context, "测试", warnings, user=object()) == []
    native.native_web_search.assert_not_called()
    assert warnings


def test_retired_paid_search_never_calls_network_or_native_fallback():
    client = Mock()
    search = WebSearchService(Settings(_env_file=None, web_search_provider="tavily",
                                      web_search_api_key="retired-synthetic-key"), client)
    result = search.search("测试")
    assert "仅支持免Key" in result.warning
    client.post.assert_not_called()
    native = Mock()
    context = SimpleNamespace(native_web_search_provider=native, web_search_service=search)
    assert TutorContextMixin._web_search_citations(context, "测试", [], user=object()) == []
    native.native_web_search.assert_not_called()


def test_default_search_needs_no_api_key(monkeypatch):
    monkeypatch.delenv("WEB_SEARCH_PROVIDER", raising=False)
    monkeypatch.delenv("WEB_SEARCH_ENDPOINT", raising=False)
    settings = Settings(_env_file=None)
    assert settings.web_search_provider == "searxng"
    calls = []
    def handler(request):
        calls.append(request)
        assert request.url.host == "searxng" and b"api_key" not in request.content
        return httpx.Response(200, json={"results": [{"title": "文档", "url": "https://docs.python.org/"}]})
    search = WebSearchService(settings, httpx.Client(transport=httpx.MockTransport(handler)))
    assert search.search("Python").citations and len(calls) == 1


def test_video_search_uses_dedicated_category_without_site_restriction():
    def handler(request):
        assert b"categories=videos" in request.content
        assert b"site%3A" not in request.content
        return httpx.Response(200, json={"results": []})
    assert service(handler).search_videos("Python 列表推导式").warning


def test_tutor_preserves_body_excerpt_and_failure_status():
    class Context(TutorContextMixin):
        native_web_search_provider = None
        web_search_service = service(lambda _: httpx.Response(200, json={"results": [
            {"title": "课程", "url": "https://example.org/", "content": "搜索摘要"},
            {"title": "课程2", "url": "https://example.net/", "content": "搜索摘要2"},
        ]}))

        @staticmethod
        def _safe_snippet(value, limit):
            return value[:limit]

    context = Context()
    def read_sources(items, query):
        return [{**items[0], "content": "正文依据", "read_status": "read"},
                {**items[1], "read_status": "http_error"}]
    context.web_search_service.read_sources = read_sources
    warnings = []
    citations = context._web_search_citations("学习", warnings)
    assert citations[0]["content"] == "正文依据" and citations[0]["snippet"] == "搜索摘要"
    assert "content" not in citations[1] and warnings

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


def test_tavily_still_requires_explicit_key():
    client = Mock()
    result = WebSearchService(Settings(_env_file=None, web_search_provider="tavily",
                                      web_search_api_key=""), client).search("测试")
    assert result.warning == "联网搜索未配置。"
    client.post.assert_not_called()

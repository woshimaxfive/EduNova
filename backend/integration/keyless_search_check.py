"""Live search smoke check. Sends only a fixed public learning question."""
from backend.app.services.web_search import WebSearchService


def run_check():
    service = WebSearchService()
    assert service.prefer_external_search, "Select SearXNG before running this check"
    result = service.search("Python 官方文档 列表推导式", max_results=3)
    assert result.citations, result.warning
    assert all(item["url"].startswith(("https://", "http://")) for item in result.citations)
    assert all(item["search_backend"] == "searxng" for item in result.citations)
    print({"sources": len(result.citations), "partial_warning": result.warning,
           "urls": [item["url"] for item in result.citations]})


if __name__ == "__main__":
    run_check()

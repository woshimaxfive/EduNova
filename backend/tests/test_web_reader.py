from unittest.mock import MagicMock, Mock

import httpcore
import pytest

from backend.app.services.web_reader import PublicNetworkBackend, WebPageReader, select_excerpt
from backend.app.services.video_resources import VideoCurationService
from backend.app.services.web_search import WebSearchResult


def reader_for(body, headers=b"Content-Type: text/html\r\n", status=b"200 OK"):
    wire = b"HTTP/1.1 " + status + b"\r\n" + headers
    wire += b"Content-Length: " + str(len(body)).encode() + b"\r\n\r\n" + body
    return WebPageReader(lambda: httpcore.ConnectionPool(network_backend=httpcore.MockBackend([wire])))


@pytest.mark.parametrize("url", ["http://127.0.0.1/", "http://169.254.169.254/", "http://[::1]/",
                                 "file:///etc/passwd", "https://user:pass@example.org/",
                                 "http://example.org:8080/", "http://[::ffff:127.0.0.1]/",
                                 "http://[ff02::1]/", "http://[64:ff9b::a00:1]/"])
def test_reader_rejects_nonpublic_or_credentialed_urls_before_network(url):
    pool = MagicMock()
    assert WebPageReader(pool).read(url).text == ""
    # A pool may be opened, but no stream request is sent.
    pool.return_value.__enter__.return_value.stream.assert_not_called()


def test_network_backend_rejects_mixed_private_dns_and_pins_public_address(monkeypatch):
    connect = Mock(return_value=object())
    monkeypatch.setattr(httpcore.SyncBackend, "connect_tcp", connect)
    monkeypatch.setattr("socket.getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("8.8.8.8", 443)),
                                                            (2, 1, 6, "", ("10.0.0.1", 443))])
    with pytest.raises(ValueError):
        PublicNetworkBackend().connect_tcp("example.org", 443)
    connect.assert_not_called()
    monkeypatch.setattr("socket.getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("8.8.8.8", 443))])
    PublicNetworkBackend().connect_tcp("example.org", 443)
    assert connect.call_args.args[:2] == ("8.8.8.8", 443)


def test_ip_pinning_keeps_original_tls_hostname_and_host_header(monkeypatch):
    class Stream(httpcore.MockStream):
        server_name = None
        written = b""

        def start_tls(self, ssl_context, server_hostname=None, timeout=None):
            self.server_name = server_hostname
            return self

        def write(self, buffer, timeout=None):
            self.written += buffer

    stream = Stream([b"HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n"])
    monkeypatch.setattr(httpcore.SyncBackend, "connect_tcp", lambda *a, **k: stream)
    monkeypatch.setattr("socket.getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("8.8.8.8", 443))])
    with httpcore.ConnectionPool(network_backend=PublicNetworkBackend()) as pool:
        assert pool.request("GET", "https://example.org/").status == 200
    assert stream.server_name == "example.org"
    assert b"Host: example.org" in stream.written


def test_reader_extracts_realistic_learning_html_without_script_or_navigation():
    text = "层序遍历使用队列，从根节点开始逐层访问左右子节点。" * 12
    body = f"<html><body><nav>登录 注册</nav><article><h1>二叉树</h1><p>{text}</p></article><script>secret()</script></body></html>".encode()
    result = reader_for(body).read("https://example.org/", "层序遍历")
    assert result.status == "read" and "层序遍历使用队列" in result.text
    assert "secret()" not in result.text


@pytest.mark.parametrize("body,headers,status,expected", [
    (b"x", b"Content-Type: application/pdf\r\n", b"200 OK", "unsupported_type"),
    (b"x", b"Content-Type: text/html\r\nContent-Encoding: gzip\r\n", b"200 OK", "unsupported_encoding"),
    (b"x" * 1_000_001, b"Content-Type: text/html\r\n", b"200 OK", "too_large"),
    (b"denied", b"Content-Type: text/html\r\n", b"403 Forbidden", "http_error"),
    (b"", b"Location: http://127.0.0.1/admin\r\n", b"302 Found", "unavailable"),
], ids=["pdf", "compressed", "oversized", "forbidden", "private_redirect"])
def test_reader_failure_boundaries(body, headers, status, expected):
    result = reader_for(body, headers, status).read("https://example.org/")
    assert result.status == expected and not result.text


def test_excerpt_finds_relevant_late_paragraph_without_inventing_text():
    text = "无关前文。" * 500 + "\n列表推导式使用表达式创建列表。"
    excerpt = select_excerpt(text, "列表推导式")
    assert "列表推导式使用表达式创建列表。" in excerpt and len(excerpt) <= 1800


def test_video_category_prefers_valid_related_bilibili_and_avoids_general_search():
    search = Mock()
    search.search_videos.return_value = WebSearchResult(citations=[
        {"title": "Python 列表推导式", "url": "https://www.youtube.com/watch?v=pGhMxGZYRPU"},
        {"title": "Python 列表推导式", "url": "https://www.bilibili.com/video/BV1b54y117KG/?tracking=1"},
        {"title": "Python 列表推导式", "url": "https://invalid.org/"},
    ])
    result = VideoCurationService(search).curate(topic="Python 列表推导式", profile_summary={})
    assert result.platform == "bilibili" and "tracking" not in result.watch_url
    search.search.assert_not_called()


def test_video_empty_category_still_uses_existing_general_search():
    search = Mock()
    search.search_videos.return_value = WebSearchResult()
    search.search.return_value = WebSearchResult(citations=[
        {"title": "二叉树层序遍历", "url": "https://www.bilibili.com/video/BV1b54y117KG/"}])
    assert VideoCurationService(search).curate(topic="二叉树层序遍历", profile_summary={}).platform == "bilibili"
    search.search.assert_called_once()

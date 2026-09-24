"""Bounded public-page reading; extraction and HTTP remain upstream implementations."""
from __future__ import annotations

import ipaddress
import re
import socket
import time
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

import httpcore
from trafilatura import extract


def is_public_address(value: str) -> bool:
    address = ipaddress.ip_address(value)
    if isinstance(address, ipaddress.IPv6Address):
        # Do not permit transition addresses to tunnel a non-public IPv4 destination.
        if (address.ipv4_mapped or address.sixtofour or address.teredo
                or address in ipaddress.ip_network("64:ff9b::/96")):
            return False
    return address.is_global and not address.is_multicast


class PublicNetworkBackend(httpcore.SyncBackend):
    def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        ips = list(dict.fromkeys(item[4][0] for item in addresses))
        if not ips or any(not is_public_address(ip) for ip in ips):
            raise ValueError("Only public addresses are allowed")
        # Connect to the checked numeric address: no second hostname lookup / DNS rebinding.
        # HTTPCore retains the original hostname for Host, SNI and certificate validation.
        return super().connect_tcp(ips[0], port, timeout=timeout,
                                   local_address=local_address, socket_options=socket_options)


@dataclass(frozen=True)
class PageRead:
    text: str = ""
    status: str = "unavailable"


class WebPageReader:
    MAX_BYTES = 1_000_000

    def __init__(self, pool_factory=None):
        self.pool_factory = pool_factory or (
            lambda: httpcore.ConnectionPool(network_backend=PublicNetworkBackend(), retries=0)
        )

    @staticmethod
    def validate_url(url: str) -> None:
        parsed = urlsplit(url)
        if (parsed.scheme not in {"http", "https"} or not parsed.hostname
                or parsed.username is not None or parsed.password is not None
                or parsed.port not in {None, 80, 443} or "%" in parsed.hostname):
            raise ValueError("Unsupported public URL")
        try:
            address = ipaddress.ip_address(parsed.hostname)
        except ValueError:
            return  # Hostnames are resolved and checked at the actual connection boundary.
        if not is_public_address(str(address)):
            raise ValueError("Non-public URL")

    def read(self, url: str, query: str = "") -> PageRead:
        deadline = time.monotonic() + 6
        try:
            with self.pool_factory() as pool:
                for _ in range(3):
                    self.validate_url(url)
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        return PageRead(status="timeout")
                    with pool.stream("GET", url, headers={
                        "User-Agent": "EduNova/1.0 (learning source reader)",
                        "Accept": "text/html,application/xhtml+xml,text/plain",
                        "Accept-Encoding": "identity",
                    }, extensions={"timeout": dict.fromkeys(
                        ("connect", "read", "write", "pool"), min(2, remaining)
                    )}) as response:
                        headers = {k.lower(): v for k, v in response.headers}
                        if response.status in {301, 302, 303, 307, 308}:
                            url = urljoin(url, headers.get(b"location", b"").decode("utf-8"))
                            continue
                        if response.status != 200:
                            return PageRead(status="http_error")
                        mime = headers.get(b"content-type", b"").split(b";", 1)[0].strip().lower()
                        if mime not in {b"text/html", b"application/xhtml+xml", b"text/plain"}:
                            return PageRead(status="unsupported_type")
                        if headers.get(b"content-encoding", b"identity").lower() not in {b"identity", b""}:
                            return PageRead(status="unsupported_encoding")
                        data = bytearray()
                        for chunk in response.iter_stream():
                            if time.monotonic() > deadline:
                                return PageRead(status="timeout")
                            if len(data) + len(chunk) > self.MAX_BYTES:
                                return PageRead(status="too_large")
                            data.extend(chunk)
                        text = (bytes(data).decode("utf-8", errors="replace") if mime == b"text/plain"
                                else extract(bytes(data), include_comments=False,
                                             include_tables=True, no_fallback=False))
                        if not text or len(text.strip()) < 80:
                            return PageRead(status="no_text")
                        return PageRead(text=select_excerpt(text, query), status="read")
            return PageRead(status="redirect_limit")
        except (ValueError, OSError, httpcore.NetworkError, httpcore.ProtocolError, httpcore.TimeoutException):
            return PageRead()


def select_excerpt(text: str, query: str) -> str:
    """Select verbatim paragraphs; never synthesize claims from search snippets."""
    paragraphs = [line.strip() for line in text[:100_000].splitlines() if line.strip()]
    terms = set(re.findall(r"[a-z0-9_]{2,}|[一-龥]{2,}", query.casefold()))
    ranked = sorted(enumerate(paragraphs), key=lambda pair: (
        -sum(term in pair[1].casefold() for term in terms), pair[0]
    ))
    selected = []
    length = 0
    for index, paragraph in ranked:
        if length >= 1800:
            break
        fragment = paragraph[:1800 - length]
        selected.append((index, fragment))
        length += len(fragment) + 1
    return "\n".join(p for _, p in sorted(selected))[:1800]

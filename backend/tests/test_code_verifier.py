from __future__ import annotations

import json

import httpx

from backend.app.services.code_verifier import HttpCodeVerifier


def test_code_verifier_returns_only_safe_execution_summary() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"ok": True, "code": "passed", "message": "完成", "outputLength": 3})

    result = HttpCodeVerifier(
        "http://code-verifier:8090",
        timeout_seconds=8,
        transport=httpx.MockTransport(handler),
    ).verify("print(123)", "123")

    assert result.ok is True
    assert result.safe_summary() == {"status": "passed", "code": "passed", "output_length": 3}
    assert captured == {
        "url": "http://code-verifier:8090/verify",
        "body": {"code": "print(123)", "expectedOutput": "123"},
    }


def test_code_verifier_fails_closed_when_runtime_is_missing_or_unavailable() -> None:
    assert HttpCodeVerifier("").verify("print(1)", "1").code == "runtime_unavailable"

    def unavailable(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("private provider detail must not escape")

    result = HttpCodeVerifier(
        "http://code-verifier:8090",
        transport=httpx.MockTransport(unavailable),
    ).verify("print(1)", "1")

    assert result.ok is False
    assert result.code == "runtime_unavailable"
    assert "private provider detail" not in result.message


def test_code_verifier_rejects_invalid_runtime_payload() -> None:
    result = HttpCodeVerifier(
        "http://code-verifier:8090",
        transport=httpx.MockTransport(lambda _request: httpx.Response(200, json=["unexpected"])),
    ).verify("print(1)", "1")

    assert result.ok is False
    assert result.code == "invalid_response"

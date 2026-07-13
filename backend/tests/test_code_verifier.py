from __future__ import annotations

import json
from urllib.error import URLError

from backend.app.services.code_verifier import HttpCodeVerifier


class FakeResponse:
    def __init__(self, payload: object) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload, ensure_ascii=False).encode("utf-8")


def test_code_verifier_returns_only_safe_execution_summary(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse({"ok": True, "code": "passed", "message": "完成", "outputLength": 3})

    monkeypatch.setattr("backend.app.services.code_verifier.urlopen", fake_urlopen)
    result = HttpCodeVerifier("http://code-verifier:8090", timeout_seconds=8).verify("print(123)", "123")

    assert result.ok is True
    assert result.safe_summary() == {"status": "passed", "code": "passed", "output_length": 3}
    assert captured == {
        "url": "http://code-verifier:8090/verify",
        "timeout": 8,
        "body": {"code": "print(123)", "expectedOutput": "123"},
    }


def test_code_verifier_fails_closed_when_runtime_is_missing_or_unavailable(monkeypatch) -> None:
    assert HttpCodeVerifier("").verify("print(1)", "1").code == "runtime_unavailable"

    def unavailable(*_args, **_kwargs):
        raise URLError("private provider detail must not escape")

    monkeypatch.setattr("backend.app.services.code_verifier.urlopen", unavailable)
    result = HttpCodeVerifier("http://code-verifier:8090").verify("print(1)", "1")

    assert result.ok is False
    assert result.code == "runtime_unavailable"
    assert "private provider detail" not in result.message


def test_code_verifier_rejects_invalid_runtime_payload(monkeypatch) -> None:
    monkeypatch.setattr(
        "backend.app.services.code_verifier.urlopen",
        lambda *_args, **_kwargs: FakeResponse(["unexpected"]),
    )

    result = HttpCodeVerifier("http://code-verifier:8090").verify("print(1)", "1")

    assert result.ok is False
    assert result.code == "invalid_response"

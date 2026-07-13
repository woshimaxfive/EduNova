from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class CodeVerificationResult:
    ok: bool
    code: str
    message: str
    output_length: int = 0

    def safe_summary(self) -> dict[str, object]:
        return {
            "status": "passed" if self.ok else "failed",
            "code": self.code,
            "output_length": self.output_length,
        }


class CodeVerifier(Protocol):
    def verify(self, code: str, expected_output: str) -> CodeVerificationResult: ...


class HttpCodeVerifier:
    def __init__(self, base_url: str, *, timeout_seconds: float = 40.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def verify(self, code: str, expected_output: str) -> CodeVerificationResult:
        if not self.base_url:
            return CodeVerificationResult(False, "runtime_unavailable", "代码验证服务未配置。")
        body = json.dumps({"code": code, "expectedOutput": expected_output}, ensure_ascii=False).encode("utf-8")
        request = Request(
            f"{self.base_url}/verify",
            data=body,
            headers={"content-type": "application/json; charset=utf-8"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, ValueError):
            return CodeVerificationResult(False, "runtime_unavailable", "代码验证服务暂不可用。")
        if not isinstance(payload, dict):
            return CodeVerificationResult(False, "invalid_response", "代码验证服务响应无效。")
        return CodeVerificationResult(
            ok=payload.get("ok") is True,
            code=str(payload.get("code") or "invalid_response")[:80],
            message=str(payload.get("message") or "代码验证已完成。")[:200],
            output_length=int(payload.get("outputLength") or 0),
        )

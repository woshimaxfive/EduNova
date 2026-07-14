from __future__ import annotations

from http import HTTPStatus
from typing import Any
from uuid import uuid4

from fastapi import Request
from fastapi.responses import JSONResponse

from backend.app.core.errors import DomainError


class ApiError(DomainError):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details=details)
        self.status_code = status_code
        self.code = code


def make_trace_id() -> str:
    return f"trace_{uuid4().hex[:12]}"


def api_response(data: Any) -> dict[str, Any]:
    return {
        "data": data,
        "trace_id": make_trace_id(),
    }


async def api_error_handler(_request: Request, exc: DomainError) -> JSONResponse:
    status_phrase = HTTPStatus(exc.status_code).phrase
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message or status_phrase,
                "details": exc.details,
            },
            "trace_id": make_trace_id(),
        },
    )

from __future__ import annotations

import json
from collections.abc import AsyncIterable, Iterable
from typing import Any

from sse_starlette import EventSourceResponse, ServerSentEvent


DEFAULT_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",
}


def sse_event(event: str, data: Any) -> ServerSentEvent:
    """Encode one application event without exposing SSE framing to callers."""
    return ServerSentEvent(
        event=event,
        data=json.dumps(data, ensure_ascii=False, separators=(",", ":")),
    )


def event_source_response(
    content: AsyncIterable[ServerSentEvent] | Iterable[ServerSentEvent],
) -> EventSourceResponse:
    return EventSourceResponse(
        content,
        headers=DEFAULT_SSE_HEADERS,
        ping=15,
        send_timeout=30,
    )

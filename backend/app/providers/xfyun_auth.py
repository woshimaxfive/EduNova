from __future__ import annotations

import base64
from datetime import UTC, datetime
from email.utils import format_datetime
import hashlib
import hmac
from urllib.parse import urlencode, urlparse


class XfyunAuthError(ValueError):
    pass


def build_xfyun_signed_url(base_url: str, api_key: str, api_secret: str) -> str:
    parsed = urlparse(base_url)
    if parsed.scheme not in {"ws", "wss"} or not parsed.netloc:
        raise XfyunAuthError("讯飞 WebSocket 地址无效。")
    path = parsed.path or "/"
    date = format_datetime(datetime.now(UTC), usegmt=True)
    signature_origin = f"host: {parsed.netloc}\ndate: {date}\nGET {path} HTTP/1.1"
    signature = base64.b64encode(
        hmac.new(api_secret.encode(), signature_origin.encode(), hashlib.sha256).digest()
    ).decode("ascii")
    authorization_origin = (
        f'api_key="{api_key}", algorithm="hmac-sha256", '
        f'headers="host date request-line", signature="{signature}"'
    )
    authorization = base64.b64encode(authorization_origin.encode()).decode("ascii")
    query = urlencode({"authorization": authorization, "date": date, "host": parsed.netloc})
    return f"{parsed.scheme}://{parsed.netloc}{path}?{query}"

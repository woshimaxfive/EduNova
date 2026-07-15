from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import format_datetime
import hashlib
import hmac
import json
from urllib.parse import urlencode, urlparse

from websockets.exceptions import WebSocketException
from websockets.sync.client import connect

from backend.app.providers.openai_compatible import ModelProviderError


@dataclass(frozen=True)
class XfyunVisionConfig:
    base_url: str
    app_id: str
    api_key: str
    api_secret: str
    domain: str = "imagev3"


class XfyunVisionProvider:
    def vision_completion(
        self,
        config: XfyunVisionConfig,
        *,
        prompt: str,
        image_data_urls: list[str],
        timeout_seconds: float,
    ) -> str:
        if not config.app_id or not config.api_key or not config.api_secret:
            raise ModelProviderError("讯飞图片理解凭证不完整。", code="not_configured")
        if not image_data_urls:
            raise ModelProviderError("图片理解请求缺少图片。", code="invalid_request")
        signed_url = self._signed_url(config)
        messages: list[dict[str, str]] = []
        for image in image_data_urls[:3]:
            messages.append({"role": "user", "content": self._image_base64(image), "content_type": "image"})
        messages.append({"role": "user", "content": prompt, "content_type": "text"})
        payload = {
            "header": {"app_id": config.app_id, "uid": "edunova"},
            "parameter": {"chat": {"domain": config.domain, "temperature": 0.2, "max_tokens": 4096}},
            "payload": {"message": {"text": messages}},
        }
        chunks: list[str] = []
        try:
            with connect(signed_url, open_timeout=timeout_seconds, close_timeout=3) as websocket:
                websocket.send(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
                while True:
                    raw = websocket.recv(timeout=timeout_seconds)
                    data = json.loads(raw)
                    header = data.get("header") or {}
                    code = int(header.get("code", -1))
                    if code != 0:
                        raise self._provider_error(code)
                    choices = ((data.get("payload") or {}).get("choices") or {})
                    for item in choices.get("text") or []:
                        content = item.get("content")
                        if isinstance(content, str):
                            chunks.append(content)
                    if int(choices.get("status", header.get("status", 2))) == 2:
                        break
        except ModelProviderError:
            raise
        except TimeoutError as exc:
            raise ModelProviderError("图片理解服务请求超时。", code="timeout", retryable=True) from exc
        except (WebSocketException, OSError) as exc:
            raise ModelProviderError("图片理解服务暂不可用。", code="network_error", retryable=True) from exc
        except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            raise ModelProviderError("图片理解服务返回了无法解析的响应。", code="invalid_response", retryable=True) from exc
        result = "".join(chunks).strip()
        if not result:
            raise ModelProviderError("图片理解服务返回了空结果。", code="invalid_response", retryable=True)
        return result

    @staticmethod
    def _image_base64(data_url: str) -> str:
        encoded = data_url.split(",", 1)[1] if data_url.startswith("data:") and "," in data_url else data_url
        try:
            base64.b64decode(encoded, validate=True)
        except ValueError as exc:
            raise ModelProviderError("图片数据无效。", code="invalid_request") from exc
        return encoded

    @staticmethod
    def _signed_url(config: XfyunVisionConfig) -> str:
        parsed = urlparse(config.base_url)
        if parsed.scheme not in {"ws", "wss"} or not parsed.netloc:
            raise ModelProviderError("讯飞图片理解地址无效。", code="invalid_request")
        path = parsed.path or "/v2.1/image"
        date = format_datetime(datetime.now(UTC), usegmt=True)
        signature_origin = f"host: {parsed.netloc}\ndate: {date}\nGET {path} HTTP/1.1"
        signature = base64.b64encode(
            hmac.new(config.api_secret.encode(), signature_origin.encode(), hashlib.sha256).digest()
        ).decode("ascii")
        authorization_origin = (
            f'api_key="{config.api_key}", algorithm="hmac-sha256", '
            f'headers="host date request-line", signature="{signature}"'
        )
        authorization = base64.b64encode(authorization_origin.encode()).decode("ascii")
        query = urlencode({"authorization": authorization, "date": date, "host": parsed.netloc})
        return f"{parsed.scheme}://{parsed.netloc}{path}?{query}"

    @staticmethod
    def _provider_error(code: int) -> ModelProviderError:
        if code in {10005, 10006, 10007, 10019}:
            return ModelProviderError("图片理解服务认证失败。", code="authentication_failed")
        if code in {11200, 11201, 11202}:
            return ModelProviderError("图片理解服务请求过于频繁。", code="rate_limited", retryable=True)
        return ModelProviderError("图片理解服务拒绝了本次请求。", code="invalid_request")

"""Read provider catalogs without persisting credentials or probing model capabilities."""
from __future__ import annotations

import json
import time
from urllib.parse import urlsplit

import httpcore
from pydantic import BaseModel, Field, field_validator

from backend.app.services.model_settings_contracts import ModelSettingsValidationError
from backend.app.services.web_reader import PublicNetworkBackend


class ModelCatalogRequest(BaseModel):
    base_url: str = Field(min_length=1, max_length=500)
    api_key: str | None = Field(default=None, max_length=500, repr=False)

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str) -> str:
        value = value.strip().rstrip("/")
        parsed = urlsplit(value)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username is not None
                or parsed.password is not None or parsed.query or parsed.fragment):
            raise ValueError("获取模型列表需要 HTTPS 服务根地址或 API Base URL，不支持查询参数。")
        _ = parsed.port
        return value


class ModelCatalogResponse(BaseModel):
    models: list[str]


class ModelCatalogError(RuntimeError):
    pass


class ModelCatalogClient:
    def __init__(self, pool_factory=None):
        self.pool_factory = pool_factory or (
            lambda: httpcore.ConnectionPool(network_backend=PublicNetworkBackend(), retries=0)
        )

    def fetch(self, base_url: str, api_key: str) -> ModelCatalogResponse:
        # Preserve compatible-mode/custom prefixes. A bare host uses the usual /v1 prefix.
        path = urlsplit(base_url).path.rstrip("/")
        url = base_url.rstrip("/") + ("/models" if path else "/v1/models")
        deadline = time.monotonic() + 15
        try:
            with self.pool_factory() as pool:
                with pool.stream("GET", url, headers={
                    "Authorization": f"Bearer {api_key}", "Accept": "application/json",
                    "Accept-Encoding": "identity",
                }, extensions={"timeout": dict.fromkeys(("connect", "read", "write", "pool"), 5)}) as response:
                    if response.status in {401, 403}:
                        raise ModelCatalogError("供应商拒绝访问模型列表，请检查 Key 和权限。")
                    if response.status in {404, 405}:
                        raise ModelCatalogError("该地址不提供模型列表，请检查 Base URL，或手动填写模型名称。")
                    if response.status != 200:
                        raise ModelCatalogError("供应商暂时无法返回模型列表，请稍后重试或手动填写。")
                    content = bytearray()
                    for chunk in response.iter_stream():
                        content.extend(chunk)
                        if len(content) > 1_000_000 or time.monotonic() > deadline:
                            raise ModelCatalogError("模型列表响应过大或超时，请手动填写模型名称。")
                    payload = json.loads(content)
            entries = payload.get("data", payload.get("models")) if isinstance(payload, dict) else None
            if not isinstance(entries, list):
                raise ModelCatalogError("供应商返回的模型列表格式不受支持，请手动填写模型名称。")
            models = set()
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                model = entry.get("id") or entry.get("slug")
                if isinstance(model, str) and model.strip() and len(model.strip()) <= 120:
                    models.add(model.strip())
            return ModelCatalogResponse(models=sorted(models))
        except ModelCatalogError:
            raise
        except (httpcore.TimeoutException, TimeoutError) as exc:
            raise ModelCatalogError("获取模型列表超时，请稍后重试或手动填写。") from exc
        except (httpcore.NetworkError, httpcore.ProtocolError, ValueError, UnicodeError) as exc:
            # Never expose provider response bodies, request headers, or credentials.
            raise ModelCatalogError("无法读取模型列表，请确认公网 HTTPS 地址、网络和返回格式；本地服务请手动填写。") from exc


def personal_catalog_key(service, user, payload: ModelCatalogRequest) -> str:
    key = (payload.api_key or "").strip()
    if key:
        return key
    setting = service.repository.get_default_for_user(user.id)
    if setting is None or (setting.base_url or "").rstrip("/") != payload.base_url:
        raise ModelSettingsValidationError("请填写此地址的 API Key；更换地址后不能复用原服务商密钥。")
    key = service._decrypt_api_key(setting.api_key_ciphertext)
    if not key:
        raise ModelSettingsValidationError("请先填写 API Key。")
    return key

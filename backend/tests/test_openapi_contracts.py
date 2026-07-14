from __future__ import annotations

from backend.app.main import app


STREAM_OR_DOWNLOAD_SUFFIXES = ("/events", "/messages/stream", "/download")


def test_all_json_operations_have_bounded_response_schemas() -> None:
    spec = app.openapi()
    missing: list[str] = []
    wide: list[str] = []
    for path, path_item in spec["paths"].items():
        for method, operation in path_item.items():
            if method not in {"get", "post", "put", "patch", "delete"}:
                continue
            if path.endswith(STREAM_OR_DOWNLOAD_SUFFIXES):
                continue
            responses = operation.get("responses", {})
            success = responses.get("200") or responses.get("202")
            schema = (success or {}).get("content", {}).get("application/json", {}).get("schema")
            key = f"{method.upper()} {path}"
            if not schema:
                missing.append(key)
            elif schema.get("additionalProperties") is True:
                wide.append(key)
    assert missing == []
    assert wide == []


def test_business_routes_publish_structured_error_envelope() -> None:
    spec = app.openapi()
    operation = spec["paths"]["/api/v1/courses/{course_id}"]["get"]
    schema = operation["responses"]["404"]["content"]["application/json"]["schema"]
    assert schema["$ref"].endswith("/ApiErrorEnvelope")

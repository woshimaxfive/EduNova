from __future__ import annotations

from backend.app.main import app


STREAM_OR_DOWNLOAD_SUFFIXES = ("/events", "/messages/stream", "/download", "/content")


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
            success_code, success = next(
                ((code, response) for code, response in responses.items() if str(code).isdigit() and 200 <= int(code) < 300),
                (None, None),
            )
            if success_code == "204":
                continue
            content = (success or {}).get("content", {})
            if content and "application/json" not in content:
                continue
            schema = content.get("application/json", {}).get("schema")
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

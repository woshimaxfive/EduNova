from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from httpx import ASGITransport, AsyncClient
import pytest

from backend.app.desktop_app import DesktopApplication, create_app


@pytest.fixture
def desktop(tmp_path: Path):
    build = tmp_path / "中文 前端"
    (build / "assets").mkdir(parents=True)
    (build / "pyodide" / "0.29.2").mkdir(parents=True)
    (build / "index.html").write_text("<!doctype html><title>EduNova</title>", encoding="utf-8")
    (build / "assets" / "app.js").write_text("export const ready = true;", encoding="utf-8")
    (build / "pyodide" / "0.29.2" / "python.wasm").write_bytes(b"\x00asm\x01\x00\x00\x00")
    (tmp_path / "private.txt").write_text("outside build", encoding="utf-8")
    api = FastAPI()

    @api.get("/api/health")
    async def health():
        return {"status": "ok"}

    @api.get("/api/v1/private")
    async def private():
        raise HTTPException(status_code=401, detail="authentication required")

    @api.get("/api/v1/events")
    async def events():
        return StreamingResponse(iter(["data: first\n\n", "data: done\n\n"]), media_type="text/event-stream")

    return DesktopApplication(api, build), build


@pytest.mark.asyncio
async def test_frontend_navigation_assets_and_wasm(desktop):
    app, _ = desktop
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://127.0.0.1") as client:
        for path in ("/", "/login", "/app/courses/12", "/app/settings"):
            response = await client.get(path, headers={"accept": "text/html"})
            assert response.status_code == 200
            assert "<title>EduNova</title>" in response.text
        script = await client.get("/assets/app.js")
        assert script.status_code == 200 and script.text == "export const ready = true;"
        assert "javascript" in script.headers["content-type"]
        cached = await client.get("/assets/app.js", headers={"if-none-match": script.headers["etag"]})
        assert cached.status_code == 304
        head = await client.head("/login", headers={"accept": "text/html"})
        assert head.status_code == 200 and not head.content
        wasm = await client.get("/pyodide/0.29.2/python.wasm", headers={"range": "bytes=0-3"})
        assert wasm.status_code == 206 and wasm.content == b"\x00asm"
        assert wasm.headers["content-type"] == "application/wasm"


@pytest.mark.asyncio
async def test_api_errors_and_streams_preserve_original_behavior(desktop):
    app, _ = desktop
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://127.0.0.1") as client:
        assert (await client.get("/api/health")).json() == {"status": "ok"}
        for path, status in (("/api", 404), ("/api/unknown", 404), ("/api/v1/private", 401)):
            response = await client.get(path, headers={"accept": "text/html"})
            assert response.status_code == status
            assert response.headers["content-type"].startswith("application/json")
        assert (await client.post("/api/health")).status_code == 405
        schema = (await client.get("/openapi.json")).json()
        assert "/api/health" in schema["paths"] and "/login" not in schema["paths"]
        events = await client.get("/api/v1/events")
        assert events.headers["content-type"].startswith("text/event-stream")
        assert events.text == "data: first\n\ndata: done\n\n"


@pytest.mark.asyncio
@pytest.mark.parametrize("path", [
    "/assets/missing.js", "/assets/extensionless", "/pyodide/missing", "/missing.wasm",
    "/%2e%2e/private.txt", "/assets/%2e%2e/%2e%2e/private.txt",
    "/assets/%5c..%5c..%5cprivate.txt", "/C:%5cWindows%5cwin.ini",
])
async def test_missing_assets_and_path_escape_do_not_return_files_or_html(desktop, path):
    app, _ = desktop
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://127.0.0.1") as client:
        response = await client.get(path, headers={"accept": "text/html"})
        assert response.status_code == 404
        assert "outside build" not in response.text and "<title>EduNova</title>" not in response.text


@pytest.mark.parametrize("configured", [None, "relative/dist"])
def test_factory_rejects_missing_or_relative_build_path(monkeypatch, configured):
    if configured is None:
        monkeypatch.delenv("EDUNOVA_DESKTOP_FRONTEND_DIR", raising=False)
    else:
        monkeypatch.setenv("EDUNOVA_DESKTOP_FRONTEND_DIR", configured)
    with pytest.raises(ValueError, match="absolute build directory"):
        create_app()


def test_factory_rejects_incomplete_build_before_api_import(monkeypatch, tmp_path):
    monkeypatch.setenv("EDUNOVA_DESKTOP_FRONTEND_DIR", str(tmp_path))
    with pytest.raises(RuntimeError, match="fallback file"):
        create_app()

"""Serve the desktop build and the existing API from one loopback origin."""

import os
from pathlib import Path

from fastapi import FastAPI
from starlette.types import ASGIApp, Receive, Scope, Send


class DesktopApplication:
    """Keep API errors/streams out of the frontend's navigation fallback."""

    def __init__(self, api: ASGIApp, directory: Path) -> None:
        self.api = api
        self.frontend = FastAPI(openapi_url=None, docs_url=None, redoc_url=None)
        self.frontend.frontend("/", directory=directory, fallback="index.html")
        # Missing runtime assets must remain 404, including extensionless paths.
        for name in ("assets", "pyodide"):
            self.frontend.frontend(f"/{name}", directory=directory / name, fallback=None)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "")
        is_api = any(path == prefix or path.startswith(prefix + "/")
                     for prefix in ("/api", "/docs", "/redoc", "/openapi.json"))
        application = self.api if scope["type"] != "http" or is_api else self.frontend
        await application(scope, receive, send)


def create_app() -> DesktopApplication:
    """Uvicorn factory; the normal backend entry point stays API-only."""
    configured = os.environ.get("EDUNOVA_DESKTOP_FRONTEND_DIR")
    if not configured or not Path(configured).is_absolute():
        raise ValueError("EDUNOVA_DESKTOP_FRONTEND_DIR must be an absolute build directory")
    directory = Path(configured).resolve()
    # Validate the build before importing/starting the application services.
    frontend = DesktopApplication(api=FastAPI(), directory=directory)
    from backend.app.main import create_app as create_api_app

    frontend.api = create_api_app()
    return frontend

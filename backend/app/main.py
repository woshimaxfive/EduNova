from fastapi import FastAPI

from backend.app.api.errors import ApiError, api_error_handler
from backend.app.api.contracts import HealthResponse
from backend.app.api.v1.router import api_router
from backend.app.core.errors import DomainError
from backend.app.core.config import get_settings
from backend.app.core.observability import configure_observability
from backend.app.db.session import engine


def create_app() -> FastAPI:
    application = FastAPI(
        title="EduNova",
    )
    application.add_exception_handler(ApiError, api_error_handler)
    application.add_exception_handler(DomainError, api_error_handler)
    application.include_router(api_router, prefix="/api/v1")
    configure_observability(application, engine, get_settings())

    @application.get("/api/health", tags=["health"], response_model=HealthResponse)
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": "edunova-api"}

    return application


app = create_app()

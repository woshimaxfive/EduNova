from fastapi import FastAPI


def create_app() -> FastAPI:
    application = FastAPI(
        title="EduNova",
    )

    @application.get("/api/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": "edunova-api"}

    return application


app = create_app()

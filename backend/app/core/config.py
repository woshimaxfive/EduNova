from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "EduNova"
    app_env: str = "development"
    app_debug: bool = True
    database_url: str = (
        "postgresql+psycopg://edunova:edunova_dev_password@localhost:5432/edunova"
    )
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = "change-this-local-development-secret"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440
    material_storage_dir: str = "var/uploads/materials"
    material_max_upload_mb: int = 25
    system_model_provider: str = "openai_compatible"
    system_model_base_url: str = "https://api.example.com/v1"
    system_model_api_key: str = "replace-with-your-own-key"
    system_chat_model: str = "example-chat-model"
    system_embedding_model: str = "example-embedding-model"
    model_settings_encryption_key: str = ""
    model_request_timeout_seconds: float = 20.0
    web_search_provider: str = "tavily"
    web_search_endpoint: str = "https://api.tavily.com/search"
    web_search_api_key: str = ""
    web_search_max_results: int = 5
    export_dir: str = "storage/exports"
    export_queue_name: str = "edunova_exports"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()

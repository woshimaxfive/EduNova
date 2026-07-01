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

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()

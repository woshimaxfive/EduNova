from functools import lru_cache

from pydantic import Field, field_validator
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
    chat_attachment_storage_dir: str = "var/uploads/chat-attachments"
    material_max_upload_mb: int = 25
    edunova_document_parser: str = "docling"
    docling_artifacts_path: str = "var/models/docling"
    docling_document_timeout_seconds: float = 120.0
    system_model_provider: str = "openai_compatible"
    system_model_base_url: str = "https://api.example.com/v1"
    system_model_api_key: str = "replace-with-your-own-key"
    system_chat_model: str = "example-chat-model"
    system_generation_provider: str = "openai_compatible"
    system_generation_base_url: str = ""
    system_generation_api_key: str = ""
    system_generation_model: str = ""
    system_embedding_provider: str = "fastembed_local"
    system_embedding_base_url: str = ""
    system_embedding_api_key: str = ""
    system_embedding_app_id: str = ""
    system_embedding_api_secret: str = ""
    system_embedding_model: str = "example-embedding-model"
    system_embedding_dimension: int | None = None
    local_embedding_model_dir: str = "storage/models/bge-small-zh-v1.5"
    local_embedding_threads: int = Field(default=2, ge=1, le=8)
    system_rerank_provider: str = ""
    system_rerank_base_url: str = ""
    system_rerank_api_key: str = ""
    system_rerank_model: str = ""
    system_rerank_workspace_id: str = ""
    vision_request_timeout_seconds: float = 60.0
    local_speech_url: str = "http://speech:8091"
    speech_request_timeout_seconds: float = 75.0
    speech_max_audio_seconds: int = 60
    model_settings_encryption_key: str = ""
    # Domestic OpenAI-compatible providers commonly need more than 20 seconds
    # for structured JSON or the first streamed token. A 45-second attempt
    # avoids three guaranteed timeouts while keeping the bounded retry runtime.
    model_request_timeout_seconds: float = 45.0
    model_max_attempts: int = 3
    model_retry_base_delay_seconds: float = 0.5
    model_retry_max_delay_seconds: float = 2.0
    model_retry_after_max_seconds: float = 3.0
    model_circuit_failure_threshold: int = 5
    model_circuit_window_seconds: int = 60
    model_circuit_open_seconds: int = 60
    model_max_concurrent_per_user: int = 3
    model_max_concurrent_global: int = 12
    model_concurrency_wait_seconds: float = 2.0
    model_call_log_retention_days: int = 30
    web_search_provider: str = "searxng"
    web_search_endpoint: str = "http://searxng:8080/search"
    web_search_max_results: int = 5
    export_dir: str = "storage/exports"
    export_queue_name: str = "edunova_exports"
    ai_job_queue_name: str = "edunova_ai"
    ai_job_timeout_seconds: int = 900
    ai_job_stale_seconds: int = 180
    ai_job_max_active_per_user: int = 2
    code_verifier_url: str = ""
    code_verifier_timeout_seconds: float = 40.0
    otel_exporter_otlp_endpoint: str = ""
    otel_service_name: str = "edunova-api"
    storage_backend: str = "local"
    s3_endpoint_url: str = ""
    s3_bucket: str = ""
    s3_region: str = "us-east-1"
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    clamav_enabled: bool = False
    clamav_host: str = "clamav"
    clamav_port: int = 3310
    clamav_timeout_seconds: float = 10.0

    @field_validator("system_embedding_dimension", mode="before")
    @classmethod
    def empty_embedding_dimension_is_unset(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("edunova_document_parser")
    @classmethod
    def validate_document_parser(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"docling", "legacy"}:
            raise ValueError("EDUNOVA_DOCUMENT_PARSER must be docling or legacy")
        return normalized

    @field_validator("storage_backend")
    @classmethod
    def validate_storage_backend(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"local", "s3"}:
            raise ValueError("STORAGE_BACKEND must be local or s3")
        return normalized

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()

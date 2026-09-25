from __future__ import annotations

from fastapi import Depends, Header, Query, status

from backend.app.services.model_usage_report import get_usage_report

from backend.app.api.contracts import TypedAPIRouter as APIRouter
from backend.app.api.errors import ApiError, api_response
from backend.app.api.v1.deps import get_current_user
from backend.app.core.config import get_settings
from backend.app.db.session import get_db_session
from backend.app.models import User
from backend.app.providers.openai_compatible import ModelProviderError, OpenAICompatibleChatProvider
from backend.app.services.model_settings import (
    EmbeddingReindexRequest,
    ModelSettingsNotFoundError,
    ModelSettingsValidationError,
    ModelSettingsConfigurationError,
    ModelConnectionTestRequest,
    ModelSettingsService,
    SaveModelConfigRequest,
    SaveModelSettingsRequest,
    SqlAlchemyModelSettingsRepository,
    UpdateModelConfigRequest,
)
from backend.app.services.ai_jobs import AiJobService, RqAiJobQueue, SqlAlchemyAiJobRepository
from backend.app.services.conversation_memory import (
    ConversationMemoryService,
    RqConversationMemoryQueue,
    UpdatePrivacySettingsRequest,
)
from backend.app.services.embeddings import EmbeddingService
from backend.app.services.model_catalog import (
    ModelCatalogClient, ModelCatalogError, ModelCatalogRequest, personal_catalog_key,
)


router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/model/usage")
def get_model_usage(
    days: int = Query(default=7, ge=1, le=30),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db_session),
) -> dict:
    report = get_usage_report(db, current_user.id, days, get_settings().model_call_log_retention_days)
    return api_response(report.model_dump())


def get_model_settings_service(db=Depends(get_db_session)) -> ModelSettingsService:
    return ModelSettingsService(
        repository=SqlAlchemyModelSettingsRepository(db),
        settings=get_settings(),
        provider=OpenAICompatibleChatProvider(),
    )


@router.post("/model/catalog")
def fetch_model_catalog(
    payload: ModelCatalogRequest,
    current_user: User = Depends(get_current_user),
    service: ModelSettingsService = Depends(get_model_settings_service),
) -> dict:
    try:
        key = personal_catalog_key(service, current_user, payload)
        result = ModelCatalogClient().fetch(payload.base_url, key)
    except ModelSettingsValidationError as exc:
        raise ApiError(status_code=400, code="MODEL_SETTINGS_INVALID", message=str(exc)) from exc
    except ModelSettingsConfigurationError as exc:
        raise ApiError(status_code=500, code="CONFIGURATION_ERROR", message=str(exc)) from exc
    except ModelCatalogError as exc:
        raise ApiError(status_code=502, code="MODEL_CATALOG_UNAVAILABLE", message=str(exc)) from exc
    return api_response(result.model_dump())


def get_settings_ai_job_service(db=Depends(get_db_session)) -> AiJobService:
    settings = get_settings()
    return AiJobService(
        SqlAlchemyAiJobRepository(db),
        settings=settings,
        queue=RqAiJobQueue(settings),
    )


def get_conversation_memory_service(db=Depends(get_db_session)) -> ConversationMemoryService:
    settings = get_settings()
    model_service = ModelSettingsService(
        repository=SqlAlchemyModelSettingsRepository(db),
        settings=get_settings(),
        provider=OpenAICompatibleChatProvider(),
    )
    return ConversationMemoryService(
        db,
        EmbeddingService(model_service),
        RqConversationMemoryQueue(redis_url=settings.redis_url, queue_name=settings.ai_job_queue_name),
    )


@router.get("/privacy")
def get_privacy_settings(
    current_user: User = Depends(get_current_user),
    service: ConversationMemoryService = Depends(get_conversation_memory_service),
) -> dict:
    return api_response(service.get_settings(current_user).model_dump())


@router.put("/privacy")
def update_privacy_settings(
    payload: UpdatePrivacySettingsRequest,
    current_user: User = Depends(get_current_user),
    service: ConversationMemoryService = Depends(get_conversation_memory_service),
) -> dict:
    return api_response(
        service.update_settings(current_user, payload.conversation_memory_enabled).model_dump()
    )


@router.delete("/privacy/conversation-memory")
def clear_conversation_memory(
    current_user: User = Depends(get_current_user),
    service: ConversationMemoryService = Depends(get_conversation_memory_service),
) -> dict:
    return api_response(service.clear(current_user).model_dump())


@router.get("/model")
def get_model_settings(
    current_user: User = Depends(get_current_user),
    service: ModelSettingsService = Depends(get_model_settings_service),
) -> dict:
    return api_response(service.get_summary(current_user).model_dump())


@router.put("/model")
def save_model_settings(
    payload: SaveModelSettingsRequest,
    current_user: User = Depends(get_current_user),
    service: ModelSettingsService = Depends(get_model_settings_service),
) -> dict:
    try:
        summary = service.save(current_user, payload)
    except ModelSettingsValidationError as exc:
        raise ApiError(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="MODEL_SETTINGS_INVALID",
            message=str(exc),
        ) from exc
    except ModelSettingsConfigurationError as exc:
        raise ApiError(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="CONFIGURATION_ERROR",
            message=str(exc),
        ) from exc

    return api_response(summary.model_dump())


@router.get("/model/configs")
def list_model_configs(
    current_user: User = Depends(get_current_user),
    service: ModelSettingsService = Depends(get_model_settings_service),
) -> dict:
    return api_response(service.list_configs(current_user).model_dump())


@router.post("/model/configs")
def create_model_config(
    payload: SaveModelConfigRequest,
    current_user: User = Depends(get_current_user),
    service: ModelSettingsService = Depends(get_model_settings_service),
) -> dict:
    try:
        config = service.create_config(current_user, payload)
    except ModelSettingsValidationError as exc:
        raise ApiError(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="MODEL_SETTINGS_INVALID",
            message=str(exc),
        ) from exc
    except ModelSettingsConfigurationError as exc:
        raise ApiError(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="CONFIGURATION_ERROR",
            message=str(exc),
        ) from exc

    return api_response(config.model_dump())


@router.patch("/model/configs/{config_id}")
def update_model_config(
    config_id: int,
    payload: UpdateModelConfigRequest,
    current_user: User = Depends(get_current_user),
    service: ModelSettingsService = Depends(get_model_settings_service),
) -> dict:
    try:
        config = service.update_config(current_user, config_id, payload)
    except ModelSettingsNotFoundError as exc:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="MODEL_SETTINGS_NOT_FOUND",
            message=str(exc),
        ) from exc
    except ModelSettingsValidationError as exc:
        raise ApiError(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="MODEL_SETTINGS_INVALID",
            message=str(exc),
        ) from exc
    except ModelSettingsConfigurationError as exc:
        raise ApiError(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="CONFIGURATION_ERROR",
            message=str(exc),
        ) from exc

    return api_response(config.model_dump())


@router.delete("/model/configs/{config_id}")
def delete_model_config(
    config_id: int,
    current_user: User = Depends(get_current_user),
    service: ModelSettingsService = Depends(get_model_settings_service),
) -> dict:
    try:
        configs = service.delete_config(current_user, config_id)
    except ModelSettingsNotFoundError as exc:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="MODEL_SETTINGS_NOT_FOUND",
            message=str(exc),
        ) from exc

    return api_response(configs.model_dump())


@router.post("/model/configs/{config_id}/default")
def set_default_model_config(
    config_id: int,
    current_user: User = Depends(get_current_user),
    service: ModelSettingsService = Depends(get_model_settings_service),
) -> dict:
    try:
        configs = service.set_default_config(current_user, config_id)
    except ModelSettingsNotFoundError as exc:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="MODEL_SETTINGS_NOT_FOUND",
            message=str(exc),
        ) from exc
    except ModelSettingsValidationError as exc:
        raise ApiError(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="MODEL_SETTINGS_INVALID",
            message=str(exc),
        ) from exc

    return api_response(configs.model_dump())


@router.post("/model/configs/{config_id}/generation-default")
def set_generation_default_model_config(
    config_id: int,
    current_user: User = Depends(get_current_user),
    service: ModelSettingsService = Depends(get_model_settings_service),
) -> dict:
    try:
        configs = service.set_generation_default_config(current_user, config_id)
    except ModelSettingsNotFoundError as exc:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="MODEL_SETTINGS_NOT_FOUND",
            message=str(exc),
        ) from exc
    except ModelSettingsValidationError as exc:
        raise ApiError(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="MODEL_SETTINGS_INVALID",
            message=str(exc),
        ) from exc

    return api_response(configs.model_dump())


@router.post("/model/configs/{config_id}/embedding-default")
def set_embedding_default_model_config(
    config_id: int,
    current_user: User = Depends(get_current_user),
    service: ModelSettingsService = Depends(get_model_settings_service),
) -> dict:
    try:
        configs = service.set_embedding_default_config(current_user, config_id)
    except ModelSettingsNotFoundError as exc:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="MODEL_SETTINGS_NOT_FOUND",
            message=str(exc),
        ) from exc
    except ModelSettingsValidationError as exc:
        raise ApiError(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="MODEL_SETTINGS_INVALID",
            message=str(exc),
        ) from exc

    return api_response(configs.model_dump())


@router.post("/model/configs/{config_id}/rerank-default")
def set_rerank_default_model_config(
    config_id: int,
    current_user: User = Depends(get_current_user),
    service: ModelSettingsService = Depends(get_model_settings_service),
) -> dict:
    try:
        configs = service.set_rerank_default_config(current_user, config_id)
    except ModelSettingsNotFoundError as exc:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="MODEL_SETTINGS_NOT_FOUND",
            message=str(exc),
        ) from exc
    except ModelSettingsValidationError as exc:
        raise ApiError(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="MODEL_SETTINGS_INVALID",
            message=str(exc),
        ) from exc
    return api_response(configs.model_dump())


@router.post("/model/configs/{config_id}/test")
def test_model_config(
    config_id: int,
    payload: ModelConnectionTestRequest | None = None,
    current_user: User = Depends(get_current_user),
    service: ModelSettingsService = Depends(get_model_settings_service),
) -> dict:
    try:
        result = service.test_config_connection(
            current_user,
            config_id,
            operation=payload.operation if payload is not None else "chat",
        )
    except ModelSettingsNotFoundError as exc:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="MODEL_SETTINGS_NOT_FOUND",
            message=str(exc),
        ) from exc
    except ModelSettingsConfigurationError as exc:
        raise ApiError(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="CONFIGURATION_ERROR",
            message=str(exc),
        ) from exc

    return api_response(result.model_dump())


@router.post("/model/test")
def test_model_settings(
    payload: ModelConnectionTestRequest | None = None,
    current_user: User = Depends(get_current_user),
    service: ModelSettingsService = Depends(get_model_settings_service),
) -> dict:
    try:
        result = service.test_connection(
            current_user,
            operation=payload.operation if payload is not None else "chat",
        )
    except ModelProviderError as exc:
        raise ApiError(
            status_code=status.HTTP_502_BAD_GATEWAY,
            code="MODEL_PROVIDER_ERROR",
            message=str(exc),
        ) from exc

    return api_response(result.model_dump())


@router.post("/model/embedding/reindex-jobs", status_code=202)
def create_embedding_reindex_job(
    payload: EmbeddingReindexRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    current_user: User = Depends(get_current_user),
    service: AiJobService = Depends(get_settings_ai_job_service),
) -> dict:
    job = service.create_embedding_reindex_job(
        current_user,
        config_id=payload.config_id,
        idempotency_key=idempotency_key,
    )
    return api_response(job.model_dump(mode="json"))

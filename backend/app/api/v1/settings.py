from __future__ import annotations

from fastapi import APIRouter, Depends, status

from backend.app.api.errors import ApiError, api_response
from backend.app.api.v1.deps import get_current_user
from backend.app.core.config import get_settings
from backend.app.db.session import get_db_session
from backend.app.models import User
from backend.app.providers.openai_compatible import ModelProviderError, OpenAICompatibleChatProvider
from backend.app.services.model_settings import (
    ModelSettingsNotFoundError,
    ModelSettingsValidationError,
    ModelSettingsConfigurationError,
    ModelSettingsService,
    SaveModelConfigRequest,
    SaveModelSettingsRequest,
    SqlAlchemyModelSettingsRepository,
    UpdateModelConfigRequest,
)


router = APIRouter(prefix="/settings", tags=["settings"])


def get_model_settings_service(db=Depends(get_db_session)) -> ModelSettingsService:
    return ModelSettingsService(
        repository=SqlAlchemyModelSettingsRepository(db),
        settings=get_settings(),
        provider=OpenAICompatibleChatProvider(),
    )


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

    return api_response(configs.model_dump())


@router.post("/model/configs/{config_id}/test")
def test_model_config(
    config_id: int,
    current_user: User = Depends(get_current_user),
    service: ModelSettingsService = Depends(get_model_settings_service),
) -> dict:
    try:
        result = service.test_config_connection(current_user, config_id)
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
    current_user: User = Depends(get_current_user),
    service: ModelSettingsService = Depends(get_model_settings_service),
) -> dict:
    try:
        result = service.test_connection(current_user)
    except ModelProviderError as exc:
        raise ApiError(
            status_code=status.HTTP_502_BAD_GATEWAY,
            code="MODEL_PROVIDER_ERROR",
            message=str(exc),
        ) from exc

    return api_response(result.model_dump())

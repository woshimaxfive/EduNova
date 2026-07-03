from __future__ import annotations

from fastapi import APIRouter, Depends, status

from backend.app.api.errors import ApiError, api_response
from backend.app.api.v1.deps import get_auth_service, get_current_user
from backend.app.models import User
from backend.app.schemas.auth import LoginRequest, RegisterRequest, user_to_api
from backend.app.services.auth import (
    DuplicateEmailError,
    InvalidCredentialsError,
    WeakPasswordError,
)


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register")
def register(
    payload: RegisterRequest,
    service=Depends(get_auth_service),
) -> dict:
    try:
        user = service.register(
            email=payload.email,
            password=payload.password,
            display_name=payload.display_name,
            starter_mode=payload.starter_mode,
        )
    except DuplicateEmailError as exc:
        raise ApiError(
            status_code=status.HTTP_409_CONFLICT,
            code="DUPLICATE_RESOURCE",
            message="这个邮箱已经注册过了。",
        ) from exc
    except WeakPasswordError as exc:
        raise ApiError(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="VALIDATION_ERROR",
            message=str(exc),
        ) from exc

    return api_response(user_to_api(user).model_dump())


@router.post("/login")
def login(
    payload: LoginRequest,
    service=Depends(get_auth_service),
) -> dict:
    try:
        result = service.login(payload.email, payload.password)
    except InvalidCredentialsError as exc:
        raise ApiError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="UNAUTHORIZED",
            message="邮箱或密码不正确。",
        ) from exc

    return api_response(
        {
            "access_token": result.access_token,
            "token_type": "bearer",
            "user": user_to_api(result.user).model_dump(),
        }
    )


@router.get("/me")
def me(current_user: User = Depends(get_current_user)) -> dict:
    return api_response(user_to_api(current_user).model_dump())


@router.post("/logout")
def logout(_current_user: User = Depends(get_current_user)) -> dict:
    return api_response({"ok": True})

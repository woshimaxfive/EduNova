from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, status

from backend.app.api.errors import ApiError
from backend.app.core.config import Settings, get_settings
from backend.app.core.security import InvalidTokenError
from backend.app.db.session import get_db_session
from backend.app.models import User
from backend.app.services.auth import (
    AuthService,
    SqlAlchemyAuthRepository,
    UserNotFoundError,
)


def get_auth_repository(db=Depends(get_db_session)) -> SqlAlchemyAuthRepository:
    return SqlAlchemyAuthRepository(db)


def get_auth_service(
    repository=Depends(get_auth_repository),
    settings: Settings = Depends(get_settings),
) -> AuthService:
    return AuthService(repository=repository, settings=settings)


def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    service: AuthService = Depends(get_auth_service),
) -> User:
    if authorization is None or not authorization.lower().startswith("bearer "):
        raise ApiError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="UNAUTHORIZED",
            message="请先登录后再访问。",
        )

    token = authorization.split(" ", 1)[1].strip()
    try:
        return service.get_user_by_token(token)
    except (InvalidTokenError, UserNotFoundError) as exc:
        raise ApiError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="UNAUTHORIZED",
            message="登录状态已失效，请重新登录。",
        ) from exc

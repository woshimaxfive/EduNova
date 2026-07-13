from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from jwt import InvalidTokenError as JwtInvalidTokenError

from backend.app.core.config import Settings, get_settings


class InvalidTokenError(Exception):
    """Raised when a JWT cannot be decoded into a valid user subject."""


@dataclass(frozen=True)
class AccessTokenClaims:
    subject: str
    auth_version: int


def hash_password(password: str) -> str:
    password_bytes = password.encode("utf-8")
    return bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(
    subject: str,
    settings: Settings | None = None,
    *,
    auth_version: int = 0,
) -> str:
    active_settings = settings or get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "auth_version": max(0, auth_version),
        "iat": now,
        "exp": now + timedelta(minutes=active_settings.jwt_expire_minutes),
    }
    return jwt.encode(
        payload,
        active_settings.jwt_secret,
        algorithm=active_settings.jwt_algorithm,
    )


def parse_access_token_claims(token: str, settings: Settings | None = None) -> AccessTokenClaims:
    active_settings = settings or get_settings()
    try:
        payload = jwt.decode(
            token,
            active_settings.jwt_secret,
            algorithms=[active_settings.jwt_algorithm],
        )
    except JwtInvalidTokenError as exc:
        raise InvalidTokenError("无效或已过期的登录凭证。") from exc

    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject:
        raise InvalidTokenError("登录凭证缺少用户信息。")
    raw_auth_version = payload.get("auth_version", 0)
    if not isinstance(raw_auth_version, int) or raw_auth_version < 0:
        raise InvalidTokenError("登录凭证版本无效。")
    return AccessTokenClaims(subject=subject, auth_version=raw_auth_version)


def parse_access_token(token: str, settings: Settings | None = None) -> str:
    return parse_access_token_claims(token, settings=settings).subject

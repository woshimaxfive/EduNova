from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from jwt import InvalidTokenError as JwtInvalidTokenError

from backend.app.core.config import Settings, get_settings


class InvalidTokenError(Exception):
    """Raised when a JWT cannot be decoded into a valid user subject."""


def hash_password(password: str) -> str:
    password_bytes = password.encode("utf-8")
    return bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(subject: str, settings: Settings | None = None) -> str:
    active_settings = settings or get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(minutes=active_settings.jwt_expire_minutes),
    }
    return jwt.encode(
        payload,
        active_settings.jwt_secret,
        algorithm=active_settings.jwt_algorithm,
    )


def parse_access_token(token: str, settings: Settings | None = None) -> str:
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
    return subject

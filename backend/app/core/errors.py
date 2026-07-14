from __future__ import annotations

from typing import Any


class DomainError(Exception):
    """Transport-neutral domain failure with a stable public classification."""

    status_code = 400
    code = "DOMAIN_ERROR"

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class NotFoundDomainError(DomainError):
    status_code = 404
    code = "NOT_FOUND"


class ValidationDomainError(DomainError):
    status_code = 400
    code = "VALIDATION_ERROR"


class ConflictDomainError(DomainError):
    status_code = 409
    code = "CONFLICT"

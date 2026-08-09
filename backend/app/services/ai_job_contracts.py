from __future__ import annotations

from typing import Protocol

from backend.app.core.errors import ConflictDomainError, NotFoundDomainError, ValidationDomainError




ACTIVE_STATUSES = {"queued", "running", "cancelling"}
TERMINAL_STATUSES = {"cancelled", "completed", "failed"}
RETRYABLE_STATUSES = {"cancelled", "failed"}
WORKFLOWS = {
    "course_builder",
    "resource_generation",
    "embedding_reindex",
    "material_ingestion",
    "path_planning",
    "practice_generation",
    "report_generation",
}


class AiJobNotFoundError(NotFoundDomainError):
    pass


class AiJobValidationError(ValidationDomainError):
    pass


class AiJobConflictError(ConflictDomainError):
    pass


class AiJobCancelled(Exception):
    pass


class AiJobQueue(Protocol):
    def enqueue(self, job_id: int) -> str: ...

    def cancel(self, queue_job_id: str) -> None: ...

    def is_active(self, queue_job_id: str) -> bool: ...

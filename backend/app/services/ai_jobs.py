from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from backend.app.core.config import Settings, get_settings
from backend.app.models import AiJob, User
from backend.app.services.ai_job_contracts import (
    AiJobCancelled as AiJobCancelled,
    AiJobConflictError as AiJobConflictError,
    AiJobNotFoundError as AiJobNotFoundError,
    AiJobQueue as AiJobQueue,
    AiJobValidationError as AiJobValidationError,
)
from backend.app.services.ai_job_execution import AiJobExecutionMixin
from backend.app.services.ai_job_lifecycle import AiJobLifecycleMixin
from backend.app.services.ai_job_queue import RqAiJobQueue as RqAiJobQueue
from backend.app.services.ai_job_repository import SqlAlchemyAiJobRepository as SqlAlchemyAiJobRepository
from backend.app.services.ai_job_requests import AiJobRequestMixin


class AiJobService(AiJobRequestMixin, AiJobLifecycleMixin, AiJobExecutionMixin):
    max_retries = 3

    def __init__(
        self,
        repository: SqlAlchemyAiJobRepository,
        *,
        settings: Settings | None = None,
        queue: AiJobQueue | None = None,
        run_jobs_inline: bool = False,
    ) -> None:
        self.repository = repository
        self.settings = settings or get_settings()
        self.queue = queue
        self.run_jobs_inline = run_jobs_inline

    def _require(self, user: User, job_id: int, *, for_update: bool = False) -> AiJob:
        job = self.repository.get_job_for_user(user.id, job_id, for_update=for_update)
        if job is None:
            raise AiJobNotFoundError("AI 任务不存在或无权访问。")
        return job

    def _mark_failed(self, job: AiJob, code: str, message: str) -> None:
        now = datetime.now(UTC)
        job.status = "failed"
        job.stage = "failed"
        job.label = "任务执行失败"
        job.error_code = code
        job.error_message = message
        job.completed_at = now
        job.heartbeat_at = now
        job.updated_at = now
        self.repository.commit()
        self.repository.refresh(job)

    def _reconcile_stale(self, job: AiJob) -> None:
        if job.status not in {"running", "cancelling"} or job.heartbeat_at is None:
            return
        heartbeat = job.heartbeat_at if job.heartbeat_at.tzinfo is not None else job.heartbeat_at.replace(tzinfo=UTC)
        if datetime.now(UTC) - heartbeat <= timedelta(seconds=self.settings.ai_job_stale_seconds):
            return
        if self.queue is not None and job.queue_job_id and self.queue.is_active(job.queue_job_id):
            return
        self._mark_failed(job, "WORKER_LOST", "AI 任务执行中断，可重新尝试。")

    @staticmethod
    def _normalize_key(value: str | None) -> str:
        normalized = "".join(ch for ch in str(value or "").strip() if ch.isalnum() or ch in {"-", "_", "."})[:120]
        return normalized or f"job-{uuid4().hex}"

    @staticmethod
    def _safe_error_code(exc: Exception) -> str:
        current: BaseException | None = exc
        while current is not None:
            code = getattr(current, "code", None)
            if isinstance(code, str) and code:
                return code
            current = current.__cause__ or current.__context__
        name = exc.__class__.__name__.upper()
        if "VALIDATION" in name or "GENERATION" in name:
            return "GENERATION_ERROR"
        if "NOTFOUND" in name or "NOT_FOUND" in name:
            return "NOT_FOUND"
        return "INTERNAL_ERROR"

    @staticmethod
    def _safe_error_message(exc: Exception) -> str:
        code = AiJobService._safe_error_code(exc)
        runtime_messages = {
            "JOB_TIMEOUT": "AI 任务执行超时，可稍后重试。",
            "authentication_failed": "模型配置认证失败，请检查模型设置后重试。",
            "context_too_long": "任务上下文过长，请缩小资料或生成范围。",
            "rate_limited": "模型服务请求较多，可稍后重试。",
            "model_busy": "当前模型任务较多，可稍后重试。",
            "circuit_open": "模型服务正在恢复，可稍后重试。",
            "timeout": "模型响应超时，可稍后重试。",
            "network_error": "暂时无法连接模型服务，可稍后重试。",
            "provider_unavailable": "模型服务暂不可用，可稍后重试。",
            "invalid_request": "模型服务无法处理本次任务，请调整输入。",
            "invalid_response": "模型返回格式异常，可重新生成。",
        }
        if code in runtime_messages:
            return runtime_messages[code]
        if isinstance(exc, (AiJobValidationError, AiJobNotFoundError)):
            return str(exc)[:300]
        name = exc.__class__.__name__.lower()
        if "generation" in name or "validation" in name or "notfound" in name:
            return str(exc)[:300] or "AI 任务执行失败，请稍后重试。"
        return "AI 任务执行失败，请稍后重试。"

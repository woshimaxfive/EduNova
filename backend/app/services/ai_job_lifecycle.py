from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Callable
from uuid import uuid4

from sqlalchemy import select

from backend.app.api.errors import make_trace_id
from backend.app.models import (
    AiJob,
    User,
    WeaknessReviewItem,
)
from backend.app.schemas.ai_jobs import AiJobListResponse, AiJobResponse, ai_job_to_api
from backend.app.services.ai_job_contracts import (
    RETRYABLE_STATUSES,
    TERMINAL_STATUSES,
    AiJobConflictError,
    AiJobNotFoundError,
    AiJobValidationError,
)
from backend.app.services.mastery_progress import is_review_due
from backend.app.services.ai_capabilities import AI_CAPABILITIES, validate_capability_scope


class AiJobLifecycleMixin:
    def _create_retry_job(
        self,
        user: User,
        original: AiJob,
        *,
        next_attempt: int,
        **kwargs: Any,
    ) -> AiJobResponse:
        """在同一数据库提交中创建重试任务并消耗额度。"""
        caller_before_commit = kwargs.pop("before_commit", None)

        def before_commit(job: AiJob) -> None:
            if caller_before_commit is not None:
                caller_before_commit(job)
            original.attempt_count = next_attempt

        return self._create(user, attempt_count=next_attempt, before_commit=before_commit, **kwargs)

    def _require_active_course(self, user_id: int, course_id: int) -> None:
        if not self.repository.is_course_active(user_id, course_id):
            raise AiJobConflictError("课程已完成归档；请先恢复学习再创建新的生成任务。")

    def _create(
        self,
        user: User,
        *,
        workflow: str,
        course_id: int | None,
        request_json: dict[str, Any],
        idempotency_key: str | None,
        retry_of_job_id: int | None = None,
        attempt_count: int = 0,
        before_commit: Callable[[AiJob], None] | None = None,
    ) -> AiJobResponse:
        key = self._normalize_key(idempotency_key)
        existing = self.repository.get_by_idempotency(user.id, key)
        if existing is not None:
            return ai_job_to_api(existing, max_retries=self.max_retries)
        capability = AI_CAPABILITIES.get(workflow)
        if capability is not None:
            request = capability.validate_input(request_json, course_id)
            validate_capability_scope(self.repository, user.id, request)
            request_json = request.model_dump(mode="json")
        if self.repository.lock_user(user.id) is None:
            raise AiJobNotFoundError("任务用户不存在。")
        existing = self.repository.get_by_idempotency(user.id, key)
        if existing is not None:
            self.repository.rollback()
            return ai_job_to_api(existing, max_retries=self.max_retries)
        if self.repository.count_active(user.id) >= self.settings.ai_job_max_active_per_user:
            self.repository.rollback()
            raise AiJobConflictError("同时运行的 AI 任务已达到上限，请等待已有任务完成。")
        job = AiJob(
            user_id=user.id,
            course_id=course_id,
            retry_of_job_id=retry_of_job_id,
            workflow=workflow,
            status="queued",
            progress_percent=0,
            stage="queued",
            label="任务已排队",
            agent_trace_id=make_trace_id(),
            idempotency_key=key,
            request_json=request_json,
            progress_json={"steps": []},
            result_json={},
            attempt_count=attempt_count,
            heartbeat_at=datetime.now(UTC),
        )
        try:
            self.repository.add(job)
            if before_commit is not None:
                before_commit(job)
            self.repository.commit()
            self.repository.refresh(job)
        except Exception:
            self.repository.rollback()
            existing = self.repository.get_by_idempotency(user.id, key)
            if existing is not None:
                return ai_job_to_api(existing, max_retries=self.max_retries)
            raise

        if self.run_jobs_inline:
            self.run_job(int(job.id))
            refreshed = self.repository.get_job_for_user(user.id, int(job.id)) or job
            return ai_job_to_api(refreshed, max_retries=self.max_retries)
        if self.queue is not None:
            try:
                job.queue_job_id = self.queue.enqueue(int(job.id))
                self.repository.commit()
                self.repository.refresh(job)
            except Exception:
                self.repository.rollback()
                failed = self.repository.get_job_for_user(user.id, int(job.id)) or job
                self._mark_failed(failed, "QUEUE_UNAVAILABLE", "AI 任务排队失败，请稍后重试。")
                job = failed
        return ai_job_to_api(job, max_retries=self.max_retries)

    def list_jobs(self, user: User, status_filter: str, limit: int) -> AiJobListResponse:
        statuses = {"queued", "running", "cancelling", "failed"} if status_filter == "active" else ({status_filter} if status_filter else None)
        jobs = self.repository.list_jobs(user.id, statuses, max(1, min(limit, 50)))
        for job in jobs:
            self._reconcile_stale(job)
        return AiJobListResponse(data=[ai_job_to_api(job, max_retries=self.max_retries) for job in jobs], total=len(jobs))

    def get_job(self, user: User, job_id: int) -> AiJobResponse:
        job = self._require(user, job_id)
        self._reconcile_stale(job)
        return ai_job_to_api(job, max_retries=self.max_retries)

    def cancel_job(self, user: User, job_id: int) -> AiJobResponse:
        job = self._require(user, job_id, for_update=True)
        if job.status in TERMINAL_STATUSES:
            self.repository.rollback()
            return ai_job_to_api(job, max_retries=self.max_retries)
        now = datetime.now(UTC)
        job.cancel_requested_at = now
        queue_job_id = job.queue_job_id
        if job.status == "queued":
            job.status = "cancelled"
            job.stage = "cancelled"
            job.label = "任务已取消"
            job.completed_at = now
        else:
            job.status = "cancelling"
            job.label = "正在安全停止任务"
        job.updated_at = now
        self.repository.commit()
        self.repository.refresh(job)
        if job.status == "cancelled" and self.queue is not None and queue_job_id:
            self.queue.cancel(queue_job_id)
        return ai_job_to_api(job, max_retries=self.max_retries)

    def retry_job(self, user: User, job_id: int) -> AiJobResponse:
        original = self._require(user, job_id, for_update=True)
        if original.status not in RETRYABLE_STATUSES:
            self.repository.rollback()
            raise AiJobConflictError("只有失败或已取消的任务可以重试。")
        if int(original.attempt_count or 0) >= self.max_retries:
            self.repository.rollback()
            raise AiJobConflictError("该任务已达到最大重试次数。")
        next_attempt = int(original.attempt_count or 0) + 1
        request = dict(original.request_json or {})
        if original.workflow == "embedding_reindex":
            from backend.app.providers.openai_compatible import OpenAICompatibleChatProvider
            from backend.app.services.model_settings import ModelSettingsService, SqlAlchemyModelSettingsRepository

            runtime = ModelSettingsService(
                repository=SqlAlchemyModelSettingsRepository(self.repository.db),
                settings=self.settings,
                provider=OpenAICompatibleChatProvider(),
            ).resolve_embedding_runtime_config(user)
            if not runtime.can_use_model:
                raise AiJobValidationError("系统向量配置已不可用，请联系管理员后重试。")
            return self._create_retry_job(
                user,
                original,
                workflow="embedding_reindex",
                course_id=None,
                request_json=request,
                idempotency_key=f"retry-{original.id}-{uuid4().hex}",
                retry_of_job_id=original.id,
                next_attempt=next_attempt,
            )
        if original.workflow == "material_ingestion":
            material_id = int(request.get("material_id") or 0)
            materials = self.repository.get_materials_for_user(user.id, [material_id])
            if len(materials) != 1:
                raise AiJobNotFoundError("资料不存在或无权访问。")
            return self._create_retry_job(
                user,
                original,
                workflow="material_ingestion",
                course_id=None,
                request_json=request,
                idempotency_key=f"retry-{original.id}-{uuid4().hex}",
                retry_of_job_id=original.id,
                next_attempt=next_attempt,
            )
        if original.workflow == "course_builder":
            material_ids = [int(item) for item in request.get("material_ids", [])]
            materials = self.repository.get_materials_for_user(user.id, material_ids)
            if len(materials) != len(material_ids):
                raise AiJobNotFoundError("资料不存在或无权访问。")
            if any(material.parse_status != "completed" or material.ingestion_status != "confirmed" for material in materials):
                raise AiJobConflictError("请先完成资料精细解析并确认目录，再重新生成课程。")
            return self._create_retry_job(
                user,
                original,
                workflow=original.workflow,
                course_id=None,
                request_json=request,
                idempotency_key=f"retry-{original.id}-{uuid4().hex}",
                retry_of_job_id=original.id,
                next_attempt=next_attempt,
            )
        if original.workflow == "path_planning":
            course_id = int(request.get("course_id") or original.course_id or 0)
            if self.repository.get_course_for_user(user.id, course_id) is None:
                raise AiJobNotFoundError("课程不存在或无权访问。")
            return self._create_retry_job(
                user,
                original,
                workflow="path_planning",
                course_id=course_id,
                request_json=request,
                idempotency_key=f"retry-{original.id}-{uuid4().hex}",
                retry_of_job_id=original.id,
                next_attempt=next_attempt,
            )
        if original.workflow in {"practice_generation", "report_generation"}:
            course_id = int(request.get("course_id") or original.course_id or 0)
            if self.repository.get_course_for_user(user.id, course_id) is None:
                raise AiJobNotFoundError("课程不存在或无权访问。")
            if original.workflow == "practice_generation":
                point_ids = [int(item) for item in request.get("knowledge_point_ids", [])]
                if not point_ids or any(self.repository.get_knowledge_point(course_id, item) is None for item in point_ids):
                    raise AiJobNotFoundError("知识点不存在或不属于当前课程。")
                weakness_item_id = request.get("weakness_item_id")
                if weakness_item_id is not None:
                    weakness = self.repository.db.scalar(
                        select(WeaknessReviewItem).where(
                            WeaknessReviewItem.id == int(weakness_item_id),
                            WeaknessReviewItem.user_id == user.id,
                            WeaknessReviewItem.course_id == course_id,
                        )
                    )
                    if weakness is None or (weakness.status not in {"confirmed", "reviewing"} and not is_review_due(weakness)):
                        raise AiJobNotFoundError("待复习弱点不存在、状态不可用或无权访问。")
            elif request.get("practice_session_id") is not None:
                session = self.repository.get_practice_session_for_user(user.id, int(request["practice_session_id"]))
                if session is None or int(session.course_id) != course_id:
                    raise AiJobNotFoundError("练习不存在或无权访问。")
            return self._create_retry_job(
                user,
                original,
                workflow=original.workflow,
                course_id=course_id,
                request_json=request,
                idempotency_key=f"retry-{original.id}-{uuid4().hex}",
                retry_of_job_id=original.id,
                next_attempt=next_attempt,
            )
        course_id = int(request["course_id"])
        if self.repository.get_course_for_user(user.id, course_id) is None:
            raise AiJobNotFoundError("课程不存在或无权访问。")
        knowledge_point_id = request.get("knowledge_point_id")
        if knowledge_point_id is not None and self.repository.get_knowledge_point(course_id, int(knowledge_point_id)) is None:
            raise AiJobNotFoundError("知识点不存在或不属于当前课程。")
        if str(request.get("generation_action") or "new") in {"alternative", "refine"}:
            source_resource_id = request.get("source_resource_id")
            source_resource = (
                self.repository.get_resource_for_user(user.id, int(source_resource_id))
                if source_resource_id is not None
                else None
            )
            if source_resource is None or source_resource.course_id != course_id:
                raise AiJobNotFoundError("来源资源不存在或无权访问。")
        return self._create_retry_job(
            user,
            original,
            workflow=original.workflow,
            course_id=course_id,
            request_json=request,
            idempotency_key=f"retry-{original.id}-{uuid4().hex}",
            retry_of_job_id=original.id,
            next_attempt=next_attempt,
        )

    def delete_job(self, user: User, job_id: int) -> None:
        job = self._require(user, job_id, for_update=True)
        if job.status not in RETRYABLE_STATUSES:
            self.repository.rollback()
            raise AiJobConflictError("只有失败或已取消的任务可以删除。")
        self.repository.delete(job)
        self.repository.commit()

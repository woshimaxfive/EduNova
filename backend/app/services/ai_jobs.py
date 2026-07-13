from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, Protocol
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.agents.runtime import AgentTraceRecorder
from backend.app.api.errors import make_trace_id
from backend.app.core.config import Settings, get_settings
from backend.app.db.session import SessionLocal
from backend.app.models import AiJob, Course, KnowledgeChunk, KnowledgePoint, Material, MaterialChunk, ModelSetting, User
from backend.app.schemas.ai_jobs import AiJobListResponse, AiJobResponse, ai_job_to_api, iso_timestamp


ACTIVE_STATUSES = {"queued", "running", "cancelling"}
TERMINAL_STATUSES = {"cancelled", "completed", "failed"}
RETRYABLE_STATUSES = {"cancelled", "failed"}
WORKFLOWS = {"course_builder", "resource_generation", "embedding_reindex"}


class AiJobNotFoundError(Exception):
    pass


class AiJobValidationError(Exception):
    pass


class AiJobConflictError(Exception):
    pass


class AiJobCancelled(Exception):
    pass


class AiJobQueue(Protocol):
    def enqueue(self, job_id: int) -> str: ...

    def cancel(self, queue_job_id: str) -> None: ...

    def is_active(self, queue_job_id: str) -> bool: ...


class RqAiJobQueue:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def enqueue(self, job_id: int) -> str:
        from redis import Redis
        from rq import Queue

        from backend.app.workers.ai_jobs import run_ai_job

        queue_job_id = f"ai-job-{job_id}"
        connection = Redis.from_url(self.settings.redis_url)
        queue = Queue(self.settings.ai_job_queue_name, connection=connection)
        queue.enqueue(
            run_ai_job,
            job_id,
            job_id=queue_job_id,
            job_timeout=self.settings.ai_job_timeout_seconds,
            result_ttl=86400,
            failure_ttl=86400,
        )
        return queue_job_id

    def cancel(self, queue_job_id: str) -> None:
        from redis import Redis
        from rq.job import Job

        connection = Redis.from_url(self.settings.redis_url)
        try:
            Job.fetch(queue_job_id, connection=connection).cancel()
        except Exception:
            return

    def is_active(self, queue_job_id: str) -> bool:
        from redis import Redis
        from rq.job import Job

        connection = Redis.from_url(self.settings.redis_url)
        try:
            return Job.fetch(queue_job_id, connection=connection).get_status(refresh=True) in {
                "queued",
                "started",
                "deferred",
                "scheduled",
            }
        except Exception:
            return False


class SqlAlchemyAiJobRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_user(self, user_id: int) -> User | None:
        return self.db.get(User, user_id)

    def lock_user(self, user_id: int) -> User | None:
        return self.db.scalar(select(User).where(User.id == user_id).with_for_update())

    def get_job(self, job_id: int, *, for_update: bool = False) -> AiJob | None:
        statement = select(AiJob).where(AiJob.id == job_id).execution_options(populate_existing=True)
        if for_update:
            statement = statement.with_for_update()
        return self.db.scalar(statement)

    def get_job_for_user(self, user_id: int, job_id: int, *, for_update: bool = False) -> AiJob | None:
        statement = (
            select(AiJob)
            .where(AiJob.id == job_id, AiJob.user_id == user_id)
            .execution_options(populate_existing=True)
        )
        if for_update:
            statement = statement.with_for_update()
        return self.db.scalar(statement)

    def get_by_idempotency(self, user_id: int, idempotency_key: str) -> AiJob | None:
        return self.db.scalar(
            select(AiJob).where(AiJob.user_id == user_id, AiJob.idempotency_key == idempotency_key)
        )

    def count_active(self, user_id: int) -> int:
        return int(
            self.db.scalar(
                select(func.count(AiJob.id)).where(AiJob.user_id == user_id, AiJob.status.in_(ACTIVE_STATUSES))
            )
            or 0
        )

    def list_jobs(self, user_id: int, statuses: set[str] | None, limit: int) -> list[AiJob]:
        statement = select(AiJob).where(AiJob.user_id == user_id)
        if statuses:
            statement = statement.where(AiJob.status.in_(statuses))
        return list(self.db.scalars(statement.order_by(AiJob.updated_at.desc(), AiJob.id.desc()).limit(limit)))

    def get_course_for_user(self, user_id: int, course_id: int) -> Course | None:
        return self.db.scalar(select(Course).where(Course.id == course_id, Course.owner_id == user_id))

    def get_materials_for_user(self, user_id: int, material_ids: list[int]) -> list[Material]:
        if not material_ids:
            return []
        return list(self.db.scalars(select(Material).where(Material.user_id == user_id, Material.id.in_(material_ids))))

    def get_knowledge_point(self, course_id: int, knowledge_point_id: int) -> KnowledgePoint | None:
        return self.db.scalar(
            select(KnowledgePoint).where(
                KnowledgePoint.id == knowledge_point_id,
                KnowledgePoint.course_id == course_id,
            )
        )

    def add(self, job: AiJob) -> AiJob:
        self.db.add(job)
        self.db.flush()
        return job

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()

    def refresh(self, instance: object) -> None:
        self.db.refresh(instance)


class AgentJobContext:
    def __init__(self, job_id: int, *, session_factory=SessionLocal) -> None:
        self.job_id = job_id
        self.session_factory = session_factory

    def before_node(self, stage: str) -> None:
        with self.session_factory() as db:
            job = db.scalar(select(AiJob).where(AiJob.id == self.job_id).with_for_update())
            if job is None:
                raise AiJobCancelled("任务已不存在。")
            if job.status in {"cancelling", "cancelled"} or job.cancel_requested_at is not None:
                now = datetime.now(UTC)
                job.status = "cancelled"
                job.stage = "cancelled"
                job.label = "任务已取消"
                job.completed_at = now
                job.heartbeat_at = now
                job.updated_at = now
                db.commit()
                raise AiJobCancelled("任务已取消。")
            job.heartbeat_at = datetime.now(UTC)
            job.stage = stage
            db.commit()

    def check_cancelled(self) -> None:
        with self.session_factory() as db:
            job = db.scalar(select(AiJob).where(AiJob.id == self.job_id).with_for_update())
            if job is None or job.status in {"cancelling", "cancelled"} or job.cancel_requested_at is not None:
                raise AiJobCancelled("任务已取消。")
            job.heartbeat_at = datetime.now(UTC)
            db.commit()

    def after_node(
        self,
        *,
        name: str,
        label: str,
        progress_percent: int,
        status: str,
        resource_type: str | None = None,
    ) -> None:
        with self.session_factory() as db:
            job = db.scalar(select(AiJob).where(AiJob.id == self.job_id).with_for_update())
            if job is None:
                return
            now = datetime.now(UTC)
            progress = dict(job.progress_json or {})
            steps = [dict(item) for item in progress.get("steps", []) if isinstance(item, dict)]
            key = f"{name}:{resource_type or ''}"
            item = {
                "name": name,
                "label": label,
                "status": status,
                "progress_percent": max(0, min(100, int(progress_percent))),
                "resource_type": resource_type,
                "updated_at": iso_timestamp(now),
                "_key": key,
            }
            existing_index = next((index for index, value in enumerate(steps) if value.get("_key") == key), None)
            if existing_index is None:
                steps.append(item)
            else:
                steps[existing_index] = item
            progress["steps"] = steps
            job.progress_json = progress
            job.progress_percent = max(int(job.progress_percent or 0), int(progress_percent))
            job.stage = name
            job.label = label
            job.heartbeat_at = now
            job.updated_at = now
            db.commit()


class AiJobService:
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

    def create_course_builder_job(
        self,
        user: User,
        *,
        material_ids: list[int],
        course_title: str,
        idempotency_key: str | None,
    ) -> AiJobResponse:
        normalized_ids = [item for item in dict.fromkeys(material_ids) if item > 0]
        if not normalized_ids:
            raise AiJobValidationError("至少选择一份资料。")
        materials = self.repository.get_materials_for_user(user.id, normalized_ids)
        if len(materials) != len(normalized_ids):
            raise AiJobNotFoundError("资料不存在或无权访问。")
        if any(material.parse_status != "completed" for material in materials):
            raise AiJobValidationError("只能使用已解析资料生成课程。")
        return self._create(
            user,
            workflow="course_builder",
            course_id=None,
            request_json={"material_ids": normalized_ids, "course_title": " ".join(course_title.split())[:255]},
            idempotency_key=idempotency_key,
        )

    def create_resource_generation_job(
        self,
        user: User,
        *,
        course_id: int,
        knowledge_point_id: int | None,
        resource_types: list[str],
        learning_goal: str,
        difficulty: str,
        idempotency_key: str | None,
    ) -> AiJobResponse:
        if self.repository.get_course_for_user(user.id, course_id) is None:
            raise AiJobNotFoundError("课程不存在或无权访问。")
        if knowledge_point_id is not None and self.repository.get_knowledge_point(course_id, knowledge_point_id) is None:
            raise AiJobNotFoundError("知识点不存在或不属于当前课程。")
        unique_types = [item for item in dict.fromkeys(resource_types) if item in {"doc", "mindmap", "quiz", "code", "slide", "animation"}]
        if not unique_types:
            raise AiJobValidationError("至少选择一种资源类型。")
        if difficulty not in {"easy", "medium", "hard"}:
            raise AiJobValidationError("不支持的资源难度。")
        return self._create(
            user,
            workflow="resource_generation",
            course_id=course_id,
            request_json={
                "course_id": course_id,
                "knowledge_point_id": knowledge_point_id,
                "resource_types": unique_types,
                "learning_goal": " ".join(learning_goal.split())[:500],
                "difficulty": difficulty,
            },
            idempotency_key=idempotency_key,
        )

    def create_embedding_reindex_job(
        self,
        user: User,
        *,
        config_id: int | None,
        idempotency_key: str | None,
    ) -> AiJobResponse:
        setting = self.repository.db.scalar(
            select(ModelSetting).where(
                ModelSetting.user_id == user.id,
                ModelSetting.is_embedding_default.is_(True),
            )
        )
        if setting is None or not setting.embedding_model:
            raise AiJobValidationError("请先保存并设定默认向量配置。")
        if config_id is not None and int(setting.id) != config_id:
            raise AiJobValidationError("只能使用当前默认向量配置重建索引。")
        return self._create(
            user,
            workflow="embedding_reindex",
            course_id=None,
            request_json={"config_id": int(setting.id), "scope": "all_user_chunks"},
            idempotency_key=idempotency_key,
        )

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
    ) -> AiJobResponse:
        key = self._normalize_key(idempotency_key)
        existing = self.repository.get_by_idempotency(user.id, key)
        if existing is not None:
            return ai_job_to_api(existing, max_retries=self.max_retries)
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
        original.attempt_count = next_attempt
        self.repository.commit()
        request = dict(original.request_json or {})
        if original.workflow == "embedding_reindex":
            config_id = int(request["config_id"]) if request.get("config_id") else None
            setting = self.repository.db.scalar(
                select(ModelSetting).where(
                    ModelSetting.user_id == user.id,
                    ModelSetting.id == config_id,
                    ModelSetting.is_embedding_default.is_(True),
                )
            )
            if setting is None or not setting.embedding_model:
                raise AiJobValidationError("当前默认向量配置已变化，请重新发起重建任务。")
            return self._create(
                user,
                workflow="embedding_reindex",
                course_id=None,
                request_json=request,
                idempotency_key=f"retry-{original.id}-{uuid4().hex}",
                retry_of_job_id=original.id,
                attempt_count=next_attempt,
            )
        if original.workflow == "course_builder":
            material_ids = [int(item) for item in request.get("material_ids", [])]
            materials = self.repository.get_materials_for_user(user.id, material_ids)
            if len(materials) != len(material_ids):
                raise AiJobNotFoundError("资料不存在或无权访问。")
            if any(material.parse_status != "completed" for material in materials):
                raise AiJobValidationError("只能使用已解析资料重新生成课程。")
            return self._create(
                user,
                workflow=original.workflow,
                course_id=None,
                request_json=request,
                idempotency_key=f"retry-{original.id}-{uuid4().hex}",
                retry_of_job_id=original.id,
                attempt_count=next_attempt,
            )
        course_id = int(request["course_id"])
        if self.repository.get_course_for_user(user.id, course_id) is None:
            raise AiJobNotFoundError("课程不存在或无权访问。")
        knowledge_point_id = request.get("knowledge_point_id")
        if knowledge_point_id is not None and self.repository.get_knowledge_point(course_id, int(knowledge_point_id)) is None:
            raise AiJobNotFoundError("知识点不存在或不属于当前课程。")
        return self._create(
            user,
            workflow=original.workflow,
            course_id=course_id,
            request_json=request,
            idempotency_key=f"retry-{original.id}-{uuid4().hex}",
            retry_of_job_id=original.id,
            attempt_count=next_attempt,
        )

    def run_job(self, job_id: int) -> AiJobResponse:
        job = self.repository.get_job(job_id, for_update=True)
        if job is None:
            raise AiJobNotFoundError("AI 任务不存在。")
        if job.status in TERMINAL_STATUSES:
            return ai_job_to_api(job, max_retries=self.max_retries)
        now = datetime.now(UTC)
        job.status = "running"
        job.stage = "starting"
        job.label = "正在启动任务"
        job.started_at = job.started_at or now
        job.heartbeat_at = now
        job.updated_at = now
        self.repository.commit()
        self.repository.refresh(job)
        context = AgentJobContext(int(job.id))
        try:
            user = self.repository.get_user(int(job.user_id))
            if user is None:
                raise AiJobNotFoundError("任务用户不存在。")
            if job.workflow == "course_builder":
                result = self._run_course_builder(user, job, context)
            elif job.workflow == "resource_generation":
                result = self._run_resource_generation(user, job, context)
            elif job.workflow == "embedding_reindex":
                result = self._run_embedding_reindex(user, job, context)
            else:
                raise AiJobValidationError("不支持的 AI 任务类型。")
            refreshed = self.repository.get_job(job_id, for_update=True) or job
            if refreshed.status in {"cancelling", "cancelled"} or refreshed.cancel_requested_at is not None:
                raise AiJobCancelled("任务已取消。")
            finished = datetime.now(UTC)
            refreshed.status = "completed"
            refreshed.progress_percent = 100
            refreshed.stage = "completed"
            refreshed.label = "任务已完成"
            refreshed.result_json = result
            refreshed.error_code = None
            refreshed.error_message = None
            refreshed.heartbeat_at = finished
            refreshed.completed_at = finished
            refreshed.updated_at = finished
            self.repository.commit()
            self.repository.refresh(refreshed)
            return ai_job_to_api(refreshed, max_retries=self.max_retries)
        except AiJobCancelled:
            self.repository.rollback()
            cancelled = self.repository.get_job(job_id, for_update=True) or job
            now = datetime.now(UTC)
            cancelled.status = "cancelled"
            cancelled.stage = "cancelled"
            cancelled.label = "任务已取消"
            cancelled.completed_at = now
            cancelled.heartbeat_at = now
            cancelled.updated_at = now
            self.repository.commit()
            return ai_job_to_api(cancelled, max_retries=self.max_retries)
        except Exception as exc:
            self.repository.rollback()
            failed = self.repository.get_job(job_id, for_update=True) or job
            self._mark_failed(failed, self._safe_error_code(exc), self._safe_error_message(exc))
            return ai_job_to_api(failed, max_retries=self.max_retries)

    def _run_course_builder(self, user: User, job: AiJob, context: AgentJobContext) -> dict[str, Any]:
        from backend.app.agents.course_builder import CourseBuilderGraphRunner
        from backend.app.providers.openai_compatible import OpenAICompatibleChatProvider
        from backend.app.services.courses import CourseService, SqlAlchemyCourseRepository
        from backend.app.services.embeddings import EmbeddingService
        from backend.app.services.material_retrieval import MaterialChunkingService
        from backend.app.services.model_settings import ModelSettingsService, SqlAlchemyModelSettingsRepository

        model_service = ModelSettingsService(
            repository=SqlAlchemyModelSettingsRepository(self.repository.db),
            settings=self.settings,
            provider=OpenAICompatibleChatProvider(),
        )
        service = CourseService(
            SqlAlchemyCourseRepository(self.repository.db),
            embedding_service=EmbeddingService(model_service),
            model_service=model_service,
            trace_recorder=AgentTraceRecorder(),
            chunking_service=MaterialChunkingService(),
        )
        request = dict(job.request_json or {})
        result = CourseBuilderGraphRunner(service).generate(
            user=user,
            material_ids=[int(item) for item in request.get("material_ids", [])],
            course_title=str(request.get("course_title") or ""),
            trace_id=job.agent_trace_id,
            job_context=context,
        )
        return {"course_id": result.course.id, "knowledge_point_count": len(result.knowledge_points), "warnings": []}

    def _run_resource_generation(self, user: User, job: AiJob, context: AgentJobContext) -> dict[str, Any]:
        from backend.app.providers.openai_compatible import OpenAICompatibleChatProvider
        from backend.app.services.model_settings import ModelSettingsService, SqlAlchemyModelSettingsRepository
        from backend.app.services.resources import ResourceGenerationGraphRunner, ResourceGenerationService, SqlAlchemyResourceRepository

        model_service = ModelSettingsService(
            repository=SqlAlchemyModelSettingsRepository(self.repository.db),
            settings=self.settings,
            provider=OpenAICompatibleChatProvider(),
        )
        service = ResourceGenerationService(
            SqlAlchemyResourceRepository(self.repository.db),
            model_settings_service=model_service,
            trace_recorder=AgentTraceRecorder(),
        )
        request = dict(job.request_json or {})
        course = service._require_course(user, int(request["course_id"]))
        knowledge_point = service._resolve_knowledge_point(course.id, request.get("knowledge_point_id"))
        result = ResourceGenerationGraphRunner(service).generate(
            user=user,
            course=course,
            knowledge_point=knowledge_point,
            resource_types=[str(item) for item in request.get("resource_types", [])],
            learning_goal=str(request.get("learning_goal") or ""),
            difficulty=str(request.get("difficulty") or "medium"),
            trace_id=job.agent_trace_id,
            job_context=context,
        )
        return {
            "course_id": str(course.id),
            "resource_ids": [resource.id for resource in result.resources],
            "failed_resource_types": result.failed_resource_types,
            "warnings": result.warnings,
        }

    def _run_embedding_reindex(self, user: User, job: AiJob, context: AgentJobContext) -> dict[str, Any]:
        from backend.app.providers.openai_compatible import OpenAICompatibleChatProvider
        from backend.app.services.embeddings import EmbeddingService
        from backend.app.services.model_settings import ModelSettingsService, SqlAlchemyModelSettingsRepository

        model_service = ModelSettingsService(
            repository=SqlAlchemyModelSettingsRepository(self.repository.db),
            settings=self.settings,
            provider=OpenAICompatibleChatProvider(),
        )
        profile = EmbeddingService(model_service).expected_profile(user)
        if profile is None:
            raise AiJobValidationError("当前默认向量配置不可用，请先完成连接测试。")
        course_chunks = list(
            self.repository.db.scalars(
                select(KnowledgeChunk)
                .join(Course, Course.id == KnowledgeChunk.course_id)
                .where(Course.owner_id == user.id)
                .order_by(KnowledgeChunk.id)
            )
        )
        material_chunks = list(
            self.repository.db.scalars(
                select(MaterialChunk)
                .join(Material, Material.id == MaterialChunk.material_id)
                .where(Material.user_id == user.id)
                .order_by(MaterialChunk.id)
            )
        )
        targets: list[Any] = [*course_chunks, *material_chunks]
        total = len(targets)
        if total == 0:
            return {"embedded_chunk_count": 0, "embedding_dimension": profile.dimension, "warnings": []}
        embedding_service = EmbeddingService(model_service)
        completed = 0
        for start in range(0, total, 24):
            context.check_cancelled()
            batch_targets = targets[start : start + 24]
            batch = embedding_service.embed_documents(user, [chunk.content for chunk in batch_targets])
            if len(batch.vectors) != len(batch_targets):
                raise AiJobValidationError("向量服务未返回完整结果，可稍后重试。")
            now = datetime.now(UTC)
            for chunk, vector in zip(batch_targets, batch.vectors, strict=True):
                chunk.embedding = vector
                chunk.embedding_provider = batch.source
                chunk.embedding_model = batch.model
                chunk.embedding_dimension = batch.dimension
                chunk.embedding_profile_hash = batch.profile_hash
                chunk.embedding_updated_at = now
                chunk.metadata_json = {
                    **(chunk.metadata_json or {}),
                    "embedding_source": batch.source,
                    "embedding_model": batch.model,
                    "embedding_dimension": batch.dimension,
                    "embedding_profile_hash": batch.profile_hash,
                }
                self.repository.db.add(chunk)
            self.repository.db.commit()
            completed += len(batch_targets)
            context.after_node(
                name="embedding_reindex",
                label=f"已重建 {completed}/{total} 个资料片段",
                progress_percent=min(99, round(completed / total * 100)),
                status="completed" if completed == total else "running",
            )
        return {
            "embedded_chunk_count": completed,
            "embedding_dimension": profile.dimension,
            "embedding_provider": profile.provider,
            "embedding_model": profile.model,
            "warnings": [],
        }

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

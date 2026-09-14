from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from backend.app.agents.runtime import AgentTraceRecorder
from backend.app.models import (
    AiJob,
    Course,
    KnowledgeChunk,
    Material,
    MaterialChunk,
    User,
)
from backend.app.schemas.ai_jobs import AiJobResponse, ai_job_to_api
from backend.app.services.ai_job_contracts import (
    TERMINAL_STATUSES,
    AiJobCancelled,
    AiJobNotFoundError,
    AiJobValidationError,
)
from backend.app.services.ai_job_runtime import AgentJobContext
from backend.app.services.ai_capabilities import AI_CAPABILITIES, validate_capability_scope
from backend.app.services.ai_job_recovery import recover_committed_result


class AiJobExecutionMixin:
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
        capability = AI_CAPABILITIES.get(job.workflow)
        context = AgentJobContext(
            int(job.id),
            timeout_seconds=self.settings.ai_job_timeout_seconds if capability is not None else None,
        )
        committed_result = None
        try:
            context.check_cancelled()
            user = self.repository.get_user(int(job.user_id))
            if user is None:
                raise AiJobNotFoundError("任务用户不存在。")
            if capability is not None:
                request = capability.validate_input(job.request_json, job.course_id)
                validate_capability_scope(self.repository, user.id, request)
            recovered = recover_committed_result(self.repository, job)
            if recovered is not None:
                result = recovered
            elif job.workflow == "course_builder":
                result = self._run_course_builder(user, job, context)
            elif job.workflow == "resource_generation":
                result = self._run_resource_generation(user, job, context)
            elif job.workflow == "embedding_reindex":
                result = self._run_embedding_reindex(user, job, context)
            elif job.workflow == "material_ingestion":
                result = self._run_material_ingestion(user, job, context)
            elif job.workflow == "path_planning":
                result = self._run_path_planning(user, job, context)
            elif job.workflow == "practice_generation":
                result = self._run_practice_generation(user, job, context)
            elif job.workflow == "report_generation":
                result = self._run_report_generation(user, job, context)
            else:
                raise AiJobValidationError("不支持的 AI 任务类型。")
            if capability is not None:
                result = capability.validate_output(result, job.course_id)
                if job.workflow in {"path_planning", "resource_generation"}:
                    committed_result = result
            context.check_cancelled()
            refreshed = self.repository.get_job(job_id, for_update=True) or job
            if refreshed.status in {"cancelling", "cancelled"} or refreshed.cancel_requested_at is not None:
                raise AiJobCancelled("任务已取消。")
            finished = datetime.now(UTC)
            refreshed.status = "completed"
            refreshed.progress_percent = 100
            refreshed.stage = "completed"
            refreshed.label = "任务已完成"
            model_task_summary = dict((refreshed.progress_json or {}).get("model_task_summary") or {})
            refreshed.result_json = {
                **result,
                "model_task_summary": model_task_summary,
            }
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
            if committed_result is not None:
                cancelled.result_json = {**committed_result, "domain_committed": True}
            self.repository.commit()
            return ai_job_to_api(cancelled, max_retries=self.max_retries)
        except Exception as exc:
            self.repository.rollback()
            if job.workflow == "material_ingestion":
                self._mark_material_ingestion_failed(job, exc)
            failed = self.repository.get_job(job_id, for_update=True) or job
            if committed_result is not None:
                failed.result_json = {**committed_result, "domain_committed": True}
            self._mark_failed(failed, self._safe_error_code(exc), self._safe_error_message(exc))
            return ai_job_to_api(failed, max_retries=self.max_retries)

    def _run_material_ingestion(self, user: User, job: AiJob, context: AgentJobContext) -> dict[str, Any]:
        from backend.app.agents.material_ingestion import MaterialIngestionGraphRunner
        from backend.app.providers.openai_compatible import OpenAICompatibleChatProvider
        from backend.app.services.model_settings import ModelSettingsService, SqlAlchemyModelSettingsRepository

        request = dict(job.request_json or {})
        material_id = int(request.get("material_id") or 0)
        materials = self.repository.get_materials_for_user(user.id, [material_id])
        if len(materials) != 1:
            raise AiJobNotFoundError("资料不存在或无权访问。")
        material = materials[0]
        material.ingestion_status = "running"
        material.metadata_json = {**(material.metadata_json or {}), "detail": "正在精细解析"}
        self.repository.commit()
        model_service = ModelSettingsService(
            repository=SqlAlchemyModelSettingsRepository(self.repository.db),
            settings=self.settings,
            provider=OpenAICompatibleChatProvider(),
        )
        return MaterialIngestionGraphRunner(
            self.repository.db,
            settings=self.settings,
            model_service=model_service,
            trace_recorder=AgentTraceRecorder(),
        ).run(user=user, material=material, trace_id=job.agent_trace_id, job_context=context)

    def _mark_material_ingestion_failed(self, job: AiJob, exc: Exception) -> None:
        request = dict(job.request_json or {})
        material_id = int(request.get("material_id") or 0)
        if material_id <= 0:
            return
        material = self.repository.db.get(Material, material_id)
        if material is None or material.user_id != job.user_id:
            return
        previous_state = request.get("previous_material_state")
        preserve_confirmed = (
            isinstance(previous_state, dict)
            and previous_state.get("ingestion_status") == "confirmed"
            and previous_state.get("parse_status") == "completed"
        )
        material.ingestion_status = "confirmed" if preserve_confirmed else "failed"
        material.parse_status = "completed" if preserve_confirmed else "failed"
        diagnostic = getattr(exc, "quality", None)
        failure = {
            "error_code": self._safe_error_code(exc),
            "risk_flags": diagnostic.get("risk_flags", []) if isinstance(diagnostic, dict) else [],
        }
        if not preserve_confirmed:
            material.quality_json = {
                **(diagnostic if isinstance(diagnostic, dict) else (material.quality_json or {})),
                "passed": False,
                "error_code": failure["error_code"],
                "warnings": list(dict.fromkeys([
                    *(
                        diagnostic.get("warnings", [])
                        if isinstance(diagnostic, dict) and isinstance(diagnostic.get("warnings"), list)
                        else []
                    ),
                    "精细解析未通过，原文件已保留。",
                ])),
            }
        material.metadata_json = {
            **(material.metadata_json or {}),
            "detail": previous_state.get("detail") or "目录已确认，可生成课程" if preserve_confirmed else "精细解析失败",
            "last_ingestion_failure": failure,
        }
        self.repository.commit()

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
        from backend.app.services.code_verifier import HttpCodeVerifier
        from backend.app.services.embeddings import EmbeddingService
        from backend.app.services.model_settings import ModelSettingsService, SqlAlchemyModelSettingsRepository
        from backend.app.services.rag import RagService, SqlAlchemyRagRepository
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
            code_verifier=HttpCodeVerifier(
                self.settings.code_verifier_url,
                timeout_seconds=self.settings.code_verifier_timeout_seconds,
            ),
        )
        request = dict(job.request_json or {})
        course = service._require_course(user, int(request["course_id"]))
        knowledge_point_id = request.get("knowledge_point_id")
        matched_evidence_chunk_ids = [
            int(item) for item in request.get("evidence_chunk_ids", []) if str(item).isdigit()
        ][:8]
        if knowledge_point_id is None and request.get("tutor_message_id") is not None:
            context.before_node("resolve_context", "正在匹配课程知识点")
            query = str(request.get("learning_goal") or "").strip()
            if not query:
                raise AiJobValidationError("对话资源缺少可用于匹配课程知识点的学习目标。")
            try:
                search_result = RagService(
                    SqlAlchemyRagRepository(self.repository.db),
                    embedding_service=EmbeddingService(model_service),
                    rerank_service=model_service,
                ).search(user=user, course_id=course.id, query=query, top_k=3)
            except Exception as exc:
                raise AiJobValidationError("暂时无法把对话主题匹配到课程知识点，请稍后重试。") from exc
            matched, matched_evidence_chunk_ids = self._select_tutor_resource_match(search_result.results)
            if matched is None:
                raise AiJobValidationError("没有在所选课程中找到与本次对话匹配的知识点。")
            knowledge_point_id = int(matched.knowledge_point_id)
        knowledge_point = service._resolve_knowledge_point(course.id, knowledge_point_id)
        source_resource = (
            service.repository.get_resource_for_user(user.id, int(request["source_resource_id"]))
            if request.get("source_resource_id") is not None
            else None
        )
        if str(request.get("generation_action") or "new") in {"alternative", "refine"} and source_resource is None:
            raise AiJobNotFoundError("来源资源不存在或无权访问。")
        result = ResourceGenerationGraphRunner(service).generate(
            user=user,
            course=course,
            knowledge_point=knowledge_point,
            resource_types=[str(item) for item in request.get("resource_types", [])],
            learning_goal=str(request.get("learning_goal") or ""),
            difficulty=str(request.get("difficulty") or "medium"),
            generation_action=str(request.get("generation_action") or "new"),
            source_resource=source_resource,
            path_task_id=(int(request["path_task_id"]) if request.get("path_task_id") is not None else None),
            trace_id=job.agent_trace_id,
            job_context=context,
        )
        return {
            "course_id": str(course.id),
            "knowledge_point_id": str(knowledge_point.id) if knowledge_point is not None else None,
            "evidence_chunk_ids": matched_evidence_chunk_ids,
            "path_task_id": str(request["path_task_id"]) if request.get("path_task_id") is not None else None,
            "resource_ids": [resource.id for resource in result.resources],
            "failed_resource_types": result.failed_resource_types,
            "warnings": result.warnings,
        }

    @staticmethod
    def _select_tutor_resource_match(results: list[Any]) -> tuple[Any | None, list[int]]:
        matched = next((item for item in results if item.knowledge_point_id is not None), None)
        if matched is None:
            return None, []
        knowledge_point_id = int(matched.knowledge_point_id)
        evidence_chunk_ids = [
            int(item.chunk_id)
            for item in results
            if item.knowledge_point_id == knowledge_point_id
        ][:8]
        return matched, evidence_chunk_ids

    def _run_path_planning(self, user: User, job: AiJob, context: AgentJobContext) -> dict[str, Any]:
        from backend.app.agents.path_planning import PathPlanningGraphRunner
        from backend.app.providers.openai_compatible import OpenAICompatibleChatProvider
        from backend.app.services.model_settings import ModelSettingsService, SqlAlchemyModelSettingsRepository
        from backend.app.services.paths import PathService, SqlAlchemyPathRepository

        request = dict(job.request_json or {})
        course_id = int(request.get("course_id") or job.course_id or 0)
        if self.repository.get_course_for_user(user.id, course_id) is None:
            raise AiJobNotFoundError("课程不存在或无权访问。")
        model_service = ModelSettingsService(
            repository=SqlAlchemyModelSettingsRepository(self.repository.db),
            settings=self.settings,
            provider=OpenAICompatibleChatProvider(),
        )
        service = PathService(
            SqlAlchemyPathRepository(self.repository.db),
            model_service=model_service,
            trace_recorder=AgentTraceRecorder(),
        )
        trigger = str(request.get("trigger") or "manual")
        previous = service.repository.get_active_path(user.id, course_id)
        result = PathPlanningGraphRunner(service).run(
            user=user,
            course_id=course_id,
            trigger=trigger,
            assessment_session_id=(
                int(request["assessment_session_id"])
                if request.get("assessment_session_id") is not None
                else None
            ),
            previous_path=previous,
            draft=bool(request.get("draft")),
            trace_id=job.agent_trace_id,
            job_context=context,
        )
        detail = result.detail
        path = detail.path if detail is not None else None
        plan = path.plan_json if path is not None else {}
        return {
            "course_id": course_id,
            "path_id": path.id if path is not None else None,
            "generation_mode": str(plan.get("generation_mode") or "deterministic_source"),
            "preserved_task_count": result.preserved_task_count,
            "agent_trace_id": result.trace_id,
            "warnings": list(plan.get("warnings") or []),
        }

    def _run_practice_generation(self, user: User, job: AiJob, context: AgentJobContext) -> dict[str, Any]:
        from backend.app.agents.assessment import AssessmentGraphRunner
        from backend.app.providers.openai_compatible import OpenAICompatibleChatProvider
        from backend.app.services.model_settings import ModelSettingsService, SqlAlchemyModelSettingsRepository
        from backend.app.services.practice import PracticeService, SqlAlchemyPracticeRepository

        request = dict(job.request_json or {})
        course_id = int(request.get("course_id") or job.course_id or 0)
        if self.repository.get_course_for_user(user.id, course_id) is None:
            raise AiJobNotFoundError("课程不存在或无权访问。")
        model_service = ModelSettingsService(
            repository=SqlAlchemyModelSettingsRepository(self.repository.db),
            settings=self.settings,
            provider=OpenAICompatibleChatProvider(),
        )
        service = PracticeService(
            SqlAlchemyPracticeRepository(self.repository.db),
            model_service=model_service,
            trace_recorder=AgentTraceRecorder(),
        )
        detail = AssessmentGraphRunner(service).create_session(
            user=user,
            course_id=course_id,
            knowledge_point_ids=[int(item) for item in request.get("knowledge_point_ids", [])],
            weakness_item_id=(int(request["weakness_item_id"]) if request.get("weakness_item_id") is not None else None),
            question_count=int(request.get("question_count") or 5),
            difficulty=str(request.get("difficulty") or "adaptive"),
            trace_id=job.agent_trace_id,
            job_context=context,
        )
        return {
            "course_id": course_id,
            "session_id": detail.id,
            "question_count": len(detail.questions),
            "agent_trace_id": detail.agent_trace_id,
            "warnings": [],
        }

    def _run_report_generation(self, user: User, job: AiJob, context: AgentJobContext) -> dict[str, Any]:
        from backend.app.agents.reporting import ReportGraphRunner
        from backend.app.providers.openai_compatible import OpenAICompatibleChatProvider
        from backend.app.services.model_settings import ModelSettingsService, SqlAlchemyModelSettingsRepository
        from backend.app.services.reports import ReportService, SqlAlchemyReportRepository

        request = dict(job.request_json or {})
        course_id = int(request.get("course_id") or job.course_id or 0)
        if self.repository.get_course_for_user(user.id, course_id) is None:
            raise AiJobNotFoundError("课程不存在或无权访问。")
        model_service = ModelSettingsService(
            repository=SqlAlchemyModelSettingsRepository(self.repository.db),
            settings=self.settings,
            provider=OpenAICompatibleChatProvider(),
        )
        service = ReportService(
            SqlAlchemyReportRepository(self.repository.db),
            model_service=model_service,
            trace_recorder=AgentTraceRecorder(),
        )
        detail = ReportGraphRunner(service).run(
            user=user,
            course_id=course_id,
            practice_session_id=(
                int(request["practice_session_id"])
                if request.get("practice_session_id") is not None
                else None
            ),
            trace_id=job.agent_trace_id,
            job_context=context,
        )
        return {
            "course_id": course_id,
            "report_id": detail.id,
            "agent_trace_id": detail.agent_trace_id,
            "warnings": [],
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
            raise AiJobValidationError("当前默认向量服务不可用，请先完成连接验证。")
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
        # Bailian's text-embedding-v4 endpoint currently accepts at most eight
        # inputs per request in this deployment. Keeping the reindex batch
        # bounded also prevents one provider limit from aborting a full rebuild.
        for start in range(0, total, 8):
            context.check_cancelled()
            batch_targets = targets[start : start + 8]
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
            context.check_cancelled()
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

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Callable

from sqlalchemy import select

from backend.app.models import (
    PracticeAnswer,
    PracticeSession,
    User,
    WeaknessReviewItem,
)
from backend.app.schemas.ai_jobs import AiJobResponse, ai_job_to_api
from backend.app.services.ai_job_contracts import (
    AiJobConflictError,
    AiJobNotFoundError,
    AiJobValidationError,
)
from backend.app.services.mastery_progress import is_review_due


class AiJobRequestMixin:
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
        if any(material.parse_status != "completed" or material.ingestion_status != "confirmed" for material in materials):
            raise AiJobConflictError("请先完成资料精细解析并确认目录，再生成课程。")
        return self._create(
            user,
            workflow="course_builder",
            course_id=None,
            request_json={"material_ids": normalized_ids, "course_title": " ".join(course_title.split())[:255]},
            idempotency_key=idempotency_key,
        )

    def create_material_ingestion_job(
        self,
        user: User,
        *,
        material_id: int,
        force: bool = False,
        idempotency_key: str | None,
    ) -> AiJobResponse:
        materials = self.repository.get_materials_for_user(user.id, [material_id])
        if len(materials) != 1:
            raise AiJobNotFoundError("资料不存在或无权访问。")
        material = materials[0]
        if Path(material.filename).suffix.lower() not in {".pdf", ".docx", ".pptx", ".txt", ".md", ".markdown"}:
            raise AiJobValidationError("当前文件格式不支持精细解析。")
        if material.ingestion_status == "confirmed" and not force:
            raise AiJobConflictError("资料目录已经确认；如需重建，请明确选择重新解析。")
        previous_state = {
            "parse_status": material.parse_status,
            "ingestion_status": material.ingestion_status,
            "detail": str((material.metadata_json or {}).get("detail") or ""),
        }
        material.ingestion_status = "queued"
        material.parse_status = "pending"
        material.metadata_json = {**(material.metadata_json or {}), "detail": "精细解析已排队"}
        self.repository.commit()
        return self._create(
            user,
            workflow="material_ingestion",
            course_id=None,
            request_json={
                "material_id": material_id,
                "force": bool(force),
                "previous_material_state": previous_state,
            },
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
        generation_action: str = "new",
        source_resource_id: int | None = None,
        path_task_id: int | None = None,
        tutor_message_id: int | None = None,
        evidence_chunk_ids: list[int] | None = None,
        on_created: Callable[[int], None] | None = None,
        idempotency_key: str | None = None,
    ) -> AiJobResponse:
        if self.repository.get_course_for_user(user.id, course_id) is None:
            raise AiJobNotFoundError("课程不存在或无权访问。")
        self._require_active_course(user.id, course_id)
        if knowledge_point_id is not None and self.repository.get_knowledge_point(course_id, knowledge_point_id) is None:
            raise AiJobNotFoundError("知识点不存在或不属于当前课程。")
        unique_types = [item for item in dict.fromkeys(resource_types) if item in {"doc", "mindmap", "quiz", "code", "slide", "animation", "video"}]
        if not unique_types:
            raise AiJobValidationError("至少选择一种资源类型。")
        if difficulty not in {"easy", "medium", "hard"}:
            raise AiJobValidationError("不支持的资源难度。")
        if path_task_id is not None:
            task = self.repository.get_learning_task_for_user(user.id, path_task_id)
            if task is None or task.course_id != course_id:
                raise AiJobNotFoundError("学习路径任务不存在或无权访问。")
        if generation_action not in {"new", "alternative", "refine"}:
            raise AiJobValidationError("不支持的资源生成动作。")
        source_resource = None
        if generation_action == "new":
            if source_resource_id is not None:
                raise AiJobValidationError("新建资源不能指定来源版本。")
        else:
            if source_resource_id is None:
                raise AiJobValidationError("重新生成必须指定来源资源。")
            source_resource = self.repository.get_resource_for_user(user.id, source_resource_id)
            if source_resource is None or source_resource.course_id != course_id:
                raise AiJobNotFoundError("来源资源不存在或无权访问。")
            if source_resource.status != "completed":
                raise AiJobValidationError("只能从已完成成果创建新版本。")
            if len(unique_types) != 1 or unique_types[0] != source_resource.resource_type:
                raise AiJobValidationError("重新生成只能生成与来源成果相同的资源类型。")
            if knowledge_point_id is not None and knowledge_point_id != source_resource.knowledge_point_id:
                raise AiJobValidationError("重新生成不能改变来源成果的知识点。")
            knowledge_point_id = source_resource.knowledge_point_id
            source_content = source_resource.content_json if isinstance(source_resource.content_json, dict) else {}
            source_intent = source_content.get("intent") if isinstance(source_content.get("intent"), dict) else {}
            learning_goal = str(source_intent.get("learning_goal") or learning_goal or "")[:500]
            source_metadata = source_content.get("metadata") if isinstance(source_content.get("metadata"), dict) else {}
            source_difficulty = str(source_metadata.get("difficulty") or difficulty)
            if source_difficulty in {"easy", "medium", "hard"}:
                difficulty = source_difficulty
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
                "generation_action": generation_action,
                "source_resource_id": source_resource_id,
                "path_task_id": path_task_id,
                "tutor_message_id": tutor_message_id,
                "evidence_chunk_ids": [int(item) for item in dict.fromkeys(evidence_chunk_ids or []) if int(item) > 0][:8],
            },
            idempotency_key=idempotency_key,
            before_commit=(lambda job: on_created(int(job.id))) if on_created is not None else None,
        )

    def create_path_task_resource_job(
        self,
        user: User,
        *,
        task_id: int,
        idempotency_key: str | None,
    ) -> AiJobResponse:
        task = self.repository.get_learning_task_for_user(user.id, task_id)
        if task is None or task.course_id is None:
            raise AiJobNotFoundError("学习路径任务不存在或无权访问。")
        active_path = self.repository.get_active_learning_path(user.id, int(task.course_id))
        if active_path is None or int(task.path_id) != int(active_path.id):
            raise AiJobConflictError("只能为当前有效学习路径生成本节资源。")
        if task.status == "completed":
            raise AiJobConflictError("该学习任务已经完成。")
        active_job = self.repository.get_active_resource_job_for_path_task(user.id, task.id)
        if active_job is not None:
            return ai_job_to_api(active_job, max_retries=self.max_retries)

        bundle = task.learning_bundle_json if isinstance(task.learning_bundle_json, dict) else {}
        raw_items = bundle.get("items") if isinstance(bundle.get("items"), list) else []
        if not raw_items:
            raise AiJobValidationError("当前任务没有可生成的本节学习安排。")
        recommended_resources = {
            int(resource_id): resource
            for resource_id in task.recommended_resource_ids or []
            if str(resource_id).isdigit()
            and (resource := self.repository.get_resource_for_user(user.id, int(resource_id))) is not None
        }
        missing_types: list[str] = []
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            resource_type = str(item.get("resource_type") or "")
            if resource_type not in {"doc", "mindmap", "quiz", "code", "slide", "animation", "video"}:
                raise AiJobValidationError("本节学习安排包含不支持的资源类型。")
            resource_id = item.get("resource_id")
            resource = (
                self.repository.get_resource_for_user(user.id, int(resource_id))
                if str(resource_id).isdigit()
                else None
            )
            ready = (
                resource is not None
                and resource.course_id == task.course_id
                and resource.status == "completed"
                and resource.resource_type == resource_type
            )
            if not ready:
                ready = any(
                    resource.course_id == task.course_id
                    and resource.status == "completed"
                    and resource.resource_type == resource_type
                    for resource in recommended_resources.values()
                )
            if not ready and resource_type not in missing_types:
                missing_types.append(resource_type)
        if not missing_types:
            raise AiJobConflictError("本节学习资源已经全部就绪。")

        difficulty = str(bundle.get("difficulty") or "medium")
        if difficulty not in {"easy", "medium", "hard"}:
            difficulty = "medium"
        learning_goal = " ".join(
            item for item in (str(task.title or "").strip(), str(bundle.get("rationale") or task.reason or "").strip()) if item
        )[:500]
        return self.create_resource_generation_job(
            user,
            course_id=int(task.course_id),
            knowledge_point_id=task.knowledge_point_id,
            resource_types=missing_types,
            learning_goal=learning_goal,
            difficulty=difficulty,
            generation_action="new",
            source_resource_id=None,
            path_task_id=task.id,
            idempotency_key=idempotency_key,
        )

    def create_practice_generation_job(
        self,
        user: User,
        *,
        course_id: int,
        knowledge_point_ids: list[int],
        question_count: int,
        difficulty: str,
        idempotency_key: str | None,
        weakness_item_id: int | None = None,
    ) -> AiJobResponse:
        if self.repository.get_course_for_user(user.id, course_id) is None:
            raise AiJobNotFoundError("课程不存在或无权访问。")
        self._require_active_course(user.id, course_id)
        if question_count < 1 or question_count > 12:
            raise AiJobValidationError("题目数量必须在 1 到 12 之间。")
        if difficulty not in {"adaptive", "easy", "medium", "hard"}:
            raise AiJobValidationError("练习难度只能是 adaptive、easy、medium 或 hard。")
        point_ids = [item for item in dict.fromkeys(knowledge_point_ids) if item > 0]
        if not point_ids or any(self.repository.get_knowledge_point(course_id, item) is None for item in point_ids):
            raise AiJobNotFoundError("知识点不存在或不属于当前课程。")
        if weakness_item_id is not None:
            weakness = self.repository.db.scalar(
                select(WeaknessReviewItem).where(
                    WeaknessReviewItem.id == weakness_item_id,
                    WeaknessReviewItem.user_id == user.id,
                    WeaknessReviewItem.course_id == course_id,
                )
            )
            if weakness is None or (weakness.status not in {"confirmed", "reviewing"} and not is_review_due(weakness)):
                raise AiJobNotFoundError("待复习弱点不存在、状态不可用或无权访问。")
            if weakness.knowledge_point_id not in point_ids:
                raise AiJobValidationError("针对性练习的知识点必须与待复习弱点一致。")
        active = self.repository.get_active_workflow_job(user.id, course_id, "practice_generation")
        if active is not None:
            active_request = active.request_json if isinstance(active.request_json, dict) else {}
            if weakness_item_id is not None and int(active_request.get("weakness_item_id") or 0) != weakness_item_id:
                raise AiJobConflictError("当前课程已有其他练习正在生成，请完成后再开始这次针对性再测。")
            return ai_job_to_api(active, max_retries=self.max_retries)
        return self._create(
            user,
            workflow="practice_generation",
            course_id=course_id,
            request_json={
                "course_id": course_id,
                "knowledge_point_ids": point_ids,
                "question_count": question_count,
                "difficulty": difficulty,
                **({"weakness_item_id": weakness_item_id} if weakness_item_id is not None else {}),
            },
            idempotency_key=idempotency_key,
        )

    def create_report_generation_job(
        self,
        user: User,
        *,
        course_id: int,
        practice_session_id: int | None,
        idempotency_key: str | None,
    ) -> AiJobResponse:
        if self.repository.get_course_for_user(user.id, course_id) is None:
            raise AiJobNotFoundError("课程不存在或无权访问。")
        self._require_active_course(user.id, course_id)
        if practice_session_id is not None:
            session = self.repository.get_practice_session_for_user(user.id, practice_session_id)
            if session is None or int(session.course_id) != course_id:
                raise AiJobNotFoundError("练习不存在或无权访问。")
        active = self.repository.get_active_workflow_job(user.id, course_id, "report_generation")
        if active is not None:
            return ai_job_to_api(active, max_retries=self.max_retries)
        return self._create(
            user,
            workflow="report_generation",
            course_id=course_id,
            request_json={
                "course_id": course_id,
                "practice_session_id": practice_session_id,
            },
            idempotency_key=idempotency_key,
        )

    def create_path_planning_job(
        self,
        user: User,
        *,
        course_id: int,
        idempotency_key: str | None,
        trigger: str = "manual",
        assessment_session_id: int | None = None,
    ) -> AiJobResponse:
        if self.repository.get_course_for_user(user.id, course_id) is None:
            raise AiJobNotFoundError("课程不存在或无权访问。")
        self._require_active_course(user.id, course_id)
        if trigger not in {"manual", "assessment"}:
            raise AiJobValidationError("不支持的路径规划触发方式。")
        active = self.repository.get_active_path_job(user.id, course_id)
        if active is not None:
            return ai_job_to_api(active, max_retries=self.max_retries)
        return self._create(
            user,
            workflow="path_planning",
            course_id=course_id,
            request_json={
                "course_id": course_id,
                "trigger": trigger,
                "assessment_session_id": assessment_session_id,
            },
            idempotency_key=idempotency_key,
        )

    def replan_after_assessment(self, user: User, course_id: int, assessment_session_id: int):
        from backend.app.services.paths import PathReplanResult

        if self.repository.get_active_learning_path(user.id, course_id) is None:
            return PathReplanResult(status="not_started", trace_id=None, detail=None)
        session = self.repository.db.scalar(
            select(PracticeSession).where(
                PracticeSession.id == assessment_session_id,
                PracticeSession.user_id == user.id,
                PracticeSession.course_id == course_id,
            )
        )
        if session is None:
            raise AiJobNotFoundError("练习记录不存在或无权访问。")
        answers = list(
            self.repository.db.scalars(
                select(PracticeAnswer)
                .where(PracticeAnswer.session_id == assessment_session_id, PracticeAnswer.user_id == user.id)
                .order_by(PracticeAnswer.id)
            )
        )
        evidence = [
            {
                "id": int(answer.id),
                "score": (answer.feedback_json or {}).get("score"),
                "grading_status": (answer.feedback_json or {}).get("grading_status"),
            }
            for answer in answers
            if (answer.feedback_json or {}).get("score") is not None
        ]
        digest = hashlib.sha256(
            json.dumps(evidence, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()[:20]
        job = self.create_path_planning_job(
            user,
            course_id=course_id,
            trigger="assessment",
            assessment_session_id=assessment_session_id,
            idempotency_key=f"assessment-path-{assessment_session_id}-{digest}",
        )
        return PathReplanResult(status="queued", trace_id=job.agent_trace_id, detail=None)

    def create_embedding_reindex_job(
        self,
        user: User,
        *,
        config_id: int | None,
        idempotency_key: str | None,
    ) -> AiJobResponse:
        del config_id
        from backend.app.providers.openai_compatible import OpenAICompatibleChatProvider
        from backend.app.services.model_settings import ModelSettingsService, SqlAlchemyModelSettingsRepository

        runtime = ModelSettingsService(
            repository=SqlAlchemyModelSettingsRepository(self.repository.db),
            settings=self.settings,
            provider=OpenAICompatibleChatProvider(),
        ).resolve_embedding_runtime_config(user)
        if not runtime.can_use_model:
            raise AiJobValidationError("系统尚未配置可用的向量模型。")
        return self._create(
            user,
            workflow="embedding_reindex",
            course_id=None,
            request_json={"scope": "all_user_chunks", "runtime_scope": "system"},
            idempotency_key=idempotency_key,
        )

from __future__ import annotations

import math
from decimal import Decimal
from typing import Any

from backend.app.agents.runtime import AgentTraceRecorder
from backend.app.models import (
    Course,
    GeneratedResource,
    KnowledgePoint,
    ResourceQualityScore,
    User,
)
from backend.app.providers.openai_compatible import ModelProviderError
from backend.app.schemas.resources import (
    GenerateResourcesResult,
    GeneratedResourceResponse,
    ResourceListResponse,
    generated_resource_to_api,
    quality_score_to_api,
)
from backend.app.schemas.personalization import PersonalizationFreshnessResponse
from backend.app.services.learner_context import context_service_from_repository
from backend.app.services.model_settings import ModelNotConfiguredError
from backend.app.services.code_verifier import CodeVerifier
from backend.app.services.embeddings import EmbeddingService
from backend.app.services.resource_artifacts import validate_resource_content
from backend.app.services.resource_content import (
    resource_context_keywords,
    safe_resource_excerpt,
    safe_resource_title,
)
from backend.app.services.resource_quality import (
    RESOURCE_PROMPT_VERSION,
    artifact_text,
    quality_risks,
    quality_summary,
)
from backend.app.services.resource_intent import (
    GenerationAction,
    evaluate_diversity,
    personalization_summary,
    quality_dimensions,
)
from backend.app.services.resource_modeling import ResourceModelingService
from backend.app.services.resource_contracts import (
    QUALITY_SCORE_NAMES,
    RESOURCE_TYPES,
    RESOURCE_TYPE_LABELS as RESOURCE_TYPE_LABELS,
    ResourceContext,
    ResourceDraft,
    ResourceGenerationError as ResourceGenerationError,
    ResourceGenerationState as ResourceGenerationState,
    ResourceModelService,
    ResourceNotFoundError,
    ResourceRepository,
    ResourceValidationError,
    resource_failure_message as resource_failure_message,
    resource_review_failure_message as resource_review_failure_message,
)
from backend.app.services.resource_graph import (
    ResourceGenerationGraphRunner as ResourceGenerationGraphRunner,
)
from backend.app.services.resource_repository import (
    SqlAlchemyResourceRepository as SqlAlchemyResourceRepository,
)
from backend.app.services.video_resources import VideoCurationService


class ResourceGenerationService:
    def __init__(
        self,
        repository: ResourceRepository,
        model_settings_service: ResourceModelService,
        trace_recorder: AgentTraceRecorder | None = None,
        code_verifier: CodeVerifier | None = None,
        video_curator: VideoCurationService | None = None,
    ) -> None:
        self.repository = repository
        self.model_settings_service = model_settings_service
        self.modeling_service = ResourceModelingService(model_settings_service)
        self.trace_recorder = trace_recorder or AgentTraceRecorder(repository_add_log=repository.add_agent_log)
        self.code_verifier = code_verifier
        self.video_curator = video_curator or VideoCurationService()

    def generate_resources(
        self,
        user: User,
        *,
        course_id: int,
        resource_types: list[str],
        knowledge_point_id: int | None = None,
        learning_goal: str = "",
        difficulty: str = "medium",
        generation_action: GenerationAction = "new",
        source_resource_id: int | None = None,
        path_task_id: int | None = None,
    ) -> GenerateResourcesResult:
        course = self._require_course(user, course_id)
        unique_types = self._normalize_resource_types(resource_types)
        if difficulty not in {"easy", "medium", "hard"}:
            raise ResourceValidationError("不支持的资源难度。")
        source_resource = self._resolve_source_resource(
            user=user,
            course=course,
            generation_action=generation_action,
            source_resource_id=source_resource_id,
            resource_types=unique_types,
            knowledge_point_id=knowledge_point_id,
        )
        if source_resource is not None:
            knowledge_point_id = source_resource.knowledge_point_id
            source_content = source_resource.content_json or {}
            source_intent = source_content.get("intent") if isinstance(source_content.get("intent"), dict) else {}
            learning_goal = str(source_intent.get("learning_goal") or learning_goal or "")[:500]
            source_metadata = source_content.get("metadata") if isinstance(source_content.get("metadata"), dict) else {}
            source_difficulty = str(source_metadata.get("difficulty") or difficulty)
            difficulty = source_difficulty if source_difficulty in {"easy", "medium", "hard"} else difficulty
        knowledge_point = self._resolve_knowledge_point(course.id, knowledge_point_id)
        if path_task_id is not None:
            task = self.repository.get_learning_task_for_user(user.id, path_task_id)
            if task is None or task.course_id != course.id:
                raise ResourceNotFoundError("学习路径任务不存在或无权访问。")
            if self.repository.is_path_draft(task.path_id):
                raise ResourceValidationError("请先确认计划，再生成草稿任务资源。")

        return ResourceGenerationGraphRunner(self).generate(
            user=user,
            course=course,
            knowledge_point=knowledge_point,
            resource_types=unique_types,
            learning_goal=learning_goal,
            difficulty=difficulty,
            generation_action=generation_action,
            source_resource=source_resource,
            path_task_id=path_task_id,
        )

    def _resolve_source_resource(
        self,
        *,
        user: User,
        course: Course,
        generation_action: GenerationAction,
        source_resource_id: int | None,
        resource_types: list[str],
        knowledge_point_id: int | None,
    ) -> GeneratedResource | None:
        if generation_action not in {"new", "alternative", "refine"}:
            raise ResourceValidationError("不支持的资源生成动作。")
        if generation_action == "new":
            if source_resource_id is not None:
                raise ResourceValidationError("新建资源不能指定来源版本。")
            return None
        if source_resource_id is None:
            raise ResourceValidationError("重新生成必须指定来源资源。")
        source = self.repository.get_resource_for_user(user.id, source_resource_id)
        if source is None or source.course_id != course.id:
            raise ResourceNotFoundError("来源资源不存在或无权访问。")
        if source.status != "completed":
            raise ResourceValidationError("只能从已完成成果创建新版本。")
        if len(resource_types) != 1 or resource_types[0] != source.resource_type:
            raise ResourceValidationError("重新生成只能生成与来源成果相同的资源类型。")
        if knowledge_point_id is not None and knowledge_point_id != source.knowledge_point_id:
            raise ResourceValidationError("重新生成不能改变来源成果的知识点。")
        return source

    def list_resources(
        self,
        user: User,
        *,
        course_id: int | None = None,
        resource_type: str | None = None,
    ) -> ResourceListResponse:
        if resource_type is not None and resource_type not in RESOURCE_TYPES:
            raise ResourceValidationError("不支持的资源类型。")
        if course_id is not None:
            self._require_course(user, course_id)
        resources = self.repository.list_resources(user.id, course_id=course_id, resource_type=resource_type)
        return ResourceListResponse(
            data=[self._resource_to_api(user.id, resource) for resource in resources],
            page=1,
            page_size=len(resources),
            total=len(resources),
        )

    def get_resource(self, user: User, resource_id: int) -> GeneratedResourceResponse:
        resource = self.repository.get_resource_for_user(user.id, resource_id)
        if resource is None:
            raise ResourceNotFoundError("资源不存在或无权访问。")
        return self._resource_to_api(user.id, resource)

    def delete_resource(self, user: User, resource_id: int) -> None:
        resource = self.repository.get_resource_for_user(user.id, resource_id, for_update=True)
        if resource is None:
            raise ResourceNotFoundError("资源不存在或无权访问。")

        for task in self.repository.list_learning_tasks_for_user(user.id):
            task.recommended_resource_ids = [
                value for value in (task.recommended_resource_ids or []) if str(value) != str(resource.id)
            ]
            bundle = dict(task.learning_bundle_json or {})
            items = bundle.get("items")
            if isinstance(items, list):
                bundle["items"] = [
                    item for item in items
                    if not isinstance(item, dict) or str(item.get("resource_id")) != str(resource.id)
                ]
                bundle["ready_count"] = len(bundle["items"])
                bundle["completed_count"] = sum(
                    1 for item in bundle["items"]
                    if isinstance(item, dict) and item.get("learning_status") == "completed"
                )
                task.learning_bundle_json = bundle

        try:
            self.repository.delete_resource(resource)
            self.repository.commit()
        except Exception:
            self.repository.rollback()
            raise

    def _resource_to_api(self, user_id: int, resource: GeneratedResource) -> GeneratedResourceResponse:
        context_service = context_service_from_repository(self.repository)
        personalization = None
        if context_service is not None:
            metadata = (resource.content_json or {}).get("metadata")
            freshness = context_service.freshness(
                metadata if isinstance(metadata, dict) else None,
                context_service.global_context(user_id).profile_applied_version,
            )
            personalization = PersonalizationFreshnessResponse(**freshness.to_dict())
        return generated_resource_to_api(resource, personalization)

    def get_resource_quality(self, user: User, resource_id: int) -> list[Any]:
        resource = self.repository.get_resource_for_user(user.id, resource_id)
        if resource is None:
            raise ResourceNotFoundError("资源不存在或无权访问。")
        return [quality_score_to_api(score) for score in self.repository.list_quality_scores(resource.id)]

    def _require_course(self, user: User, course_id: int) -> Course:
        course = self.repository.get_course_for_user(user.id, course_id)
        if course is None:
            raise ResourceNotFoundError("课程不存在或无权访问。")
        return course

    def _resolve_knowledge_point(self, course_id: int, knowledge_point_id: int | None) -> KnowledgePoint | None:
        if knowledge_point_id is None:
            return None
        point = self.repository.get_knowledge_point(course_id, knowledge_point_id)
        if point is None:
            raise ResourceNotFoundError("知识点不存在或不属于当前课程。")
        return point

    @staticmethod
    def _normalize_resource_types(resource_types: list[str]) -> list[str]:
        unique_types = list(dict.fromkeys(resource_types))
        if not unique_types:
            raise ResourceValidationError("至少选择一种资源类型。")
        invalid_types = [resource_type for resource_type in unique_types if resource_type not in RESOURCE_TYPES]
        if invalid_types:
            raise ResourceValidationError("不支持的资源类型。")
        if len(unique_types) > 7:
            raise ResourceValidationError("一次最多生成 7 类资源。")
        return unique_types

    def _quality_gate(
        self,
        *,
        resource_type: str,
        content: dict[str, Any],
        draft: ResourceDraft,
        contexts: list[ResourceContext],
        model_delta: bool,
        intent: dict[str, Any] | None = None,
        comparison_contents: list[dict[str, Any]] | None = None,
        source_content: dict[str, Any] | None = None,
        source_intent: dict[str, Any] | None = None,
        generation_action: GenerationAction = "new",
        semantic_similarity: float | None = None,
        semantic_status: str = "not_checked",
    ) -> tuple[dict[str, Any], list[str]]:
        valid_refs = {item.citation.chunk_id for item in contexts}
        risks = quality_risks(
            resource_type,
            content,
            topic=draft.source.topic,
            evidence_terms=[item.excerpt for item in contexts],
            valid_citation_refs=valid_refs,
        )
        safe_intent = intent if isinstance(intent, dict) else {}
        diversity, diversity_risks = evaluate_diversity(
            content=content,
            intent=safe_intent,
            comparison_contents=comparison_contents or [],
            source_content=source_content,
            source_intent=source_intent,
            generation_action=generation_action,
            semantic_similarity=semantic_similarity,
            semantic_status=semantic_status,
        )
        risks.extend(diversity_risks)
        code_verification = None
        if resource_type == "code" and not risks:
            artifact = content.get("artifact") if isinstance(content.get("artifact"), dict) else {}
            files = artifact.get("files") if isinstance(artifact, dict) else []
            entry_file = str(artifact.get("entry_file") or "") if isinstance(artifact, dict) else ""
            code = next(
                (str(item.get("content") or "") for item in files or [] if isinstance(item, dict) and item.get("path") == entry_file),
                "",
            )
            verification = self.code_verifier.verify(code, str(artifact.get("expected_output") or "")) if self.code_verifier else None
            if verification is None:
                risks.append("code_verifier_unavailable")
                code_verification = {"status": "failed", "code": "runtime_unavailable", "output_length": 0}
            else:
                code_verification = verification.safe_summary()
                if not verification.ok:
                    risks.append(f"code_{verification.code}")
        coverage = min(1.0, len(valid_refs) / max(1, len(contexts))) if contexts else 0.0
        base_quality = quality_summary(
            risks=risks,
            prompt_version=RESOURCE_PROMPT_VERSION,
            source_coverage=coverage,
            model_delta=model_delta,
            code_verification=code_verification,
        )
        dimensions = quality_dimensions(
            existing_risks=risks,
            intent=safe_intent,
            diversity=diversity,
            source_coverage=coverage,
        )
        result = {
            **content,
            "intent": safe_intent,
            "personalization_summary": personalization_summary(safe_intent),
            "diversity": diversity,
            "quality": {**base_quality, "dimensions": dimensions},
        }
        return result, list(dict.fromkeys(risks))

    def _semantic_similarity(
        self,
        user: User,
        content: dict[str, Any],
        comparisons: list[dict[str, Any]],
    ) -> tuple[float | None, str]:
        if not comparisons:
            return None, "not_needed"
        if not hasattr(self.model_settings_service, "resolve_embedding_runtime_config"):
            return None, "not_configured"
        candidate_text = artifact_text(content.get("artifact"))[:2000]
        comparison_texts: list[str] = []
        for item in comparisons[:5]:
            if not isinstance(item, dict):
                continue
            text = artifact_text(item.get("artifact"))[:2000]
            if text.strip() and text not in comparison_texts:
                comparison_texts.append(text)
        if not candidate_text.strip() or not comparison_texts:
            return None, "empty"
        try:
            batch = EmbeddingService(self.model_settings_service).embed_documents(
                user,
                [candidate_text, *comparison_texts],
            )
        except (AttributeError, ModelNotConfiguredError, ModelProviderError):
            return None, "provider_failed"
        if batch.status != "completed" or len(batch.vectors) < 2:
            return None, batch.status
        candidate_vector = batch.vectors[0]
        similarities = [self._cosine_similarity(candidate_vector, vector) for vector in batch.vectors[1:]]
        return (max(similarities) if similarities else None), "completed"

    @staticmethod
    def _cosine_similarity(left: list[float], right: list[float]) -> float:
        if not left or len(left) != len(right):
            return 0.0
        denominator = math.sqrt(sum(value * value for value in left)) * math.sqrt(sum(value * value for value in right))
        if denominator <= 0:
            return 0.0
        return max(-1.0, min(1.0, sum(a * b for a, b in zip(left, right, strict=True)) / denominator))

    @staticmethod
    def _parse_review_result(content: str, requested_types: set[str]) -> dict[str, dict[str, Any]]:
        return ResourceModelingService.parse_review_result(content, requested_types)

    def _create_quality_scores(
        self,
        resource_id: int,
        *,
        resource_type: str,
        markdown: str,
        review_status: str,
        generation_mode: str,
        context_count: int,
        profile_summary: dict[str, Any],
        difficulty: str,
        content_json: dict[str, Any] | None = None,
    ) -> list[ResourceQualityScore]:
        source_match = Decimal("0.86") if context_count >= 2 else Decimal("0.72") if context_count == 1 else Decimal("0.42")
        profile_fit = Decimal("0.80") if any(profile_summary.get(key) for key in ("learning_goal", "knowledge_foundation", "weak_points")) else Decimal("0.62")
        fact_confidence = Decimal("0.88") if generation_mode in {"model_generated", "model_enhanced"} and context_count else Decimal("0.78") if context_count else Decimal("0.48")
        difficulty_fit = Decimal("0.80") if difficulty in markdown else Decimal("0.72")
        is_complete = (
            not validate_resource_content(resource_type, content_json)
            if content_json is not None and content_json.get("schema_version") in {2, 3}
            else self._is_complete_resource(resource_type, markdown)
        )
        completeness = Decimal("0.90") if is_complete else Decimal("0.52")
        if review_status == "low_evidence":
            source_match = min(source_match, Decimal("0.50"))
            fact_confidence = min(fact_confidence, Decimal("0.50"))
        scores = {
            "source_match": source_match,
            "profile_fit": profile_fit,
            "fact_confidence": fact_confidence,
            "difficulty_fit": difficulty_fit,
            "completeness": completeness,
        }
        dimensions = (
            content_json.get("quality", {}).get("dimensions", {})
            if isinstance(content_json, dict) and isinstance(content_json.get("quality"), dict)
            else {}
        )
        for name in ("authenticity", "personalization", "diversity", "pedagogical_utility", "type_correctness"):
            dimension = dimensions.get(name) if isinstance(dimensions, dict) else None
            score = dimension.get("score") if isinstance(dimension, dict) else None
            scores[name] = Decimal(str(max(0.0, min(1.0, float(score))))) if isinstance(score, (int, float)) else Decimal("0.50")
        rationales = {
            "source_match": f"命中 {context_count} 条课程短摘录，资源围绕课程章节组织。",
            "profile_fit": "结合用户级画像目标、基础或薄弱点；画像不足时按课程默认学习目标生成。",
            "fact_confidence": "事实依据来自课程短摘录；模型增强只在通过安全检查后使用。",
            "difficulty_fit": f"按请求难度 {difficulty} 生成，并保留可执行复习动作。",
            "completeness": "检查该资源类型的必备结构是否齐全。",
            "authenticity": "检查课程事实、引用编号和资料依据是否一致。",
            "personalization": "检查教学策略是否使用当前可信画像和课程学习状态。",
            "diversity": "检查与同批资源、历史成果和来源版本是否保持有效差异。",
            "pedagogical_utility": "检查资源是否包含明确职责和可验证学习结果。",
            "type_correctness": "检查资源结构与该类型的交互和内容要求是否一致。",
        }
        return [
            ResourceQualityScore(
                resource_id=resource_id,
                score_name=name,
                score_value=scores[name],
                rationale=rationales[name],
            )
            for name in QUALITY_SCORE_NAMES
        ]

    _safe_title = staticmethod(safe_resource_title)
    _safe_excerpt = staticmethod(safe_resource_excerpt)
    _context_keywords = staticmethod(resource_context_keywords)

    @staticmethod
    def _confidence_score(review_status: str, generation_mode: str, contexts: list[ResourceContext]) -> Decimal:
        if review_status == "low_evidence":
            return Decimal("0.50")
        if generation_mode in {"model_generated", "model_enhanced"}:
            return Decimal("0.88")
        return Decimal("0.78") if len(contexts) >= 2 else Decimal("0.72")

    @staticmethod
    def _is_complete_resource(resource_type: str, markdown: str) -> bool:
        required_tokens = {
            "doc": ("概念解释", "关键步骤", "易错点"),
            "mindmap": ("```mermaid", "mindmap"),
            "quiz": ("单选题", "答案", "解析"),
            "code": ("```python", "运行说明", "改造任务"),
            "slide": ("第 1 页", "讲稿"),
            "animation": ("场景 1", "```mermaid"),
        }
        return all(token in markdown for token in required_tokens.get(resource_type, ()))

    @staticmethod
    def _contains_sensitive(value: str) -> bool:
        return ResourceModelingService.contains_sensitive(value)

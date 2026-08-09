from __future__ import annotations

import json
import re
from decimal import Decimal
from time import perf_counter
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from backend.app.api.errors import make_trace_id
from backend.app.core.config import get_settings
from backend.app.models import Course, GeneratedResource, KnowledgePoint, User
from backend.app.providers.model_tasks import ModelTaskProfile
from backend.app.schemas.resources import GenerateResourcesResult, quality_score_to_api
from backend.app.services.content_locale import china_first_content_policy
from backend.app.services.learner_context import context_service_from_repository
from backend.app.services.model_execution import execution_context_for_state, model_execution_scope
from backend.app.services.resource_artifacts import ArtifactBuildInput, validate_resource_content
from backend.app.services.resource_contracts import (
    ResourceDraft,
    ResourceGenerationError,
    ResourceGenerationState,
    ResourceNotFoundError,
    ResourceValidationError,
    resource_failure_message,
    resource_review_failure_message,
)
from backend.app.services.resource_intent import (
    ALLOWED_TEACHING_STRATEGIES,
    GenerationAction,
    build_artifact_intents,
    evaluate_diversity,
    personalization_summary,
    safe_history_summary,
)
from backend.app.services.resource_quality import RESOURCE_PROMPT_VERSION, meaningful_model_delta
from backend.app.services.structured_output import parse_json_object
from backend.app.services.video_resources import VideoCurationError

if TYPE_CHECKING:
    from backend.app.services.resources import ResourceGenerationService


class ResourceGenerationGraphRunner:
    workflow = "resource_generation"
    artifact_type = "generated_resource"
    worker_names = {
        "doc": "DocWorker",
        "mindmap": "MindmapWorker",
        "quiz": "QuizWorker",
        "code": "CodeWorker",
        "slide": "SlideWorker",
        "animation": "AnimationWorker",
        "video": "VideoCuratorWorker",
    }
    job_progress = {
        "profile": (8, "已读取学习画像"),
        "retrieve": (18, "已检索课程依据"),
        "diagnosis": (26, "已完成学习诊断"),
        "planner": (34, "已生成资源计划"),
        "aggregate": (72, "已汇总资源产物"),
        "review": (82, "已审核资源质量"),
        "repair": (90, "已修订资源产物"),
        "persist": (100, "资源已保存"),
    }

    def __init__(self, service: ResourceGenerationService) -> None:
        self.service = service
        self.graph = self._build_graph()

    def generate(
        self,
        *,
        user: User,
        course: Course,
        knowledge_point: KnowledgePoint | None,
        resource_types: list[str],
        learning_goal: str,
        difficulty: str,
        generation_action: GenerationAction = "new",
        source_resource: GeneratedResource | None = None,
        path_task_id: int | None = None,
        trace_id: str | None = None,
        job_context: Any | None = None,
    ) -> GenerateResourcesResult:
        trace_id = trace_id or make_trace_id()
        state: ResourceGenerationState = {
            "trace_id": trace_id,
            "workflow": self.workflow,
            "artifact_type": self.artifact_type,
            "user_id": user.id,
            "course_id": course.id,
            "knowledge_point_id": knowledge_point.id if knowledge_point is not None else None,
            "user": user,
            "course": course,
            "knowledge_point": knowledge_point,
            "resource_types": resource_types,
            "learning_goal": learning_goal,
            "difficulty": difficulty,
            "generation_action": generation_action,
            "source_resource": source_resource,
            "generation_batch_id": uuid4().hex,
            "path_task_id": path_task_id,
            "worker_results": [],
            "warnings": [],
            "errors": [],
            "job_context": job_context,
        }
        persist_started = perf_counter()
        try:
            with model_execution_scope(execution_context_for_state(state, workflow=self.workflow)):
                # Resource workers all use the same per-user model runtime. Dispatching more
                # graph tasks than the runtime permits makes workers race its short semaphore
                # wait and randomly drops otherwise valid resources. Run in bounded waves that
                # never exceed the configured per-user limit.
                max_concurrency = max(1, min(3, get_settings().model_max_concurrent_per_user))
                result = self.graph.invoke(state, config={"max_concurrency": max_concurrency})
            self._job_before(result, "persist")
            self.service.repository.commit()
            resources = list(result.get("resource_objects", []))
            for resource in resources:
                self.service.repository.refresh(resource)
            self._record(
                result,
                agent_name="persist",
                step_index=9,
                status="completed",
                input_summary="保存审核通过的结构化资源",
                output_summary=f"保存 {len(resources)} 个资源",
                metadata={"resource_count": len(resources)},
                started_at=persist_started,
            )
            self._job_after(result, "persist")
        except Exception as exc:
            self.service.repository.rollback()
            self._record(
                state,
                agent_name="persist",
                step_index=9,
                status="failed",
                input_summary="保存审核通过的结构化资源",
                output_summary="资源事务失败，未保存不完整产物。",
                metadata={"error_code": exc.__class__.__name__},
                started_at=persist_started,
            )
            self._job_after(state, "persist", status="failed", label="资源保存失败", progress_percent=95)
            raise

        return GenerateResourcesResult(
            agent_trace_id=trace_id,
            resources=[self.service._resource_to_api(int(result["user_id"]), resource) for resource in result.get("resource_objects", [])],
            quality_scores=result.get("quality_scores", {}),
            warnings=list(result.get("result_warnings", [])),
            failed_resource_types=list(result.get("failed_resource_types", [])),
        )

    def _build_graph(self):
        graph = StateGraph(ResourceGenerationState)
        graph.add_node("profile", self._profile_node)
        graph.add_node("retrieve", self._retrieve_node)
        graph.add_node("diagnosis", self._diagnosis_node)
        graph.add_node("planner", self._planner_node)
        graph.add_node("resource_worker", self._resource_worker_node)
        graph.add_node("aggregate", self._aggregate_node)
        graph.add_node("review", self._review_node)
        graph.add_node("repair", self._repair_node)
        graph.add_node("persist", self._persist_node)
        graph.add_edge(START, "profile")
        graph.add_edge("profile", "retrieve")
        graph.add_edge("retrieve", "diagnosis")
        graph.add_edge("diagnosis", "planner")
        graph.add_conditional_edges("planner", self._dispatch_workers)
        graph.add_edge("resource_worker", "aggregate")
        graph.add_edge("aggregate", "review")
        graph.add_conditional_edges(
            "review",
            self._review_route,
            {"repair": "repair", "persist": "persist"},
        )
        graph.add_edge("repair", "persist")
        graph.add_edge("persist", END)
        return graph.compile()

    def _profile_node(self, state: ResourceGenerationState) -> dict[str, Any]:
        started = perf_counter()
        self._job_before(state, "profile")
        context_service = context_service_from_repository(self.service.repository)
        if context_service is not None:
            learner_context = context_service.course_context(int(state["user_id"]), int(state["course_id"]))
            profile_summary = learner_context.prompt_summary()
            context_metadata = learner_context.trace_metadata()
        else:
            profile = self.service.repository.get_profile(int(state["user_id"]))
            profile_summary = self.service._profile_summary(profile)
            learner_context = None
            context_metadata = {"profile_context_used": bool(profile_summary)}
        self._record(
            state,
            agent_name="profile",
            step_index=1,
            input_summary="读取用户级画像摘要",
            output_summary="画像已合入资源生成上下文",
            metadata=context_metadata,
            started_at=started,
        )
        self._job_after(state, "profile")
        return {"profile_summary": profile_summary, "learner_context": learner_context}

    def _retrieve_node(self, state: ResourceGenerationState) -> dict[str, Any]:
        started = perf_counter()
        self._job_before(state, "retrieve")
        course = state["course"]
        knowledge_point = state.get("knowledge_point")
        context_points = self.service.repository.list_knowledge_points(course.id)
        chunks = self.service.repository.list_course_chunks(
            course.id,
            knowledge_point.id if knowledge_point is not None else None,
        )
        contexts = self.service._safe_resource_contexts(chunks, knowledge_point, context_points)
        citations = [context.citation for context in contexts]
        if not citations and knowledge_point is None and not context_points:
            raise ResourceGenerationError("当前课程没有足够依据生成资源。")
        self._record(
            state,
            agent_name="retrieve",
            step_index=2,
            input_summary="检索课程引用摘要",
            output_summary=f"命中 {len(citations)} 条安全引用摘要",
            metadata={"citation_count": len(citations), "source_count": len(citations)},
            started_at=started,
        )
        self._job_after(state, "retrieve")
        return {
            "context_points": context_points,
            "contexts": contexts,
            "resource_citations": citations,
            "citations": [citation.to_json() for citation in citations],
        }

    def _diagnosis_node(self, state: ResourceGenerationState) -> dict[str, Any]:
        started = perf_counter()
        self._job_before(state, "diagnosis")
        resource_types = list(state.get("resource_types", []))
        knowledge_point = state.get("knowledge_point")
        diagnosis = {
            "resource_count": len(resource_types),
            "knowledge_point_id": knowledge_point.id if knowledge_point is not None else None,
            "difficulty": state.get("difficulty"),
            "generation_action": state.get("generation_action", "new"),
            "mastery_average": dict(state.get("profile_summary", {})).get("mastery_average"),
            "active_weaknesses": list(dict(state.get("profile_summary", {})).get("weak_points") or [])[:3],
        }
        self._record(
            state,
            agent_name="diagnosis",
            step_index=3,
            input_summary="分析资源类型、难度和课程上下文",
            output_summary=f"准备生成 {len(resource_types)} 类资源",
            metadata={
                "knowledge_point_id": diagnosis["knowledge_point_id"],
                "resource_count": len(resource_types),
                "worker_count": len(resource_types),
                "generation_action": diagnosis["generation_action"],
            },
            started_at=started,
        )
        self._job_after(state, "diagnosis")
        return {"diagnosis": diagnosis}

    def _planner_node(self, state: ResourceGenerationState) -> dict[str, Any]:
        started = perf_counter()
        self._job_before(state, "planner")
        profile_summary = dict(state.get("profile_summary", {}))
        learning_goal = str(state.get("learning_goal") or profile_summary.get("learning_goal") or "掌握当前知识点")
        knowledge_point = state.get("knowledge_point")
        context_points = list(state.get("context_points", []))
        topic = knowledge_point.title if knowledge_point is not None else (
            context_points[0].title if context_points else state["course"].title
        )
        requested_topic = self._requested_dialogue_topic(learning_goal)
        if requested_topic:
            course_topics = " ".join([state["course"].title, *(point.title for point in context_points)])
            if self._normalized_topic(requested_topic) not in self._normalized_topic(course_topics):
                raise ResourceGenerationError(f"所选课程没有“{requested_topic}”的可用资料，请选择对应课程后再生成。")
            topic = requested_topic
        source_resource = state.get("source_resource")
        source_content = source_resource.content_json if source_resource is not None and isinstance(source_resource.content_json, dict) else {}
        source_intent = source_content.get("intent") if isinstance(source_content.get("intent"), dict) else None
        historical_resources = [
            resource
            for resource in self.service.repository.list_resources(int(state["user_id"]), course_id=int(state["course_id"]))
            if resource.status == "completed" and (source_resource is None or resource.id != source_resource.id)
        ]
        intents = build_artifact_intents(
            resource_types=list(state.get("resource_types", [])),
            topic=topic,
            learning_goal=learning_goal,
            difficulty=str(state.get("difficulty") or "medium"),
            profile_summary=profile_summary,
            evidence_refs=[citation.chunk_id for citation in state.get("resource_citations", [])],
            generation_action=state.get("generation_action", "new"),
            source_intent=source_intent,
        )
        intents = self._model_refine_artifact_intents(state, intents) or intents
        plan = {
            "learning_goal": learning_goal,
            "difficulty": str(state.get("difficulty") or "medium"),
            "weak_points": list(profile_summary.get("weak_points") or [])[:3],
            "resource_types": list(state.get("resource_types", [])),
            "artifact_intents": intents,
            "generation_action": state.get("generation_action", "new"),
            "history": safe_history_summary(historical_resources),
        }
        self._record(
            state,
            agent_name="planner",
            step_index=4,
            input_summary="规划各资源 Worker 的共同目标",
            output_summary=f"已为 {len(plan['resource_types'])} 个 Worker 制定互补教学策略",
            metadata={
                "worker_count": len(plan["resource_types"]),
                "generation_action": plan["generation_action"],
                "history_count": len(historical_resources),
                "personalized_intent_count": sum(
                    1 for intent in intents.values() if intent.get("personalization_status") == "personalized"
                ),
            },
            started_at=started,
        )
        self._job_after(state, "planner")
        return {
            "resource_plan": plan,
            "artifact_intents": intents,
            "historical_resources": historical_resources,
        }

    @staticmethod
    def _requested_dialogue_topic(learning_goal: str) -> str | None:
        match = re.search(r"(?:生成|制作|创建|出)\s*(.+?)\s*(?:的)?\s*(?:资源|讲义|笔记|思维导图|脑图|题目|练习|测验|代码|课件|PPT|动画|视频)", learning_goal, re.IGNORECASE)
        if match is None:
            return None
        topic = re.sub(r"\s+", "", match.group(1)).strip("，。！？!?：:")
        return topic[:80] if topic else None

    @staticmethod
    def _normalized_topic(value: str) -> str:
        return re.sub(r"[\s\W_]+", "", value, flags=re.UNICODE).casefold()

    def _model_refine_artifact_intents(
        self,
        state: ResourceGenerationState,
        intents: dict[str, dict[str, Any]],
    ) -> dict[str, dict[str, Any]] | None:
        try:
            raw = self.service._call_model_for_resource(
                state["user"],
                [
                    {
                        "role": "system",
                        "content": (
                            "你是 EduNova 资源教学策略规划器。只输出 JSON，不输出思维链。"
                            "只能调整给定资源的 teaching_strategy、cognitive_level、example_direction、"
                            "interaction_structure 和 learning_need，不得新增资源类型或引用。"
                            + china_first_content_policy.prompt_instruction()
                        ),
                    },
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "profile": state.get("profile_summary", {}),
                                "diagnosis": state.get("diagnosis", {}),
                                "candidate_intents": intents,
                                "allowed_strategies": sorted(ALLOWED_TEACHING_STRATEGIES),
                                "output": {"intents": intents},
                            },
                            ensure_ascii=False,
                        )[:12000],
                    },
                ],
                profile=ModelTaskProfile(
                    task_type="resource_intent_planning",
                    reasoning="disabled",
                    output_mode="json_object",
                    creativity="balanced",
                    timeout_seconds=20.0,
                    max_attempts=1,
                ),
            )
        except Exception:
            return None
        payload = parse_json_object(raw)
        proposed = payload.get("intents") if isinstance(payload, dict) else None
        if not isinstance(proposed, dict) or set(proposed) != set(intents):
            return None
        refined: dict[str, dict[str, Any]] = {}
        for resource_type, baseline in intents.items():
            candidate = proposed.get(resource_type)
            if not isinstance(candidate, dict):
                return None
            strategy = str(candidate.get("teaching_strategy") or baseline["teaching_strategy"])
            if strategy not in ALLOWED_TEACHING_STRATEGIES:
                return None
            cognitive_level = str(candidate.get("cognitive_level") or baseline["cognitive_level"])
            if cognitive_level not in {"understand", "apply", "analyze", "create"}:
                return None
            refined[resource_type] = {
                **baseline,
                "teaching_strategy": strategy,
                "cognitive_level": cognitive_level,
                "example_direction": str(candidate.get("example_direction") or baseline["example_direction"])[:160],
                "interaction_structure": str(candidate.get("interaction_structure") or baseline["interaction_structure"])[:160],
                "learning_need": str(candidate.get("learning_need") or baseline["learning_need"])[:240],
                "personalization_status": "model_personalized",
            }
        return refined

    @staticmethod
    def _dispatch_workers(state: ResourceGenerationState) -> list[Send]:
        return [
            Send("resource_worker", {**state, "worker_resource_type": resource_type})
            for resource_type in state.get("resource_types", [])
        ]

    def _semantic_diversity(
        self,
        state: ResourceGenerationState,
        *,
        resource_type: str,
        content: dict[str, Any],
        source_content: dict[str, Any] | None,
        comparison_contents: list[dict[str, Any]],
    ) -> tuple[float | None, str]:
        comparisons = [
            item
            for item in [source_content, *comparison_contents]
            if isinstance(item, dict)
        ]
        if not comparisons:
            return None, "not_needed"
        with model_execution_scope(
            execution_context_for_state(
                state,
                workflow=self.workflow,
                node_name=f"semantic_diversity:{resource_type}",
            )
        ):
            return self.service._semantic_similarity(state["user"], content, comparisons)

    def _resource_worker_node(self, state: ResourceGenerationState) -> dict[str, Any]:
        started = perf_counter()
        resource_type = str(state["worker_resource_type"])
        worker_name = self.worker_names[resource_type]
        self._job_before(state, "resource_worker")
        try:
            course = state["course"]
            knowledge_point = state.get("knowledge_point")
            contexts = list(state.get("contexts", []))
            profile_summary = dict(state.get("profile_summary", {}))
            artifact_intent = dict(state.get("artifact_intents", {}).get(resource_type, {}))
            if resource_type == "video":
                topic = knowledge_point.title if knowledge_point is not None else course.title
                curated = self.service.video_curator.curate(topic=topic, profile_summary=profile_summary)
                learning_goal = str(state.get("learning_goal") or "").strip()
                fit_reason = f"作为“{topic}”的外部补充讲解"
                if learning_goal:
                    fit_reason += f"，用于支持学习目标：{learning_goal[:120]}"
                match_level = curated.match_level
                if match_level == "related":
                    fit_reason = f"与“{topic}”相关的外部补充讲解，不替代该知识点的精确讲解"
                artifact = curated.artifact(topic=topic, fit_reason=fit_reason)
                markdown = f"# {curated.title}\n\n外部教学视频（{curated.platform}）：[{curated.title}]({curated.watch_url})\n\n{fit_reason}"
                source = ArtifactBuildInput(
                    resource_type="video", topic=topic, course_title=course.title,
                    difficulty=str(state.get("difficulty") or "medium"), citation_lines=[], excerpt_lines=[],
                    weak_points="", profile_goal="", foundation="", learning_preference="", citation_refs=[],
                )
                content_json = {
                    "schema_version": 3, "format": "rich", "topic": topic, "course_title": course.title,
                    "summary": curated.snippet or fit_reason, "learning_objectives": ["观看后说明讲解与当前知识点的关联"],
                    "markdown": markdown, "artifact": artifact, "citation_summaries": [],
                    "intent": artifact_intent, "personalization_summary": personalization_summary(artifact_intent),
                    "diversity": {"status": "passed", "score": 1.0, "risk_flags": []},
                    "quality": {"status": "passed", "risk_flags": [], "prompt_version": RESOURCE_PROMPT_VERSION,
                                "source_coverage": 0.0, "model_delta": False, "dimensions": {}},
                    "metadata": {"generation_mode": "curated_external", "external_supplement": True},
                    "external_citations": [curated.citation()],
                }
                draft = ResourceDraft(title=curated.title, markdown=markdown, content_json=content_json, source=source)
                return {"worker_results": [{
                    "status": "completed", "resource_type": "video", "draft": draft, "markdown": markdown,
                    "content_json": content_json, "generation_mode": "curated_external", "model_failed": False,
                    "warnings": (["未匹配到精确视频，已提供相关补充视频。"] if match_level == "related" else []),
                    "comparison_contents": [], "source_content": None, "source_intent": None,
                    "artifact_intent": artifact_intent,
                }]}
            source_resource = state.get("source_resource")
            source_content = (
                source_resource.content_json
                if source_resource is not None and isinstance(source_resource.content_json, dict)
                else None
            )
            source_intent = (
                source_content.get("intent")
                if isinstance(source_content, dict) and isinstance(source_content.get("intent"), dict)
                else None
            )
            historical_resources = [
                resource
                for resource in state.get("historical_resources", [])
                if resource.resource_type == resource_type
                and resource.knowledge_point_id == (knowledge_point.id if knowledge_point is not None else None)
            ][:5]
            history_summaries = safe_history_summary(historical_resources)
            comparison_contents = [
                resource.content_json
                for resource in historical_resources
                if isinstance(resource.content_json, dict)
            ]
            draft = self.service._build_draft(
                resource_type=resource_type,
                course=course,
                knowledge_point=knowledge_point,
                context_points=list(state.get("context_points", [])),
                contexts=contexts,
                profile_summary=profile_summary,
                difficulty=str(state.get("difficulty") or "medium"),
                intent=artifact_intent,
            )
            with model_execution_scope(
                execution_context_for_state(state, workflow=self.workflow, node_name=f"{worker_name}:{resource_type}")
            ):
                model_content, model_failed = self.service._enhance_resource_with_model(
                    user=state["user"],
                    resource_type=resource_type,
                    draft=draft,
                    contexts=contexts,
                    profile_summary=profile_summary,
                    learning_goal=str(state.get("learning_goal") or ""),
                    difficulty=str(state.get("difficulty") or "medium"),
                    artifact_intent=artifact_intent,
                    history_summaries=history_summaries,
                )
            warnings: list[str] = []
            model_delta = bool(model_content and meaningful_model_delta(model_content, draft.content_json))
            if model_content is None:
                raise ResourceGenerationError(f"{resource_type} 模型生成失败，未保存规则模板。")
            if not model_delta:
                raise ResourceGenerationError(f"{resource_type} 模型产物与结构底稿无有效差异，未保存。")
            candidate_content = model_content
            semantic_similarity, semantic_status = self._semantic_diversity(
                state,
                resource_type=resource_type,
                content=candidate_content,
                source_content=source_content,
                comparison_contents=comparison_contents,
            )
            content_json, risks = self.service._quality_gate(
                resource_type=resource_type,
                content=model_content,
                draft=draft,
                contexts=contexts,
                model_delta=True,
                intent=artifact_intent,
                comparison_contents=comparison_contents,
                source_content=source_content,
                source_intent=source_intent,
                generation_action=state.get("generation_action", "new"),
                semantic_similarity=semantic_similarity,
                semantic_status=semantic_status,
            )
            generation_mode = "model_generated"

            if risks:
                warnings.append(f"{resource_type} 候选产物未通过质量门禁，已进入单次内容修订。")

            if model_failed:
                warnings.append(f"{resource_type} 模型调用失败。")
            markdown = str(content_json.get("markdown") or "")
            result = {
                "status": "completed",
                "resource_type": resource_type,
                "draft": draft,
                "markdown": markdown,
                "content_json": content_json,
                "generation_mode": generation_mode,
                "model_failed": model_failed,
                "warnings": warnings,
                "comparison_contents": comparison_contents,
                "source_content": source_content,
                "source_intent": source_intent,
                "artifact_intent": artifact_intent,
            }
            self._record(
                state,
                agent_name=worker_name,
                step_index=5,
                status="warning" if warnings else "completed",
                input_summary=f"生成 {resource_type} 结构化资源",
                output_summary=f"{worker_name} 已生成可审核产物",
                metadata={
                    "resource_type": resource_type,
                    "generation_mode": generation_mode,
                    "model_used": model_content is not None,
                    "prompt_version": RESOURCE_PROMPT_VERSION,
                    "generation_action": state.get("generation_action", "new"),
                    "personalization_status": artifact_intent.get("personalization_status", "context_limited"),
                    "history_count": len(history_summaries),
                },
                started_at=started,
            )
            self._job_after(
                state,
                worker_name,
                status="warning" if warnings else "completed",
                label=f"{worker_name} 已完成",
                progress_percent=60,
                resource_type=resource_type,
            )
            return {"worker_results": [result]}
        except Exception as exc:
            if exc.__class__.__name__ == "AiJobCancelled":
                raise
            self._record(
                state,
                agent_name=worker_name,
                step_index=5,
                status="failed",
                input_summary=f"生成 {resource_type} 结构化资源",
                output_summary="该类型资源生成失败，其他 Worker 继续执行。",
                metadata={
                    "resource_type": resource_type,
                    "error_code": exc.__class__.__name__,
                    **(
                        {"video_curation": dict(exc.diagnostics)}
                        if isinstance(exc, VideoCurationError)
                        else {}
                    ),
                },
                started_at=started,
            )
            self._job_after(
                state,
                worker_name,
                status="failed",
                label=f"{worker_name} 生成失败",
                progress_percent=60,
                resource_type=resource_type,
            )
            return {
                "worker_results": [
                    {
                        "status": "failed",
                        "resource_type": resource_type,
                        "error_code": exc.__class__.__name__,
                        "error_message": resource_failure_message(resource_type, exc),
                    }
                ]
            }

    def _aggregate_node(self, state: ResourceGenerationState) -> dict[str, Any]:
        started = perf_counter()
        self._job_before(state, "aggregate")
        order = {resource_type: index for index, resource_type in enumerate(state.get("resource_types", []))}
        results = sorted(list(state.get("worker_results", [])), key=lambda item: order.get(item["resource_type"], 99))
        completed = [item for item in results if item.get("status") == "completed"]
        for payload in completed:
            other_contents = [
                item["content_json"]
                for item in completed
                if item is not payload and isinstance(item.get("content_json"), dict)
            ]
            batch_diversity, batch_risks = evaluate_diversity(
                content=payload["content_json"],
                intent=dict(payload.get("artifact_intent") or {}),
                comparison_contents=other_contents,
                source_content=None,
                source_intent=None,
                generation_action="new",
            )
            quality = dict(payload["content_json"].get("quality") or {})
            existing_diversity = dict(payload["content_json"].get("diversity") or {})
            combined_score = min(
                float(existing_diversity.get("score") or 1.0),
                float(batch_diversity.get("score") or 1.0),
            )
            combined_risks = list(dict.fromkeys([
                *quality.get("risk_flags", []),
                *(batch_risks if payload.get("generation_mode") == "model_generated" else []),
            ]))
            dimensions = dict(quality.get("dimensions") or {})
            dimensions["diversity"] = {
                "status": (
                    "passed"
                    if combined_score >= 0.6 and (not batch_risks or payload.get("generation_mode") != "model_generated")
                    else "failed"
                ),
                "score": round(combined_score, 3),
                "rationale": "检查与同批资源、历史成果和来源版本是否保持有效差异。",
            }
            payload["content_json"] = {
                **payload["content_json"],
                "diversity": {
                    **existing_diversity,
                    "score": round(combined_score, 3),
                    "batch_duplicate_sentence_ratio": batch_diversity.get("duplicate_sentence_ratio", 0),
                    "batch_comparison_count": len(other_contents),
                    "risk_flags": list(dict.fromkeys([
                        *existing_diversity.get("risk_flags", []),
                        *(batch_risks if payload.get("generation_mode") == "model_generated" else []),
                    ])),
                },
                "quality": {
                    **quality,
                    "status": "failed" if combined_risks else quality.get("status", "passed"),
                    "risk_flags": combined_risks,
                    "dimensions": dimensions,
                },
            }
            payload["markdown"] = str(payload["content_json"].get("markdown") or payload.get("markdown") or "")
        failed_types = [str(item["resource_type"]) for item in results if item.get("status") == "failed"]
        if not completed:
            self._record(
                state,
                agent_name="aggregate",
                step_index=6,
                status="failed",
                input_summary="汇总并行 Worker 产物",
                output_summary="所有严格资源均未通过生成或质量门禁。",
                metadata={
                    "worker_count": len(results),
                    "failed_resource_types": failed_types,
                    "failure_codes": sorted({str(item.get("error_code") or "generation_failed") for item in results}),
                },
                started_at=started,
            )
            self._job_after(state, "aggregate", status="failed", label="所有资源均未通过质量门禁")
            raise ResourceGenerationError("所有资源 Worker 均生成失败，请稍后重试。")
        warnings = [
            *[
                f"{item['resource_type']} 资源生成失败：{item.get('error_message') or '未通过质量门禁'}"
                for item in results
                if item.get("status") == "failed"
            ],
            *[
                str(warning)
                for item in completed
                for warning in item.get("warnings", [])
                if str(warning).strip()
            ],
        ]
        self._record(
            state,
            agent_name="aggregate",
            step_index=6,
            status="warning" if failed_types else "completed",
            input_summary="汇总并行 Worker 产物",
            output_summary=f"汇总 {len(completed)} 个可审核资源",
            metadata={
                "resource_count": len(completed),
                "worker_count": len(results),
                "failed_resource_types": failed_types,
            },
            started_at=started,
        )
        self._job_after(state, "aggregate", status="warning" if failed_types else "completed")
        return {
            "worker_results": [],
            "resource_payloads": completed,
            "failed_resource_types": failed_types,
            "result_warnings": list(dict.fromkeys(warnings)),
        }

    def _review_node(self, state: ResourceGenerationState) -> dict[str, Any]:
        started = perf_counter()
        self._job_before(state, "review")
        contexts = list(state.get("contexts", []))
        payloads = list(state.get("resource_payloads", []))
        with model_execution_scope(execution_context_for_state(state, workflow=self.workflow, node_name="review")):
            model_reviews, review_model_failed = self.service._review_resources_with_model(
                user=state["user"],
                payloads=[payload for payload in payloads if payload.get("resource_type") != "video"],
                contexts=contexts,
                learning_goal=str(state.get("learning_goal") or ""),
                history_summaries=list(dict(state.get("resource_plan", {})).get("history") or []),
            )
        reviewed: list[dict[str, Any]] = []
        generation_warnings = 0
        needs_repair = False
        all_risk_flags: list[str] = []
        for payload in payloads:
            resource_type = str(payload["resource_type"])
            quality = payload["content_json"].get("quality")
            deterministic_risks = validate_resource_content(resource_type, payload["content_json"])
            if isinstance(quality, dict):
                deterministic_risks = list(dict.fromkeys([*deterministic_risks, *quality.get("risk_flags", [])]))
            model_review = model_reviews.get(resource_type)
            model_risks = list(model_review.get("risk_flags", [])) if model_review else []
            risk_flags = list(dict.fromkeys([*deterministic_risks, *model_risks]))
            model_rejected = model_review is not None and model_review.get("status") == "failed"
            review_status = "failed" if risk_flags or model_rejected else "passed" if resource_type == "video" else "low_evidence" if not contexts else "passed"
            review_mode = "model_and_rules" if model_review is not None else "rules_only"
            if review_status == "failed":
                needs_repair = True
            if review_status == "low_evidence":
                generation_warnings += 1
            all_risk_flags.extend(risk_flags)
            confidence = (
                Decimal(str(model_review["confidence"]))
                if model_review is not None
                else self.service._confidence_score(review_status, payload["generation_mode"], contexts)
            )
            reviewed.append(
                {
                    **payload,
                    "review_status": review_status,
                    "review_mode": review_mode,
                    "confidence": confidence,
                    "risk_flags": risk_flags,
                    "repair_count": 0,
                }
            )

        review_result = "failed" if needs_repair else "low_evidence" if generation_warnings else "passed"
        review_metadata = {
            "confidence": 0.55 if needs_repair or generation_warnings else 0.86,
            "review_status": review_result,
            "review_result": review_result,
            "risk_flags": list(dict.fromkeys(all_risk_flags)),
            "safety_summary": "已完成结构规则、引用、隐私和模型复核。",
            "resource_count": len(reviewed),
            "warning_count": generation_warnings,
            "review_mode": "rules_only" if review_model_failed or not model_reviews else "model_and_rules",
            "repair_count": 0,
        }
        self._record(
            state,
            agent_name="ReviewAgent",
            step_index=7,
            input_summary="审核资源依据和画像贴合度",
            output_summary=f"审核结果：{review_result}",
            status="warning" if generation_warnings or needs_repair or review_model_failed else "completed",
            metadata=review_metadata,
            started_at=started,
        )
        warnings = list(state.get("result_warnings", []))
        if review_model_failed:
            warnings.append("模型审核暂不可用，资源已通过本地结构与安全规则审核。")
        self._job_after(
            state,
            "review",
            status="warning" if generation_warnings or needs_repair or review_model_failed else "completed",
        )
        return {
            "reviewed_results": reviewed,
            "review_result": review_metadata,
            "generation_warnings": generation_warnings,
            "needs_repair": needs_repair,
            "result_warnings": list(dict.fromkeys(warnings)),
        }

    @staticmethod
    def _review_route(state: ResourceGenerationState) -> str:
        return "repair" if state.get("needs_repair") else "persist"

    def _repair_node(self, state: ResourceGenerationState) -> dict[str, Any]:
        started = perf_counter()
        self._job_before(state, "repair")
        contexts = list(state.get("contexts", []))
        repaired_results: list[dict[str, Any]] = []
        failed_types = list(state.get("failed_resource_types", []))
        warnings = list(state.get("result_warnings", []))
        repaired_count = 0
        for payload in state.get("reviewed_results", []):
            if payload.get("review_status") != "failed":
                repaired_results.append(payload)
                continue
            resource_type = str(payload["resource_type"])
            with model_execution_scope(execution_context_for_state(state, workflow=self.workflow, node_name="repair")):
                repaired_content = self.service._repair_resource_with_model(
                    user=state["user"],
                    payload={**payload, "generation_action": state.get("generation_action", "new")},
                )
            draft: ResourceDraft = payload["draft"]
            if repaired_content is not None:
                repair_semantic_similarity, repair_semantic_status = self._semantic_diversity(
                    state,
                    resource_type=resource_type,
                    content=repaired_content,
                    source_content=payload.get("source_content"),
                    comparison_contents=list(payload.get("comparison_contents") or []),
                )
                repaired_content, repaired_risks = self.service._quality_gate(
                    resource_type=resource_type,
                    content=repaired_content,
                    draft=draft,
                    contexts=contexts,
                    model_delta=meaningful_model_delta(repaired_content, draft.content_json),
                    intent=dict(payload.get("artifact_intent") or payload["content_json"].get("intent") or {}),
                    comparison_contents=list(payload.get("comparison_contents") or []),
                    source_content=payload.get("source_content"),
                    source_intent=payload.get("source_intent"),
                    generation_action=state.get("generation_action", "new"),
                    semantic_similarity=repair_semantic_similarity,
                    semantic_status=repair_semantic_status,
                )
            else:
                repaired_risks = ["repair_failed"]
            if repaired_content is not None and not repaired_risks:
                repaired_results.append(
                    {
                        **payload,
                        "markdown": str(repaired_content.get("markdown") or ""),
                        "content_json": repaired_content,
                        "generation_mode": "model_generated",
                        "review_status": "low_evidence" if not contexts else "passed",
                        "review_mode": "model_and_rules",
                        "risk_flags": [],
                        "repair_count": 1,
                    }
                )
                repaired_count += 1
                continue

            failed_types.append(resource_type)
            reason = ",".join(str(flag) for flag in payload.get("risk_flags", [])[:3]) or "repair_failed"
            warnings.append(resource_review_failure_message(resource_type, reason))

        self._record(
            state,
            agent_name="RepairAgent",
            step_index=8,
            status="warning" if failed_types else "completed",
            input_summary="修订未通过审核的资源",
            output_summary=f"完成 {repaired_count} 个资源的单次安全修订",
            metadata={"repair_count": repaired_count, "failed_resource_types": list(dict.fromkeys(failed_types))},
            started_at=started,
        )
        safe_results = [item for item in repaired_results if item.get("review_status") in {"passed", "low_evidence"}]
        if not safe_results:
            raise ResourceGenerationError("所有资源均未通过安全审核，请调整资料后重试。")
        self._job_after(state, "repair", status="warning" if failed_types else "completed")
        return {
            "reviewed_results": safe_results,
            "failed_resource_types": list(dict.fromkeys(failed_types)),
            "result_warnings": list(dict.fromkeys(warnings)),
            "needs_repair": False,
        }

    def _persist_node(self, state: ResourceGenerationState) -> dict[str, Any]:
        self._job_before(state, "persist")
        course = state["course"]
        knowledge_point = state.get("knowledge_point")
        contexts = list(state.get("contexts", []))
        citations = list(state.get("resource_citations", []))
        profile_summary = dict(state.get("profile_summary", {}))
        difficulty = str(state.get("difficulty") or "medium")
        trace_id = str(state["trace_id"])
        resources: list[GeneratedResource] = []
        quality_scores: dict[str, list[Any]] = {}
        generation_action: GenerationAction = state.get("generation_action", "new")
        source_resource = state.get("source_resource")
        source_locked: GeneratedResource | None = None
        version_family_id: str | None = None
        next_version_number: int | None = None
        if generation_action in {"alternative", "refine"}:
            if source_resource is None:
                raise ResourceValidationError("重新生成缺少来源资源。")
            if source_resource.version_family_id:
                version_family_id = source_resource.version_family_id
                self.service.repository.lock_version_family(version_family_id)
            source_locked = self.service.repository.get_resource_for_user(
                int(state["user_id"]),
                int(source_resource.id),
                for_update=True,
            )
            if source_locked is None or source_locked.course_id != course.id:
                raise ResourceNotFoundError("来源资源不存在或无权访问。")
            version_family_id = source_locked.version_family_id or version_family_id or str(uuid4())
            if source_locked.version_family_id is None:
                source_locked.version_family_id = version_family_id
                source_locked.version_number = 1
                source_locked.generation_action = "new"
            elif source_resource.version_family_id is None:
                self.service.repository.lock_version_family(version_family_id)
            next_version_number = self.service.repository.max_version_number(version_family_id) + 1

        payloads = list(state.get("reviewed_results", []))
        if not payloads:
            payloads = list(state.get("resource_payloads", []))
        for payload in payloads:
            if payload.get("review_status") not in {"passed", "low_evidence"}:
                continue
            draft: ResourceDraft = payload["draft"]
            content_json = {
                **payload["content_json"],
                "markdown": payload["markdown"],
                "metadata": {
                    **dict(payload["content_json"].get("metadata") or {}),
                    "agent_trace_id": trace_id,
                    "generation_mode": payload["generation_mode"],
                    "review_mode": payload.get("review_mode", "rules_only"),
                    "repair_count": int(payload.get("repair_count", 0)),
                    "difficulty": difficulty,
                    "has_learning_goal": bool(str(state.get("learning_goal") or "").strip()),
                    "source_excerpt_count": len(contexts),
                    "model_enhancement_failed": bool(payload.get("model_failed")),
                    "prompt_version": RESOURCE_PROMPT_VERSION,
                    "profile_applied_version": (
                        state["learner_context"].global_context.profile_applied_version
                        if state.get("learner_context") is not None
                        else 0
                    ),
                    "course_context_hash": (
                        state["learner_context"].context_hash
                        if state.get("learner_context") is not None
                        else "legacy"
                    ),
                    "generation_action": generation_action,
                    "generation_batch_id": str(state.get("generation_batch_id") or ""),
                    "source_resource_id": source_locked.id if source_locked is not None else None,
                    **china_first_content_policy.metadata(),
                },
            }
            resource_family_id = version_family_id or str(uuid4())
            resource_version_number = next_version_number or 1
            resource = self.service.repository.add_resource(
                GeneratedResource(
                    user_id=int(state["user_id"]),
                    course_id=course.id,
                    knowledge_point_id=knowledge_point.id if knowledge_point is not None else None,
                    resource_type=payload["resource_type"],
                    title=draft.title,
                    agent_trace_id=trace_id,
                    content_json=content_json,
                    citation_json=(
                        list(content_json.get("external_citations") or [])
                        if payload["resource_type"] == "video"
                        else [citation.to_json() for citation in citations]
                    ),
                    status="completed",
                    review_status=payload["review_status"],
                    confidence_score=payload["confidence"],
                    version_family_id=resource_family_id,
                    revision_of_resource_id=source_locked.id if source_locked is not None else None,
                    version_number=resource_version_number,
                    generation_action=generation_action,
                )
            )
            resources.append(resource)
            scores = self.service._create_quality_scores(
                resource.id,
                resource_type=payload["resource_type"],
                markdown=payload["markdown"],
                review_status=payload["review_status"],
                generation_mode=payload["generation_mode"],
                context_count=len(contexts),
                profile_summary=profile_summary,
                difficulty=difficulty,
                content_json=content_json,
            )
            quality_scores[str(resource.id)] = [
                quality_score_to_api(self.service.repository.add_quality_score(score)) for score in scores
            ]

        path_task_id = state.get("path_task_id")
        if path_task_id is not None and resources:
            task = self.service.repository.get_learning_task_for_user(int(state["user_id"]), int(path_task_id))
            if task is None or task.course_id != course.id:
                raise ResourceNotFoundError("学习路径任务不存在或无权访问。")
            resource_ids = list(dict.fromkeys([*list(task.recommended_resource_ids or []), *[item.id for item in resources]]))
            task.recommended_resource_ids = resource_ids
            bundle = dict(task.learning_bundle_json or {})
            # JSON columns do not notice mutations made to nested dictionaries in
            # place.  Build fresh item objects so SQLAlchemy can compare the new
            # value with the persisted bundle and actually write the association.
            bundle_items = [dict(item) if isinstance(item, dict) else item for item in list(bundle.get("items") or [])]
            by_type = {item.resource_type: item for item in resources}
            for item in bundle_items:
                generated = by_type.get(str(item.get("resource_type") or "")) if isinstance(item, dict) else None
                if generated is not None:
                    item["resource_id"] = generated.id
                    item["status"] = "ready"
            task.learning_bundle_json = {**bundle, "items": bundle_items}

        return {"resource_objects": resources, "quality_scores": quality_scores}

    @staticmethod
    def _job_before(state: ResourceGenerationState, name: str) -> None:
        context = state.get("job_context")
        if context is not None:
            context.before_node(name)

    def _job_after(
        self,
        state: ResourceGenerationState,
        name: str,
        *,
        status: str = "completed",
        label: str | None = None,
        progress_percent: int | None = None,
        resource_type: str | None = None,
    ) -> None:
        context = state.get("job_context")
        if context is None:
            return
        default_progress, default_label = self.job_progress.get(name, (60, f"{name} 已完成"))
        try:
            context.after_node(
                name=name,
                label=label or default_label,
                progress_percent=default_progress if progress_percent is None else progress_percent,
                status=status,
                resource_type=resource_type,
            )
        except Exception:
            return

    def _record(
        self,
        state: ResourceGenerationState,
        *,
        agent_name: str,
        step_index: int,
        input_summary: str,
        output_summary: str,
        status: str = "completed",
        metadata: dict[str, Any] | None = None,
        started_at: float | None = None,
    ) -> None:
        started = started_at if started_at is not None else perf_counter()
        duration_ms = max(1, int((perf_counter() - started) * 1000))
        try:
            self.service.trace_recorder.record(
                trace_id=str(state["trace_id"]),
                user_id=int(state["user_id"]),
                course_id=int(state["course_id"]) if state.get("course_id") is not None else None,
                agent_name=agent_name,
                step_index=step_index,
                status=status,
                input_summary=input_summary,
                output_summary=output_summary,
                duration_ms=duration_ms,
                workflow=self.workflow,
                artifact_type=self.artifact_type,
                metadata=metadata,
            )
        except Exception:
            return

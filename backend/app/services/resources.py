from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.api.errors import make_trace_id
from backend.app.models import (
    AgentRunLog,
    Course,
    GeneratedResource,
    KnowledgeChunk,
    KnowledgePoint,
    ResourceQualityScore,
    StudentProfile,
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
from backend.app.services.model_settings import ModelNotConfiguredError


RESOURCE_TYPES = ("doc", "mindmap", "quiz", "code", "slide")
QUALITY_SCORE_NAMES = ("source_match", "profile_fit", "fact_confidence", "difficulty_fit", "completeness")
RESOURCE_MODEL_TIMEOUT_SECONDS = 5.0
SENSITIVE_MARKERS = (
    "系统提示词",
    "system prompt",
    "模型输入",
    "model input",
    "api key",
    "sk-",
    "资料原文",
    "source text",
    "raw prompt",
)


class ResourceNotFoundError(Exception):
    pass


class ResourceValidationError(ValueError):
    pass


class ResourceGenerationError(RuntimeError):
    pass


class ResourceModelService(Protocol):
    def chat_completion(self, user: User, messages: list[dict[str, str]]) -> str: ...


class ResourceRepository(Protocol):
    def get_course_for_user(self, user_id: int, course_id: int) -> Course | None: ...

    def get_knowledge_point(self, course_id: int, knowledge_point_id: int) -> KnowledgePoint | None: ...

    def list_knowledge_points(self, course_id: int) -> list[KnowledgePoint]: ...

    def list_course_chunks(self, course_id: int, knowledge_point_id: int | None = None) -> list[KnowledgeChunk]: ...

    def get_profile(self, user_id: int) -> StudentProfile | None: ...

    def add_resource(self, resource: GeneratedResource) -> GeneratedResource: ...

    def add_quality_score(self, score: ResourceQualityScore) -> ResourceQualityScore: ...

    def add_agent_log(self, log: AgentRunLog) -> AgentRunLog: ...

    def list_resources(
        self,
        user_id: int,
        *,
        course_id: int | None = None,
        resource_type: str | None = None,
    ) -> list[GeneratedResource]: ...

    def get_resource_for_user(self, user_id: int, resource_id: int) -> GeneratedResource | None: ...

    def list_quality_scores(self, resource_id: int) -> list[ResourceQualityScore]: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...

    def refresh(self, instance: object) -> None: ...


class SqlAlchemyResourceRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_course_for_user(self, user_id: int, course_id: int) -> Course | None:
        return self.db.scalar(select(Course).where(Course.id == course_id, Course.owner_id == user_id))

    def get_knowledge_point(self, course_id: int, knowledge_point_id: int) -> KnowledgePoint | None:
        return self.db.scalar(
            select(KnowledgePoint).where(
                KnowledgePoint.id == knowledge_point_id,
                KnowledgePoint.course_id == course_id,
            )
        )

    def list_knowledge_points(self, course_id: int) -> list[KnowledgePoint]:
        return list(
            self.db.scalars(
                select(KnowledgePoint)
                .where(KnowledgePoint.course_id == course_id)
                .order_by(KnowledgePoint.order_index, KnowledgePoint.id)
            )
        )

    def list_course_chunks(self, course_id: int, knowledge_point_id: int | None = None) -> list[KnowledgeChunk]:
        statement = select(KnowledgeChunk).where(KnowledgeChunk.course_id == course_id)
        if knowledge_point_id is not None:
            statement = statement.where(KnowledgeChunk.knowledge_point_id == knowledge_point_id)
        return list(self.db.scalars(statement.order_by(KnowledgeChunk.id).limit(5)))

    def get_profile(self, user_id: int) -> StudentProfile | None:
        return self.db.scalar(select(StudentProfile).where(StudentProfile.user_id == user_id))

    def add_resource(self, resource: GeneratedResource) -> GeneratedResource:
        self.db.add(resource)
        self.db.flush()
        return resource

    def add_quality_score(self, score: ResourceQualityScore) -> ResourceQualityScore:
        self.db.add(score)
        self.db.flush()
        return score

    def add_agent_log(self, log: AgentRunLog) -> AgentRunLog:
        self.db.add(log)
        self.db.flush()
        return log

    def list_resources(
        self,
        user_id: int,
        *,
        course_id: int | None = None,
        resource_type: str | None = None,
    ) -> list[GeneratedResource]:
        statement = select(GeneratedResource).where(GeneratedResource.user_id == user_id)
        if course_id is not None:
            statement = statement.where(GeneratedResource.course_id == course_id)
        if resource_type is not None:
            statement = statement.where(GeneratedResource.resource_type == resource_type)
        return list(self.db.scalars(statement.order_by(GeneratedResource.updated_at.desc(), GeneratedResource.id.desc())))

    def get_resource_for_user(self, user_id: int, resource_id: int) -> GeneratedResource | None:
        return self.db.scalar(
            select(GeneratedResource).where(
                GeneratedResource.id == resource_id,
                GeneratedResource.user_id == user_id,
            )
        )

    def list_quality_scores(self, resource_id: int) -> list[ResourceQualityScore]:
        return list(
            self.db.scalars(
                select(ResourceQualityScore)
                .where(ResourceQualityScore.resource_id == resource_id)
                .order_by(ResourceQualityScore.id)
            )
        )

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()

    def refresh(self, instance: object) -> None:
        self.db.refresh(instance)


@dataclass(frozen=True)
class SafeCitation:
    chunk_id: int
    knowledge_point_id: int | None
    source_title: str
    section_title: str
    page_number: int | None

    def to_json(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "knowledge_point_id": self.knowledge_point_id,
            "source_title": self.source_title,
            "section_title": self.section_title,
            "page_number": self.page_number,
        }


@dataclass(frozen=True)
class ResourceDraft:
    title: str
    markdown: str
    content_json: dict[str, Any]


class ResourceGenerationService:
    def __init__(self, repository: ResourceRepository, model_settings_service: ResourceModelService) -> None:
        self.repository = repository
        self.model_settings_service = model_settings_service

    def generate_resources(
        self,
        user: User,
        *,
        course_id: int,
        resource_types: list[str],
        knowledge_point_id: int | None = None,
        learning_goal: str = "",
        difficulty: str = "medium",
    ) -> GenerateResourcesResult:
        course = self._require_course(user, course_id)
        knowledge_point = self._resolve_knowledge_point(course.id, knowledge_point_id)
        unique_types = self._normalize_resource_types(resource_types)
        if difficulty not in {"easy", "medium", "hard"}:
            raise ResourceValidationError("不支持的资源难度。")

        context_points = self.repository.list_knowledge_points(course.id)
        chunks = self.repository.list_course_chunks(course.id, knowledge_point.id if knowledge_point is not None else None)
        citations = self._safe_citations(chunks, knowledge_point, context_points)
        if not citations and knowledge_point is None and not context_points:
            raise ResourceGenerationError("当前课程没有足够依据生成资源。")

        profile = self.repository.get_profile(user.id)
        profile_summary = self._profile_summary(profile)
        agent_trace_id = make_trace_id()
        resources: list[GeneratedResource] = []
        quality_scores: dict[str, list[Any]] = {}
        generation_warnings = 0
        model_failed = False

        try:
            self._log(agent_trace_id, user, course.id, "profile", 1, "读取用户级画像摘要", "画像已合入资源生成上下文")
            self._log(
                agent_trace_id,
                user,
                course.id,
                "retrieve",
                2,
                "检索课程引用摘要",
                f"命中 {len(citations)} 条安全引用摘要",
                metadata={"citation_count": len(citations), "source_count": len(citations)},
            )
            self._log(
                agent_trace_id,
                user,
                course.id,
                "diagnosis",
                3,
                "分析资源类型、难度和课程上下文",
                f"准备生成 {len(unique_types)} 类资源",
                metadata={"knowledge_point_id": knowledge_point.id if knowledge_point is not None else None},
            )

            for resource_type in unique_types:
                draft = self._build_draft(
                    resource_type=resource_type,
                    course=course,
                    knowledge_point=knowledge_point,
                    context_points=context_points,
                    citations=citations,
                    profile_summary=profile_summary,
                    difficulty=difficulty,
                )
                markdown, review_status, confidence, model_failed_for_resource = self._enhance_with_model(
                    user=user,
                    draft=draft,
                    resource_type=resource_type,
                    citations=citations,
                    learning_goal=learning_goal,
                    difficulty=difficulty,
                    allow_model=not model_failed,
                )
                if model_failed_for_resource:
                    model_failed = True
                if review_status == "low_evidence":
                    generation_warnings += 1
                content_json = {
                    **draft.content_json,
                    "markdown": markdown,
                    "metadata": {
                        "agent_trace_id": agent_trace_id,
                        "generation_mode": "model" if review_status == "passed" else "deterministic_fallback",
                        "difficulty": difficulty,
                        "has_learning_goal": bool(learning_goal.strip()),
                    },
                }
                resource = self.repository.add_resource(
                    GeneratedResource(
                        user_id=user.id,
                        course_id=course.id,
                        knowledge_point_id=knowledge_point.id if knowledge_point is not None else None,
                        resource_type=resource_type,
                        title=draft.title,
                        content_json=content_json,
                        citation_json=[citation.to_json() for citation in citations],
                        status="completed",
                        review_status=review_status,
                        confidence_score=confidence,
                    )
                )
                resources.append(resource)
                scores = self._create_quality_scores(resource.id, review_status)
                quality_scores[str(resource.id)] = [
                    quality_score_to_api(self.repository.add_quality_score(score)) for score in scores
                ]

            review_status = "warning" if generation_warnings else "completed"
            review_result = "low_evidence" if generation_warnings else "passed"
            self._log(
                agent_trace_id,
                user,
                course.id,
                "resource",
                4,
                "生成课程资源",
                f"生成 {len(resources)} 个课程资源",
                metadata={"resource_count": len(resources)},
            )
            self._log(
                agent_trace_id,
                user,
                course.id,
                "review",
                5,
                "审核资源依据和画像贴合度",
                f"审核结果：{review_result}",
                status=review_status,
                metadata={
                    "confidence": 0.55 if generation_warnings else 0.82,
                    "review_result": review_result,
                    "resource_count": len(resources),
                },
            )
            self._log(
                agent_trace_id,
                user,
                course.id,
                "persist",
                6,
                "保存资源、质量分和轨迹摘要",
                f"保存 {len(resources)} 个资源",
                metadata={"resource_count": len(resources)},
            )

            self.repository.commit()
            for resource in resources:
                self.repository.refresh(resource)
        except Exception:
            self.repository.rollback()
            raise

        return GenerateResourcesResult(
            agent_trace_id=agent_trace_id,
            resources=[generated_resource_to_api(resource) for resource in resources],
            quality_scores=quality_scores,
        )

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
            data=[generated_resource_to_api(resource) for resource in resources],
            page=1,
            page_size=len(resources),
            total=len(resources),
        )

    def get_resource(self, user: User, resource_id: int) -> GeneratedResourceResponse:
        resource = self.repository.get_resource_for_user(user.id, resource_id)
        if resource is None:
            raise ResourceNotFoundError("资源不存在或无权访问。")
        return generated_resource_to_api(resource)

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
        if len(unique_types) > 5:
            raise ResourceValidationError("一次最多生成 5 类资源。")
        return unique_types

    @staticmethod
    def _safe_citations(
        chunks: list[KnowledgeChunk],
        knowledge_point: KnowledgePoint | None,
        context_points: list[KnowledgePoint],
    ) -> list[SafeCitation]:
        point_by_id = {point.id: point for point in context_points}
        if knowledge_point is not None:
            point_by_id[knowledge_point.id] = knowledge_point
        citations: list[SafeCitation] = []
        for chunk in chunks[:5]:
            metadata = chunk.metadata_json or {}
            source_title = ResourceGenerationService._safe_title(metadata.get("source_filename") or "课程资料")
            section_title = ResourceGenerationService._safe_title(chunk.section_title)
            point = point_by_id.get(chunk.knowledge_point_id or 0) or knowledge_point
            fallback_title = point.title if point is not None else "课程知识点"
            citations.append(
                SafeCitation(
                    chunk_id=chunk.id,
                    knowledge_point_id=chunk.knowledge_point_id,
                    source_title=source_title or "课程资料",
                    section_title=section_title or fallback_title,
                    page_number=chunk.page_number,
                )
            )
        return citations

    @staticmethod
    def _profile_summary(profile: StudentProfile | None) -> dict[str, Any]:
        if profile is None:
            return {"learning_goal": "", "knowledge_foundation": "", "weak_points": [], "learning_preference": ""}
        data = profile.profile_json or {}
        weak_points = data.get("weak_points")
        return {
            "learning_goal": ResourceGenerationService._safe_title(data.get("learning_goal")),
            "knowledge_foundation": ResourceGenerationService._safe_title(data.get("knowledge_foundation")),
            "weak_points": weak_points if isinstance(weak_points, list) else [],
            "learning_preference": ResourceGenerationService._safe_title(data.get("learning_preference")),
        }

    @staticmethod
    def _build_draft(
        *,
        resource_type: str,
        course: Course,
        knowledge_point: KnowledgePoint | None,
        context_points: list[KnowledgePoint],
        citations: list[SafeCitation],
        profile_summary: dict[str, Any],
        difficulty: str,
    ) -> ResourceDraft:
        topic = knowledge_point.title if knowledge_point is not None else (context_points[0].title if context_points else course.title)
        title_map = {
            "doc": f"{topic}个性化讲解",
            "mindmap": f"{topic}思维导图",
            "quiz": f"{topic}练习题",
            "code": f"{topic}代码实操",
            "slide": f"{topic}PPT 大纲",
        }
        citation_lines = [f"- {citation.section_title}（{citation.source_title}）" for citation in citations] or ["- 当前课程知识点摘要"]
        weak_points = "、".join(str(item) for item in profile_summary.get("weak_points", [])[:3]) or "暂无明确薄弱点"
        markdown_builders = {
            "doc": ResourceGenerationService._doc_markdown,
            "mindmap": ResourceGenerationService._mindmap_markdown,
            "quiz": ResourceGenerationService._quiz_markdown,
            "code": ResourceGenerationService._code_markdown,
            "slide": ResourceGenerationService._slide_markdown,
        }
        markdown = markdown_builders[resource_type](topic, course.title, citation_lines, weak_points, difficulty)
        return ResourceDraft(
            title=title_map[resource_type],
            markdown=markdown,
            content_json={
                "format": "markdown",
                "topic": topic,
                "course_title": course.title,
                "citation_summaries": citation_lines,
                "profile_overlay": {
                    "learning_goal": profile_summary.get("learning_goal", ""),
                    "knowledge_foundation": profile_summary.get("knowledge_foundation", ""),
                    "weak_points": profile_summary.get("weak_points", []),
                    "learning_preference": profile_summary.get("learning_preference", ""),
                },
            },
        )

    @staticmethod
    def _doc_markdown(topic: str, course_title: str, citation_lines: list[str], weak_points: str, difficulty: str) -> str:
        return "\n".join(
            [
                f"# {topic}个性化讲解",
                f"课程：{course_title}",
                f"难度：{difficulty}",
                "",
                "## 学习目标",
                f"- 先理解 {topic} 的核心概念，再用例题检查薄弱点。",
                f"- 当前画像提示需要关注：{weak_points}。",
                "",
                "## 引用依据",
                *citation_lines,
                "",
                "## 复习建议",
                "- 用自己的话复述概念。",
                "- 做一道小题并标记仍卡住的位置。",
            ]
        )

    @staticmethod
    def _mindmap_markdown(topic: str, _course_title: str, citation_lines: list[str], _weak_points: str, _difficulty: str) -> str:
        branches = "\n".join(f"    {line.removeprefix('- ')}" for line in citation_lines[:4])
        return "\n".join(["# 思维导图", "```mermaid", "mindmap", f"  root(({topic}))", branches, "```"])

    @staticmethod
    def _quiz_markdown(topic: str, _course_title: str, citation_lines: list[str], _weak_points: str, _difficulty: str) -> str:
        basis = citation_lines[0].removeprefix("- ")
        return "\n".join(
            [
                f"# {topic}练习题",
                "## 单选题",
                f"1. 下列哪项最能帮助你判断 {topic} 的关键步骤？",
                "   - A. 只记结论",
                "   - B. 结合概念、条件和例题",
                "   - C. 跳过引用来源",
                "   - D. 只背题干",
                "答案：B",
                "",
                "## 多选题",
                f"2. 复习 {topic} 时可以参考哪些线索？",
                f"答案要点：{basis}；课程章节；自己的薄弱点。",
                "",
                "## 简答题",
                f"3. 用三句话说明 {topic} 的用途，并写出一个容易混淆的点。",
            ]
        )

    @staticmethod
    def _code_markdown(topic: str, _course_title: str, _citation_lines: list[str], _weak_points: str, _difficulty: str) -> str:
        return "\n".join(
            [
                f"# {topic}代码实操",
                "```python",
                "def explain_step(name: str, score: float) -> str:",
                "    return f\"{name}: 当前估计分数 {score:.2f}\"",
                "",
                "print(explain_step(\"search-state\", 0.82))",
                "```",
                "",
                "运行后尝试修改 score，观察输出如何变化，再把它对应回课程概念。",
            ]
        )

    @staticmethod
    def _slide_markdown(topic: str, course_title: str, citation_lines: list[str], weak_points: str, _difficulty: str) -> str:
        return "\n".join(
            [
                f"# {topic}PPT 大纲",
                f"1. 课程背景：{course_title}",
                f"2. 核心概念：{topic}",
                f"3. 引用来源：{citation_lines[0].removeprefix('- ')}",
                f"4. 学生薄弱点：{weak_points}",
                "5. 课堂练习：用一个例题验证理解",
                "6. 讲稿提示：每页用一个问题引出下一步。",
            ]
        )

    def _enhance_with_model(
        self,
        *,
        user: User,
        draft: ResourceDraft,
        resource_type: str,
        citations: list[SafeCitation],
        learning_goal: str,
        difficulty: str,
        allow_model: bool = True,
    ) -> tuple[str, str, Decimal, bool]:
        if not allow_model:
            return draft.markdown, "low_evidence", Decimal("0.55"), False
        messages = [
            {
                "role": "system",
                "content": "你是 EduNova 的资源生成 Agent，只能基于课程引用摘要和学生画像摘要改写学习资源。",
            },
            {
                "role": "user",
                "content": "\n".join(
                    [
                        f"资源类型：{resource_type}",
                        f"难度：{difficulty}",
                        f"学习目标：{learning_goal[:200]}",
                        "引用摘要：",
                        *[f"- {citation.section_title} / {citation.source_title}" for citation in citations],
                        "请输出可直接展示给学生的 Markdown。",
                    ]
                ),
            },
        ]
        try:
            content = self._call_model_for_resource(user, messages)
        except (ModelNotConfiguredError, ModelProviderError):
            return draft.markdown, "low_evidence", Decimal("0.55"), True
        if self._contains_sensitive(content):
            return draft.markdown, "low_evidence", Decimal("0.55"), False
        return content.strip() or draft.markdown, "passed", Decimal("0.82"), False

    def _call_model_for_resource(self, user: User, messages: list[dict[str, str]]) -> str:
        completion_with_timeout = getattr(self.model_settings_service, "chat_completion_with_timeout", None)
        if callable(completion_with_timeout):
            return completion_with_timeout(user, messages, timeout_seconds=RESOURCE_MODEL_TIMEOUT_SECONDS)
        return self.model_settings_service.chat_completion(user, messages)

    @staticmethod
    def _create_quality_scores(resource_id: int, review_status: str) -> list[ResourceQualityScore]:
        base = Decimal("0.55") if review_status == "low_evidence" else Decimal("0.82")
        rationales = {
            "source_match": "基于课程引用摘要生成。",
            "profile_fit": "结合用户级画像叠层。",
            "fact_confidence": "低依据状态会降低事实置信分。",
            "difficulty_fit": "按请求难度生成。",
            "completeness": "覆盖本阶段资源最小结构。",
        }
        return [
            ResourceQualityScore(
                resource_id=resource_id,
                score_name=name,
                score_value=base if name != "completeness" else min(Decimal("0.90"), base + Decimal("0.06")),
                rationale=rationales[name],
            )
            for name in QUALITY_SCORE_NAMES
        ]

    def _log(
        self,
        trace_id: str,
        user: User,
        course_id: int,
        agent_name: str,
        step_index: int,
        input_summary: str,
        output_summary: str,
        *,
        status: str = "completed",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        now = datetime.now(UTC)
        self.repository.add_agent_log(
            AgentRunLog(
                user_id=user.id,
                course_id=course_id,
                trace_id=trace_id,
                agent_name=agent_name,
                step_index=step_index,
                status=status,
                input_summary=input_summary,
                output_summary=output_summary,
                duration_ms=10 + step_index,
                metadata_json=metadata or {},
                created_at=now,
            )
        )

    @staticmethod
    def _safe_title(value: object) -> str:
        if value is None:
            return ""
        return " ".join(str(value).split())[:120]

    @staticmethod
    def _contains_sensitive(value: str) -> bool:
        lowered = value.lower()
        return any(marker in lowered or marker in value for marker in SENSITIVE_MARKERS)

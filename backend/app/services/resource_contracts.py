from __future__ import annotations

import operator
from dataclasses import dataclass
from typing import Annotated, Any, Protocol

from backend.app.agents.schemas import AgentState
from backend.app.core.errors import NotFoundDomainError, ValidationDomainError
from backend.app.providers.model_tasks import ModelTaskProfile
from backend.app.models import (
    AgentRunLog,
    Course,
    GeneratedResource,
    KnowledgeChunk,
    KnowledgePoint,
    LearningTask,
    ResourceQualityScore,
    StudentProfile,
    User,
)
from backend.app.services.resource_artifacts import ArtifactBuildInput
from backend.app.services.resource_intent import GenerationAction
from backend.app.services.video_resources import VideoCurationError


RESOURCE_TYPES = ("doc", "mindmap", "quiz", "code", "slide", "animation", "video")
QUALITY_SCORE_NAMES = (
    "source_match",
    "profile_fit",
    "fact_confidence",
    "difficulty_fit",
    "completeness",
    "authenticity",
    "personalization",
    "diversity",
    "pedagogical_utility",
    "type_correctness",
)
RESOURCE_MODEL_TIMEOUT_SECONDS = 45.0
RESOURCE_EXCERPT_LIMIT = 96
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
RESOURCE_TYPE_LABELS = {
    "doc": "讲解文档",
    "mindmap": "思维导图",
    "quiz": "练习题",
    "code": "代码实操",
    "slide": "PPT",
    "animation": "动画图解",
    "video": "教学视频",
}


class ResourceNotFoundError(NotFoundDomainError):
    pass


class ResourceValidationError(ValidationDomainError):
    pass


class ResourceGenerationError(ValidationDomainError):
    pass


def resource_failure_message(resource_type: str, error: Exception) -> str:
    """Return a student-facing outcome without exposing model or validation internals."""
    label = RESOURCE_TYPE_LABELS.get(resource_type, "该资源")
    if isinstance(error, VideoCurationError):
        return "暂未匹配到可靠教学视频，已保留其他资源。可以稍后重新匹配。"
    if isinstance(error, ResourceGenerationError):
        return f"{label}本次未生成，未保存不完整内容。可以重新生成。"
    return f"{label}暂时未生成，其他资源不受影响。可以稍后重试。"


def resource_review_failure_message(resource_type: str, _reason: str) -> str:
    label = RESOURCE_TYPE_LABELS.get(resource_type, "该资源")
    return f"{label}未通过内容检查，未保存本次产物。可以重新生成。"


class ResourceGenerationState(AgentState, total=False):
    worker_resource_type: str
    worker_results: Annotated[list[dict[str, Any]], operator.add]
    resource_plan: dict[str, Any]
    reviewed_results: list[dict[str, Any]]
    failed_resource_types: list[str]
    result_warnings: list[str]
    needs_repair: bool
    job_context: Any
    generation_action: GenerationAction
    source_resource: GeneratedResource | None
    historical_resources: list[GeneratedResource]
    artifact_intents: dict[str, dict[str, Any]]
    generation_batch_id: str
    path_task_id: int | None


class ResourceModelService(Protocol):
    def chat_completion_for_task(self, user: User, messages: list[dict[str, str]], profile: ModelTaskProfile) -> str: ...


class ResourceRepository(Protocol):
    def get_course_for_user(self, user_id: int, course_id: int) -> Course | None: ...

    def get_knowledge_point(self, course_id: int, knowledge_point_id: int) -> KnowledgePoint | None: ...

    def list_knowledge_points(self, course_id: int) -> list[KnowledgePoint]: ...

    def list_course_chunks(self, course_id: int, knowledge_point_id: int | None = None) -> list[KnowledgeChunk]: ...

    def get_profile(self, user_id: int) -> StudentProfile | None: ...

    def get_learning_task_for_user(self, user_id: int, task_id: int) -> LearningTask | None: ...

    def is_path_draft(self, path_id: int) -> bool: ...

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

    def get_resource_for_user(
        self,
        user_id: int,
        resource_id: int,
        *,
        for_update: bool = False,
    ) -> GeneratedResource | None: ...

    def list_learning_tasks_for_user(self, user_id: int) -> list[LearningTask]: ...

    def delete_resource(self, resource: GeneratedResource) -> None: ...

    def max_version_number(self, version_family_id: str) -> int: ...

    def lock_version_family(self, version_family_id: str) -> None: ...

    def list_quality_scores(self, resource_id: int) -> list[ResourceQualityScore]: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...

    def refresh(self, instance: object) -> None: ...


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
class ResourceContext:
    citation: SafeCitation
    excerpt: str
    keywords: list[str]


@dataclass(frozen=True)
class ResourceDraft:
    title: str
    markdown: str
    content_json: dict[str, Any]
    source: ArtifactBuildInput

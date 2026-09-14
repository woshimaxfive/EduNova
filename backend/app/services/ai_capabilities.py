"""Internal contracts for the two pilot AIJob capabilities, not a second runtime.

Validation never commits: AIJob owns scheduling/terminal state and the existing
LangGraph runners retain their domain persistence and model execution policies.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from backend.app.schemas.resources import GenerateResourcesRequest, ResourceType
from backend.app.services.ai_job_contracts import AiJobNotFoundError, AiJobValidationError

PositiveId = Annotated[int, Field(strict=True, gt=0)]
WireId = Annotated[str, Field(pattern=r"^[1-9][0-9]*$")]


class PathPlanningInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    course_id: PositiveId
    trigger: Literal["manual", "assessment"] = "manual"
    assessment_session_id: PositiveId | None = None


class ResourceGenerationInput(GenerateResourcesRequest):
    model_config = ConfigDict(extra="forbid", strict=True)
    course_id: PositiveId
    knowledge_point_id: PositiveId | None = None
    source_resource_id: PositiveId | None = None
    path_task_id: PositiveId | None = None
    tutor_message_id: PositiveId | None = None
    evidence_chunk_ids: list[PositiveId] = Field(default_factory=list, max_length=8)


class PathPlanningOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    course_id: PositiveId
    path_id: WireId | None
    generation_mode: str
    preserved_task_count: int = Field(ge=0)
    agent_trace_id: str
    warnings: list[str]


class ResourceGenerationOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    course_id: WireId
    knowledge_point_id: WireId | None
    evidence_chunk_ids: list[PositiveId] = Field(max_length=8)
    path_task_id: WireId | None
    resource_ids: list[WireId]
    failed_resource_types: list[ResourceType]
    warnings: list[str]


class CapabilityInputError(AiJobValidationError):
    code = "CAPABILITY_INPUT_INVALID"


class CapabilityOutputError(AiJobValidationError):
    code = "CAPABILITY_OUTPUT_INVALID"


@dataclass(frozen=True)
class AiCapability:
    input_model: type[PathPlanningInput] | type[ResourceGenerationInput]
    output_model: type[PathPlanningOutput] | type[ResourceGenerationOutput]

    def validate_input(self, payload: Any, course_id: int | None) -> PathPlanningInput | ResourceGenerationInput:
        try:
            request = self.input_model.model_validate(payload)
        except ValidationError:
            # Never expose validation input (potentially private text) in job errors.
            raise CapabilityInputError("AI 任务输入不符合能力合同。") from None
        if request.course_id != course_id:
            raise CapabilityInputError("AI 任务课程范围不一致。")
        return request

    def validate_output(self, payload: Any, course_id: int) -> dict[str, Any]:
        try:
            result = self.output_model.model_validate(payload)
        except ValidationError:
            raise CapabilityOutputError("AI 任务结果不符合能力合同。") from None
        if int(result.course_id) != course_id:
            raise CapabilityOutputError("AI 任务结果课程范围不一致。")
        # Preserve legacy wire types: path course is int, resource course is str.
        return result.model_dump(mode="json")


AI_CAPABILITIES = MappingProxyType({
    "path_planning": AiCapability(PathPlanningInput, PathPlanningOutput),
    "resource_generation": AiCapability(ResourceGenerationInput, ResourceGenerationOutput),
})


def validate_capability_scope(repository: Any, user_id: int, request: PathPlanningInput | ResourceGenerationInput) -> None:
    """Recheck queued/retried work against current deterministic authorization."""
    course_id = request.course_id
    if repository.get_course_for_user(user_id, course_id) is None:
        raise AiJobNotFoundError("课程不存在或无权访问。")
    if not repository.is_course_active(user_id, course_id):
        raise AiJobValidationError("课程已完成归档；请先恢复学习。")
    if isinstance(request, PathPlanningInput):
        if request.assessment_session_id is not None:
            session = repository.get_practice_session_for_user(user_id, request.assessment_session_id)
            if session is None or session.course_id != course_id:
                raise AiJobNotFoundError("评估不存在或不属于当前课程。")
        return
    if not isinstance(request, ResourceGenerationInput):
        raise CapabilityInputError("不支持的能力输入。")
    if request.knowledge_point_id is not None:
        if repository.get_knowledge_point(course_id, request.knowledge_point_id) is None:
            raise AiJobNotFoundError("知识点不存在或不属于当前课程。")
    if request.path_task_id is not None:
        task = repository.get_learning_task_for_user(user_id, request.path_task_id)
        if task is None or task.course_id != course_id:
            raise AiJobNotFoundError("学习任务不存在或不属于当前课程。")
        if task.knowledge_point_id != request.knowledge_point_id:
            raise AiJobValidationError("学习任务知识点不一致。")
    if request.tutor_message_id is not None:
        if not repository.has_message_for_user(user_id, request.tutor_message_id):
            raise AiJobNotFoundError("来源回答不存在或无权访问。")
    if request.evidence_chunk_ids:
        if not repository.has_course_chunks(course_id, request.evidence_chunk_ids):
            raise AiJobNotFoundError("引用证据不存在或不属于当前课程。")
    if request.source_resource_id is not None:
        source = repository.get_resource_for_user(user_id, request.source_resource_id)
        if source is None or source.course_id != course_id:
            raise AiJobNotFoundError("来源资源不存在或无权访问。")
        if source.status != "completed" or request.resource_types != [source.resource_type]:
            raise AiJobValidationError("来源资源不可用或资源类型不一致。")
        if source.knowledge_point_id != request.knowledge_point_id:
            raise AiJobValidationError("来源资源知识点不一致。")

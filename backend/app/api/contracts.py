from __future__ import annotations

from typing import Any, Generic, TypeVar

from fastapi import APIRouter
from fastapi.datastructures import DefaultPlaceholder
from pydantic import BaseModel

from backend.app.schemas.agents import AgentTraceResponse
from backend.app.schemas.ai_jobs import AiJobListResponse, AiJobResponse
from backend.app.schemas.auth import ApiUser
from backend.app.schemas.courses import (
    CourseKnowledgePoint,
    CourseKnowledgePointContent,
    CourseLearningState,
    CourseMasteryMap,
    CourseOverview,
    CourseSummary,
    CourseWeaknessReviewItem,
    CreateCourseFromMaterialsResult,
)
from backend.app.schemas.dashboard import DashboardSummary
from backend.app.schemas.learning import LearningNextAction
from backend.app.schemas.exports import ExportJobResponse, LearningDossierExport
from backend.app.schemas.materials import (
    AttachCourseMaterialsResult,
    MaterialComparisonResult,
    MaterialDetail,
    MaterialListItem,
    MaterialOutlineResponse,
    MaterialProgress,
    MaterialUploadResult,
)
from backend.app.schemas.paths import LearningPathDetail, LearningPathTaskResponse
from backend.app.schemas.practice import PracticeSessionDetail, PracticeSessionSummary
from backend.app.schemas.profiles import ProfileChatResponse, ProfileEventResponse, StudentProfileResponse
from backend.app.schemas.rag import RagSearchResponse
from backend.app.schemas.reports import ReportEnvelope
from backend.app.schemas.resources import (
    GeneratedResourceResponse,
    GenerateResourcesResult,
    ResourceQualityScoreResponse,
    ResourceLearningStateResponse,
)
from backend.app.schemas.tutor import (
    DeleteTutorSessionResponse,
    TutorSessionDetail,
    TutorSessionHistoryPage,
    TutorSessionSummary,
    TutorImageAttachment,
)
from backend.app.services.model_settings import (
    ModelConfigSummary,
    ModelConnectionTestResponse,
    ModelSettingsListResponse,
    ModelSettingsSummary,
)
from backend.app.services.conversation_memory import (
    ClearConversationMemoryResponse,
    PrivacySettingsResponse,
)


T = TypeVar("T")


class ApiEnvelope(BaseModel, Generic[T]):
    data: T
    trace_id: str


class ApiErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, Any]


class ApiErrorEnvelope(BaseModel):
    error: ApiErrorBody
    trace_id: str


class OkResponse(BaseModel):
    ok: bool


class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    user: ApiUser


class CourseListEnvelope(BaseModel):
    data: list[CourseSummary]
    page: int
    page_size: int
    total: int
    trace_id: str


class ResourceListEnvelope(BaseModel):
    data: list[GeneratedResourceResponse]
    page: int
    page_size: int
    total: int
    trace_id: str


class HealthResponse(BaseModel):
    status: str
    service: str


ERROR_RESPONSES = {
    status_code: {"model": ApiErrorEnvelope}
    for status_code in (400, 401, 403, 404, 409, 422, 500, 502, 503)
}


RESPONSE_MODELS: dict[str, Any] = {
    "get_agent_trace": ApiEnvelope[AgentTraceResponse],
    "list_ai_jobs": ApiEnvelope[AiJobListResponse],
    "get_ai_job": ApiEnvelope[AiJobResponse],
    "cancel_ai_job": ApiEnvelope[AiJobResponse],
    "retry_ai_job": ApiEnvelope[AiJobResponse],
    "register": ApiEnvelope[ApiUser],
    "login": ApiEnvelope[LoginResponse],
    "me": ApiEnvelope[ApiUser],
    "update_me": ApiEnvelope[ApiUser],
    "change_password": ApiEnvelope[OkResponse],
    "logout": ApiEnvelope[OkResponse],
    "list_courses": CourseListEnvelope,
    "get_course": ApiEnvelope[CourseSummary],
    "get_course_overview": ApiEnvelope[CourseOverview],
    "get_course_knowledge_points": ApiEnvelope[list[CourseKnowledgePoint]],
    "get_course_knowledge_point_content": ApiEnvelope[CourseKnowledgePointContent],
    "get_course_mastery_map": ApiEnvelope[CourseMasteryMap],
    "get_course_learning_state": ApiEnvelope[CourseLearningState],
    "confirm_weakness_review_item": ApiEnvelope[CourseWeaknessReviewItem],
    "start_weakness_review_item": ApiEnvelope[CourseWeaknessReviewItem],
    "complete_weakness_review_item": ApiEnvelope[CourseWeaknessReviewItem],
    "dismiss_weakness_review_item": ApiEnvelope[CourseWeaknessReviewItem],
    "create_course_from_materials": ApiEnvelope[CreateCourseFromMaterialsResult],
    "create_course_from_materials_job": ApiEnvelope[AiJobResponse],
    "summary": ApiEnvelope[DashboardSummary],
    "get_learning_next_action": ApiEnvelope[LearningNextAction],
    "export_learning_dossier": ApiEnvelope[LearningDossierExport],
    "create_learning_dossier_export_job": ApiEnvelope[ExportJobResponse],
    "get_export_job": ApiEnvelope[ExportJobResponse],
    "upload_material": ApiEnvelope[MaterialUploadResult],
    "create_material_ingestion_job": ApiEnvelope[AiJobResponse],
    "get_material_outline": ApiEnvelope[MaterialOutlineResponse],
    "update_material_outline": ApiEnvelope[MaterialOutlineResponse],
    "confirm_material_outline": ApiEnvelope[MaterialOutlineResponse],
    "list_materials": ApiEnvelope[list[MaterialListItem]],
    "compare_materials": ApiEnvelope[MaterialComparisonResult],
    "get_latest_material_comparison": ApiEnvelope[MaterialComparisonResult | None],
    "get_material_comparison": ApiEnvelope[MaterialComparisonResult],
    "get_material": ApiEnvelope[MaterialDetail],
    "get_material_progress": ApiEnvelope[MaterialProgress],
    "attach_course_materials": ApiEnvelope[AttachCourseMaterialsResult],
    "generate_path": ApiEnvelope[LearningPathDetail],
    "create_path_generation_job": ApiEnvelope[AiJobResponse],
    "create_path_task_resource_job": ApiEnvelope[AiJobResponse],
    "get_current_path": ApiEnvelope[LearningPathDetail],
    "update_path_task": ApiEnvelope[LearningPathTaskResponse],
    "create_practice_session": ApiEnvelope[PracticeSessionDetail],
    "get_latest_practice_session": ApiEnvelope[PracticeSessionDetail | None],
    "list_recent_completed_practice_sessions": ApiEnvelope[list[PracticeSessionSummary]],
    "get_practice_session": ApiEnvelope[PracticeSessionDetail],
    "save_practice_draft": ApiEnvelope[PracticeSessionDetail],
    "submit_practice_answers": ApiEnvelope[PracticeSessionDetail],
    "regrade_practice_answers": ApiEnvelope[PracticeSessionDetail],
    "get_my_profile": ApiEnvelope[StudentProfileResponse],
    "update_profile_by_chat": ApiEnvelope[ProfileChatResponse],
    "list_profile_events": ApiEnvelope[list[ProfileEventResponse]],
    "search_course_knowledge": ApiEnvelope[RagSearchResponse],
    "generate_report": ApiEnvelope[ReportEnvelope],
    "get_latest_report": ApiEnvelope[ReportEnvelope],
    "generate_resources": ApiEnvelope[GenerateResourcesResult],
    "create_resource_generation_job": ApiEnvelope[AiJobResponse],
    "list_resources": ResourceListEnvelope,
    "get_resource": ApiEnvelope[GeneratedResourceResponse],
    "get_resource_quality": ApiEnvelope[list[ResourceQualityScoreResponse]],
    "create_resource_export_job": ApiEnvelope[ExportJobResponse],
    "list_resource_export_jobs": ApiEnvelope[list[ExportJobResponse]],
    "record_resource_interaction": ApiEnvelope[ResourceLearningStateResponse],
    "get_resource_learning_state": ApiEnvelope[ResourceLearningStateResponse],
    "get_model_settings": ApiEnvelope[ModelSettingsSummary],
    "save_model_settings": ApiEnvelope[ModelSettingsSummary],
    "list_model_configs": ApiEnvelope[ModelSettingsListResponse],
    "create_model_config": ApiEnvelope[ModelConfigSummary],
    "update_model_config": ApiEnvelope[ModelConfigSummary],
    "delete_model_config": ApiEnvelope[ModelSettingsListResponse],
    "set_default_model_config": ApiEnvelope[ModelSettingsListResponse],
    "set_embedding_default_model_config": ApiEnvelope[ModelSettingsListResponse],
    "set_rerank_default_model_config": ApiEnvelope[ModelSettingsListResponse],
    "set_vision_default_model_config": ApiEnvelope[ModelSettingsListResponse],
    "test_model_config": ApiEnvelope[ModelConnectionTestResponse],
    "test_model_settings": ApiEnvelope[ModelConnectionTestResponse],
    "create_embedding_reindex_job": ApiEnvelope[AiJobResponse],
    "get_privacy_settings": ApiEnvelope[PrivacySettingsResponse],
    "update_privacy_settings": ApiEnvelope[PrivacySettingsResponse],
    "clear_conversation_memory": ApiEnvelope[ClearConversationMemoryResponse],
    "create_session": ApiEnvelope[TutorSessionSummary],
    "list_sessions": ApiEnvelope[list[TutorSessionSummary]],
    "list_home_history": ApiEnvelope[TutorSessionHistoryPage],
    "get_session": ApiEnvelope[TutorSessionDetail],
    "rename_session": ApiEnvelope[TutorSessionSummary],
    "delete_session": ApiEnvelope[DeleteTutorSessionResponse],
    "send_message": ApiEnvelope[TutorSessionDetail],
    "upload_tutor_attachment": ApiEnvelope[TutorImageAttachment],
    "delete_tutor_attachment": ApiEnvelope[TutorImageAttachment],
}


class TypedAPIRouter(APIRouter):
    """Bind stable transport schemas without leaking generator types into handlers."""

    def add_api_route(self, path: str, endpoint, *, response_model=None, responses=None, **kwargs):  # type: ignore[no-untyped-def]
        if isinstance(response_model, DefaultPlaceholder) or response_model is None:
            response_model = RESPONSE_MODELS.get(endpoint.__name__, response_model)
        merged_responses = {**ERROR_RESPONSES, **(responses or {})}
        return super().add_api_route(
            path,
            endpoint,
            response_model=response_model,
            responses=merged_responses,
            **kwargs,
        )

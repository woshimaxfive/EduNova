from __future__ import annotations


from fastapi import Depends, File, Header, Query, Response, UploadFile, status
from sse_starlette import EventSourceResponse

from backend.app.api.contracts import TypedAPIRouter as APIRouter
from backend.app.agents.runtime import AgentTraceRecorder
from backend.app.api.errors import ApiError, api_response
from backend.app.api.sse import event_source_response, sse_event
from backend.app.api.v1.deps import get_current_user
from backend.app.core.config import get_settings
from backend.app.db.session import get_db_session
from backend.app.models import User
from backend.app.providers.openai_compatible import OpenAICompatibleChatProvider
from backend.app.schemas.tutor import (
    AttachTutorMaterialRequest,
    CreateTutorSessionRequest,
    DeleteTutorSessionResponse,
    SendTutorMessageRequest,
    CreateTutorResourceJobRequest,
    UpdateTutorSessionRequest,
    attachment_to_api,
)
from backend.app.services.course_answers import CourseAnswerGenerationError, CourseAnswerService
from backend.app.services.embeddings import EmbeddingService
from backend.app.services.model_settings import ModelSettingsService, SqlAlchemyModelSettingsRepository
from backend.app.services.material_retrieval import MaterialRetrievalService, SqlAlchemyMaterialRetrievalRepository
from backend.app.services.profiles import ProfileService, SqlAlchemyProfileRepository
from backend.app.services.rag import RagService, SqlAlchemyRagRepository
from backend.app.services.semantic_decision import SemanticDecisionService
from backend.app.services.tutor import (
    EmptyMessageError,
    InvalidMaterialContextError,
    InvalidResourceContextError,
    InvalidSessionScopeError,
    SessionNotFoundError,
    SqlAlchemyTutorSessionRepository,
    TutorSessionService,
)
from backend.app.services.tutor_attachments import (
    TutorAttachmentError,
    TutorAttachmentNotFoundError,
    TutorAttachmentService,
)
from backend.app.services.vision_understanding import VisionUnderstandingService
from backend.app.services.web_search import WebSearchService
from backend.app.services.conversation_memory import ConversationMemoryService, RqConversationMemoryQueue
from backend.app.api.v1.ai_jobs import get_ai_job_service
from backend.app.services.ai_jobs import AiJobService


router = APIRouter(prefix="/tutor", tags=["tutor"])


def get_tutor_attachment_service(db=Depends(get_db_session)) -> TutorAttachmentService:
    return TutorAttachmentService(db, get_settings())


def get_tutor_session_service(db=Depends(get_db_session)) -> TutorSessionService:
    model_settings_service = ModelSettingsService(
        repository=SqlAlchemyModelSettingsRepository(db),
        settings=get_settings(),
        provider=OpenAICompatibleChatProvider(),
    )
    attachment_service = TutorAttachmentService(db, get_settings())
    attachment_service.cleanup_expired_pending(limit=20)
    return TutorSessionService(
        SqlAlchemyTutorSessionRepository(db),
        course_citation_searcher=RagService(
            SqlAlchemyRagRepository(db),
            embedding_service=EmbeddingService(model_settings_service),
            rerank_service=model_settings_service,
        ),
        course_answer_generator=CourseAnswerService(model_settings_service),
        profile_event_recorder=ProfileService(
            SqlAlchemyProfileRepository(db),
            model_service=model_settings_service,
            trace_recorder=AgentTraceRecorder(),
        ),
        web_search_service=WebSearchService(get_settings()),
        material_citation_searcher=MaterialRetrievalService(
            SqlAlchemyMaterialRetrievalRepository(db),
            embedding_service=EmbeddingService(model_settings_service),
            rerank_service=model_settings_service,
        ),
        semantic_decision_service=SemanticDecisionService(model_settings_service),
        native_web_search_provider=model_settings_service,
        conversation_memory_service=ConversationMemoryService(
            db,
            EmbeddingService(model_settings_service),
            RqConversationMemoryQueue(
                redis_url=get_settings().redis_url,
                queue_name=get_settings().ai_job_queue_name,
            ),
        ),
        vision_understanding_service=VisionUnderstandingService(model_settings_service, attachment_service),
    )


@router.post("/sessions")
def create_session(
    payload: CreateTutorSessionRequest,
    current_user: User = Depends(get_current_user),
    service: TutorSessionService = Depends(get_tutor_session_service),
) -> dict:
    try:
        session = service.create_session(
            user=current_user,
            scope=payload.scope,
            course_id=payload.course_id,
            mode=payload.mode,
            title=payload.title,
            selected_material_ids=payload.selected_material_ids,
        )
    except InvalidSessionScopeError as exc:
        raise ApiError(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="VALIDATION_ERROR",
            message=str(exc),
        ) from exc
    except SessionNotFoundError as exc:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="NOT_FOUND",
            message="课程不存在或无权访问。",
        ) from exc
    except InvalidMaterialContextError as exc:
        raise ApiError(status_code=status.HTTP_400_BAD_REQUEST, code="MATERIAL_CONTEXT_INVALID", message=str(exc)) from exc

    from backend.app.schemas.tutor import session_to_summary

    return api_response(session_to_summary(session).model_dump())


@router.get("/sessions")
def list_sessions(
    scope: str = Query(default="home"),
    course_id: int | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    service: TutorSessionService = Depends(get_tutor_session_service),
) -> dict:
    try:
        sessions = service.list_sessions(user=current_user, scope=scope, course_id=course_id)
    except InvalidSessionScopeError as exc:
        raise ApiError(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="VALIDATION_ERROR",
            message=str(exc),
        ) from exc
    except SessionNotFoundError as exc:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="NOT_FOUND",
            message="课程不存在或无权访问。",
        ) from exc

    return api_response([session.model_dump() for session in sessions])


@router.get("/sessions/history")
def list_home_history(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=30, ge=1, le=50),
    q: str = Query(default="", max_length=100),
    current_user: User = Depends(get_current_user),
    service: TutorSessionService = Depends(get_tutor_session_service),
) -> dict:
    result = service.list_home_history(current_user, page=page, page_size=page_size, query=q)
    return api_response(result.model_dump())


@router.get("/sessions/{session_id}")
def get_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    service: TutorSessionService = Depends(get_tutor_session_service),
) -> dict:
    try:
        detail = service.get_session(user=current_user, session_id=session_id)
    except SessionNotFoundError as exc:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="NOT_FOUND",
            message="会话不存在或无权访问。",
        ) from exc
    except CourseAnswerGenerationError as exc:
        raise ApiError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="MODEL_PROVIDER_ERROR",
            message=str(exc),
        ) from exc

    return api_response(detail.model_dump())


@router.patch("/sessions/{session_id}")
def rename_session(
    session_id: int,
    payload: UpdateTutorSessionRequest,
    current_user: User = Depends(get_current_user),
    service: TutorSessionService = Depends(get_tutor_session_service),
) -> dict:
    try:
        session = service.update_session(
            user=current_user,
            session_id=session_id,
            title=payload.title,
            selected_material_ids=payload.selected_material_ids,
        )
    except EmptyMessageError as exc:
        raise ApiError(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="VALIDATION_ERROR",
            message=str(exc),
        ) from exc
    except SessionNotFoundError as exc:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="NOT_FOUND",
            message="会话不存在或无权访问。",
        ) from exc
    except InvalidMaterialContextError as exc:
        raise ApiError(status_code=status.HTTP_400_BAD_REQUEST, code="MATERIAL_CONTEXT_INVALID", message=str(exc)) from exc

    return api_response(session.model_dump())


@router.delete("/sessions/{session_id}")
def delete_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    service: TutorSessionService = Depends(get_tutor_session_service),
) -> dict:
    try:
        deleted = service.delete_session(user=current_user, session_id=session_id)
    except SessionNotFoundError as exc:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="NOT_FOUND",
            message="会话不存在或无权访问。",
        ) from exc
    return api_response(DeleteTutorSessionResponse(session_id=deleted.id, deleted=True).model_dump())


@router.post("/sessions/{session_id}/messages")
def send_message(
    session_id: int,
    payload: SendTutorMessageRequest,
    current_user: User = Depends(get_current_user),
    service: TutorSessionService = Depends(get_tutor_session_service),
) -> dict:
    try:
        detail = service.append_message(
            user=current_user,
            session_id=session_id,
            content=payload.message,
            use_web_search=payload.use_web_search,
            deep_thinking=payload.deep_thinking,
            selected_material_ids=payload.selected_material_ids,
            attachment_ids=payload.attachment_ids,
            context_resource_id=payload.context_resource_id,
        )
    except EmptyMessageError as exc:
        raise ApiError(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="VALIDATION_ERROR",
            message=str(exc),
        ) from exc
    except SessionNotFoundError as exc:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="NOT_FOUND",
            message="会话不存在或无权访问。",
        ) from exc
    except InvalidMaterialContextError as exc:
        raise ApiError(status_code=status.HTTP_400_BAD_REQUEST, code="MATERIAL_CONTEXT_INVALID", message=str(exc)) from exc
    except InvalidResourceContextError as exc:
        raise ApiError(status_code=status.HTTP_400_BAD_REQUEST, code="RESOURCE_CONTEXT_INVALID", message=str(exc)) from exc
    except CourseAnswerGenerationError as exc:
        raise ApiError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="MODEL_PROVIDER_ERROR",
            message=str(exc),
        ) from exc

    return api_response(detail.model_dump())


@router.post("/sessions/{session_id}/messages/stream")
def stream_message(
    session_id: int,
    payload: SendTutorMessageRequest,
    current_user: User = Depends(get_current_user),
    service: TutorSessionService = Depends(get_tutor_session_service),
) -> EventSourceResponse:
    try:
        events = service.stream_message(
            user=current_user,
            session_id=session_id,
            content=payload.message,
            use_web_search=payload.use_web_search,
            deep_thinking=payload.deep_thinking,
            selected_material_ids=payload.selected_material_ids,
            attachment_ids=payload.attachment_ids,
            resource_request=payload.resource_request,
            context_resource_id=payload.context_resource_id,
        )
    except EmptyMessageError as exc:
        raise ApiError(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="VALIDATION_ERROR",
            message=str(exc),
        ) from exc
    except InvalidSessionScopeError as exc:
        raise ApiError(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="VALIDATION_ERROR",
            message=str(exc),
        ) from exc
    except SessionNotFoundError as exc:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="NOT_FOUND",
            message="会话不存在或无权访问。",
        ) from exc
    except InvalidMaterialContextError as exc:
        raise ApiError(status_code=status.HTTP_400_BAD_REQUEST, code="MATERIAL_CONTEXT_INVALID", message=str(exc)) from exc
    except InvalidResourceContextError as exc:
        raise ApiError(status_code=status.HTTP_400_BAD_REQUEST, code="RESOURCE_CONTEXT_INVALID", message=str(exc)) from exc
    except CourseAnswerGenerationError as exc:
        raise ApiError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="MODEL_PROVIDER_ERROR",
            message=str(exc),
        ) from exc

    def encode_events():
        for event in events:
            event_name = str(event.get("event") or "message")
            data = event.get("data", {})
            yield sse_event(event_name, data)

    return event_source_response(encode_events())


@router.post("/sessions/{session_id}/messages/{message_id}/resource-jobs", status_code=202)
def create_tutor_resource_job(
    session_id: int,
    message_id: int,
    payload: CreateTutorResourceJobRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    current_user: User = Depends(get_current_user),
    tutor_service: TutorSessionService = Depends(get_tutor_session_service),
    job_service: AiJobService = Depends(get_ai_job_service),
) -> dict:
    try:
        request, _linked_job_ids = tutor_service.prepare_resource_job(
            current_user,
            session_id,
            message_id,
            payload.course_id,
            legacy_request={
                "resource_types": list(payload.resource_types),
                "learning_goal": payload.learning_goal,
                "difficulty": payload.difficulty,
            },
        )
        job = job_service.create_resource_generation_job(
            current_user,
            **request,
            on_created=lambda job_id: tutor_service.link_resource_job(current_user, session_id, message_id, job_id),
            idempotency_key=idempotency_key or f"tutor-resource-{session_id}-{message_id}",
        )
    except SessionNotFoundError as exc:
        raise ApiError(status.HTTP_404_NOT_FOUND, "NOT_FOUND", str(exc)) from exc
    except InvalidMaterialContextError as exc:
        raise ApiError(status.HTTP_400_BAD_REQUEST, "RESOURCE_PROPOSAL_INVALID", str(exc)) from exc
    return api_response(job.model_dump(mode="json"))


@router.post("/sessions/{session_id}/attachments", status_code=status.HTTP_201_CREATED)
def upload_tutor_attachment(
    session_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    service: TutorAttachmentService = Depends(get_tutor_attachment_service),
) -> dict:
    try:
        service.cleanup_expired_pending(limit=20)
        content = file.file.read(4 * 1024 * 1024 + 1)
        attachment = service.upload(
            user=current_user,
            session_id=session_id,
            filename=file.filename or "image.png",
            declared_mime=file.content_type or "application/octet-stream",
            content=content,
        )
    except TutorAttachmentNotFoundError as exc:
        raise ApiError(status_code=status.HTTP_404_NOT_FOUND, code="NOT_FOUND", message=str(exc)) from exc
    except TutorAttachmentError as exc:
        raise ApiError(status_code=status.HTTP_400_BAD_REQUEST, code="IMAGE_UPLOAD_INVALID", message=str(exc)) from exc
    return api_response(attachment_to_api(attachment).model_dump())


@router.post("/sessions/{session_id}/attachments/from-material", status_code=status.HTTP_201_CREATED)
def attach_tutor_material(
    session_id: int,
    payload: AttachTutorMaterialRequest,
    current_user: User = Depends(get_current_user),
    service: TutorAttachmentService = Depends(get_tutor_attachment_service),
) -> dict:
    try:
        service.cleanup_expired_pending(limit=20)
        attachment = service.attach_material(
            user=current_user,
            session_id=session_id,
            material_id=payload.material_id,
        )
    except TutorAttachmentNotFoundError as exc:
        raise ApiError(status_code=status.HTTP_404_NOT_FOUND, code="NOT_FOUND", message=str(exc)) from exc
    except TutorAttachmentError as exc:
        raise ApiError(status_code=status.HTTP_400_BAD_REQUEST, code="IMAGE_UPLOAD_INVALID", message=str(exc)) from exc
    return api_response(attachment_to_api(attachment).model_dump())


@router.get("/attachments/{attachment_id}/content")
def get_tutor_attachment_content(
    attachment_id: int,
    current_user: User = Depends(get_current_user),
    service: TutorAttachmentService = Depends(get_tutor_attachment_service),
) -> Response:
    try:
        attachment, content = service.read(user=current_user, attachment_id=attachment_id)
    except TutorAttachmentNotFoundError as exc:
        raise ApiError(status_code=status.HTTP_404_NOT_FOUND, code="NOT_FOUND", message=str(exc)) from exc
    return Response(
        content=content,
        media_type=attachment.mime_type,
        headers={"Cache-Control": "private, max-age=300", "X-Content-Type-Options": "nosniff"},
    )


@router.delete("/attachments/{attachment_id}")
def delete_tutor_attachment(
    attachment_id: int,
    current_user: User = Depends(get_current_user),
    service: TutorAttachmentService = Depends(get_tutor_attachment_service),
) -> dict:
    try:
        attachment = service.delete(user=current_user, attachment_id=attachment_id)
    except TutorAttachmentNotFoundError as exc:
        raise ApiError(status_code=status.HTTP_404_NOT_FOUND, code="NOT_FOUND", message=str(exc)) from exc
    return api_response(attachment_to_api(attachment).model_dump())

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Header, Query, UploadFile, status

from backend.app.agents.runtime import AgentTraceRecorder
from backend.app.api.errors import ApiError, api_response
from backend.app.api.v1.deps import get_current_user
from backend.app.core.config import get_settings
from backend.app.db.session import get_db_session
from backend.app.models import User
from backend.app.providers.openai_compatible import OpenAICompatibleChatProvider
from backend.app.schemas.materials import (
    AttachCourseMaterialsRequest,
    CompareMaterialsRequest,
    ConfirmMaterialOutlineRequest,
    MaterialIngestionJobRequest,
    UpdateMaterialOutlineRequest,
)
from backend.app.services.ai_jobs import (
    AiJobConflictError,
    AiJobNotFoundError,
    AiJobService,
    AiJobValidationError,
    RqAiJobQueue,
    SqlAlchemyAiJobRepository,
)
from backend.app.services.materials import (
    CourseNotFoundError,
    MaterialNotFoundError,
    MaterialService,
    MaterialValidationError,
    SqlAlchemyMaterialRepository,
)
from backend.app.services.model_settings import ModelSettingsService, SqlAlchemyModelSettingsRepository


router = APIRouter(tags=["materials"])


def get_material_service(db=Depends(get_db_session)) -> MaterialService:
    model_service = ModelSettingsService(
        repository=SqlAlchemyModelSettingsRepository(db),
        settings=get_settings(),
        provider=OpenAICompatibleChatProvider(),
    )
    return MaterialService(
        SqlAlchemyMaterialRepository(db),
        model_service=model_service,
        trace_recorder=AgentTraceRecorder(),
    )


def get_material_job_service(db=Depends(get_db_session)) -> AiJobService:
    settings = get_settings()
    return AiJobService(SqlAlchemyAiJobRepository(db), settings=settings, queue=RqAiJobQueue(settings))


def raise_material_job_error(exc: Exception) -> None:
    if isinstance(exc, AiJobNotFoundError):
        raise ApiError(status_code=404, code="NOT_FOUND", message=str(exc)) from exc
    if isinstance(exc, AiJobValidationError):
        raise ApiError(status_code=400, code="VALIDATION_ERROR", message=str(exc)) from exc
    if isinstance(exc, AiJobConflictError):
        raise ApiError(status_code=409, code="CONFLICT", message=str(exc)) from exc
    raise exc


@router.post("/materials/upload")
async def upload_material(
    file: UploadFile = File(...),
    course_id: int | None = Form(default=None),
    current_user: User = Depends(get_current_user),
    service: MaterialService = Depends(get_material_service),
    job_service: AiJobService = Depends(get_material_job_service),
) -> dict:
    content = await file.read()
    try:
        result = service.upload_material(
            user=current_user,
            filename=file.filename or "",
            content_type=file.content_type or "application/octet-stream",
            content=content,
            course_id=course_id,
            defer_ingestion=True,
        )
        if result.parse_status == "pending":
            job = job_service.create_material_ingestion_job(
                current_user,
                material_id=result.material_id,
                idempotency_key=f"material-upload-{result.material_id}",
            )
            result.ingestion_job_id = job.job_id
    except MaterialValidationError as exc:
        raise ApiError(status_code=status.HTTP_400_BAD_REQUEST, code="VALIDATION_ERROR", message=str(exc)) from exc
    except CourseNotFoundError as exc:
        raise ApiError(status_code=status.HTTP_404_NOT_FOUND, code="NOT_FOUND", message=str(exc)) from exc
    except Exception as exc:
        raise_material_job_error(exc)

    return api_response(result.model_dump())


@router.post("/materials/{material_id}/ingestion-jobs", status_code=202)
def create_material_ingestion_job(
    material_id: int,
    payload: MaterialIngestionJobRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    current_user: User = Depends(get_current_user),
    service: AiJobService = Depends(get_material_job_service),
) -> dict:
    try:
        result = service.create_material_ingestion_job(
            current_user,
            material_id=material_id,
            force=payload.force,
            idempotency_key=idempotency_key,
        )
    except Exception as exc:
        raise_material_job_error(exc)
        raise
    return api_response(result.model_dump(mode="json"))


@router.get("/materials/{material_id}/outline")
def get_material_outline(
    material_id: int,
    current_user: User = Depends(get_current_user),
    service: MaterialService = Depends(get_material_service),
) -> dict:
    try:
        result = service.get_outline(current_user, material_id)
    except MaterialNotFoundError as exc:
        raise ApiError(status_code=404, code="NOT_FOUND", message=str(exc)) from exc
    return api_response(result.model_dump())


@router.patch("/materials/{material_id}/outline")
def update_material_outline(
    material_id: int,
    payload: UpdateMaterialOutlineRequest,
    current_user: User = Depends(get_current_user),
    service: MaterialService = Depends(get_material_service),
) -> dict:
    try:
        result = service.update_outline(current_user, material_id, payload)
    except MaterialNotFoundError as exc:
        raise ApiError(status_code=404, code="NOT_FOUND", message=str(exc)) from exc
    except MaterialValidationError as exc:
        code = "CONFLICT" if "刷新" in str(exc) or "版本" in str(exc) else "VALIDATION_ERROR"
        http_status = 409 if code == "CONFLICT" else 400
        raise ApiError(status_code=http_status, code=code, message=str(exc)) from exc
    return api_response(result.model_dump())


@router.post("/materials/{material_id}/outline/confirm")
def confirm_material_outline(
    material_id: int,
    payload: ConfirmMaterialOutlineRequest,
    current_user: User = Depends(get_current_user),
    service: MaterialService = Depends(get_material_service),
) -> dict:
    try:
        result = service.confirm_outline(current_user, material_id, payload.version)
    except MaterialNotFoundError as exc:
        raise ApiError(status_code=404, code="NOT_FOUND", message=str(exc)) from exc
    except MaterialValidationError as exc:
        code = "CONFLICT" if "版本" in str(exc) else "VALIDATION_ERROR"
        raise ApiError(status_code=409 if code == "CONFLICT" else 400, code=code, message=str(exc)) from exc
    return api_response(result.model_dump())


@router.get("/materials")
def list_materials(
    course_id: int | None = Query(default=None),
    unassigned: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
    service: MaterialService = Depends(get_material_service),
) -> dict:
    try:
        result = service.list_materials(current_user, course_id=course_id, unassigned=unassigned)
    except CourseNotFoundError as exc:
        raise ApiError(status_code=status.HTTP_404_NOT_FOUND, code="NOT_FOUND", message=str(exc)) from exc

    return api_response([item.model_dump() for item in result])


@router.post("/materials/compare")
def compare_materials(
    payload: CompareMaterialsRequest,
    current_user: User = Depends(get_current_user),
    service: MaterialService = Depends(get_material_service),
) -> dict:
    try:
        result = service.compare_materials(current_user, course_id=payload.course_id, material_ids=payload.material_ids)
    except MaterialValidationError as exc:
        raise ApiError(status_code=status.HTTP_400_BAD_REQUEST, code="VALIDATION_ERROR", message=str(exc)) from exc
    except (CourseNotFoundError, MaterialNotFoundError) as exc:
        raise ApiError(status_code=status.HTTP_404_NOT_FOUND, code="NOT_FOUND", message=str(exc)) from exc

    return api_response(result.model_dump())


@router.get("/materials/comparisons/latest")
def get_latest_material_comparison(
    course_id: int = Query(...),
    current_user: User = Depends(get_current_user),
    service: MaterialService = Depends(get_material_service),
) -> dict:
    try:
        result = service.get_latest_comparison(current_user, course_id)
    except CourseNotFoundError as exc:
        raise ApiError(status_code=status.HTTP_404_NOT_FOUND, code="NOT_FOUND", message=str(exc)) from exc
    return api_response(result.model_dump() if result is not None else None)


@router.get("/materials/comparisons/{comparison_id}")
def get_material_comparison(
    comparison_id: int,
    current_user: User = Depends(get_current_user),
    service: MaterialService = Depends(get_material_service),
) -> dict:
    try:
        result = service.get_comparison(current_user, comparison_id)
    except MaterialNotFoundError as exc:
        raise ApiError(status_code=status.HTTP_404_NOT_FOUND, code="NOT_FOUND", message=str(exc)) from exc
    return api_response(result.model_dump())


@router.get("/materials/{material_id}")
def get_material(
    material_id: int,
    current_user: User = Depends(get_current_user),
    service: MaterialService = Depends(get_material_service),
) -> dict:
    try:
        result = service.get_material(current_user, material_id)
    except MaterialNotFoundError as exc:
        raise ApiError(status_code=status.HTTP_404_NOT_FOUND, code="NOT_FOUND", message=str(exc)) from exc

    return api_response(result.model_dump())


@router.get("/materials/{material_id}/progress")
def get_material_progress(
    material_id: int,
    current_user: User = Depends(get_current_user),
    service: MaterialService = Depends(get_material_service),
) -> dict:
    try:
        result = service.get_progress(current_user, material_id)
    except MaterialNotFoundError as exc:
        raise ApiError(status_code=status.HTTP_404_NOT_FOUND, code="NOT_FOUND", message=str(exc)) from exc

    return api_response(result.model_dump())


@router.post("/courses/{course_id}/materials")
def attach_course_materials(
    course_id: int,
    payload: AttachCourseMaterialsRequest,
    current_user: User = Depends(get_current_user),
    service: MaterialService = Depends(get_material_service),
) -> dict:
    try:
        result = service.attach_materials_to_course(current_user, course_id=course_id, material_ids=payload.material_ids)
    except (CourseNotFoundError, MaterialNotFoundError) as exc:
        raise ApiError(status_code=status.HTTP_404_NOT_FOUND, code="NOT_FOUND", message=str(exc)) from exc

    return api_response(result.model_dump())

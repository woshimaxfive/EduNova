from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status

from backend.app.api.errors import ApiError, api_response
from backend.app.api.v1.deps import get_current_user
from backend.app.db.session import get_db_session
from backend.app.models import User
from backend.app.schemas.materials import AttachCourseMaterialsRequest
from backend.app.services.materials import (
    CourseNotFoundError,
    MaterialNotFoundError,
    MaterialService,
    MaterialValidationError,
    SqlAlchemyMaterialRepository,
)


router = APIRouter(tags=["materials"])


def get_material_service(db=Depends(get_db_session)) -> MaterialService:
    return MaterialService(SqlAlchemyMaterialRepository(db))


@router.post("/materials/upload")
async def upload_material(
    file: UploadFile = File(...),
    course_id: int | None = Form(default=None),
    current_user: User = Depends(get_current_user),
    service: MaterialService = Depends(get_material_service),
) -> dict:
    content = await file.read()
    try:
        result = service.upload_material(
            user=current_user,
            filename=file.filename or "",
            content_type=file.content_type or "application/octet-stream",
            content=content,
            course_id=course_id,
        )
    except MaterialValidationError as exc:
        raise ApiError(status_code=status.HTTP_400_BAD_REQUEST, code="VALIDATION_ERROR", message=str(exc)) from exc
    except CourseNotFoundError as exc:
        raise ApiError(status_code=status.HTTP_404_NOT_FOUND, code="NOT_FOUND", message=str(exc)) from exc

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

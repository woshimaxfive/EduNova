from __future__ import annotations

from fastapi import APIRouter, Depends, status

from backend.app.api.errors import ApiError, api_response
from backend.app.api.v1.deps import get_current_user
from backend.app.db.session import get_db_session
from backend.app.models import User
from backend.app.schemas.rag import RagSearchRequest
from backend.app.services.rag import RagCourseNotFoundError, RagService, RagValidationError, SqlAlchemyRagRepository


router = APIRouter(prefix="/rag", tags=["rag"])


def get_rag_service(db=Depends(get_db_session)) -> RagService:
    return RagService(SqlAlchemyRagRepository(db))


@router.post("/search")
def search_course_knowledge(
    payload: RagSearchRequest,
    current_user: User = Depends(get_current_user),
    service: RagService = Depends(get_rag_service),
) -> dict:
    try:
        result = service.search(
            current_user,
            course_id=payload.course_id,
            query=payload.query,
            top_k=payload.top_k,
        )
    except RagCourseNotFoundError as exc:
        raise ApiError(status.HTTP_404_NOT_FOUND, "NOT_FOUND", str(exc)) from exc
    except RagValidationError as exc:
        raise ApiError(status.HTTP_400_BAD_REQUEST, "VALIDATION_ERROR", str(exc)) from exc

    return api_response(result.model_dump())

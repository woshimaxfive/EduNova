from __future__ import annotations

from fastapi import Depends, status

from backend.app.api.contracts import TypedAPIRouter as APIRouter
from backend.app.api.errors import ApiError, api_response
from backend.app.api.v1.deps import get_current_user
from backend.app.core.config import get_settings
from backend.app.db.session import get_db_session
from backend.app.models import User
from backend.app.providers.openai_compatible import OpenAICompatibleChatProvider
from backend.app.schemas.rag import RagSearchRequest
from backend.app.services.embeddings import EmbeddingService
from backend.app.services.model_settings import ModelSettingsService, SqlAlchemyModelSettingsRepository
from backend.app.services.rag import RagCourseNotFoundError, RagService, RagValidationError, SqlAlchemyRagRepository


router = APIRouter(prefix="/rag", tags=["rag"])


def get_rag_service(db=Depends(get_db_session)) -> RagService:
    model_settings_service = ModelSettingsService(
        repository=SqlAlchemyModelSettingsRepository(db),
        settings=get_settings(),
        provider=OpenAICompatibleChatProvider(),
    )
    return RagService(
        SqlAlchemyRagRepository(db),
        embedding_service=EmbeddingService(model_settings_service),
        rerank_service=model_settings_service,
    )


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

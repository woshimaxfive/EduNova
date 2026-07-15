from __future__ import annotations

from fastapi import Depends, Query

from backend.app.api.contracts import TypedAPIRouter as APIRouter
from backend.app.api.errors import ApiError, api_response
from backend.app.api.v1.courses import get_course_service
from backend.app.api.v1.deps import get_current_user
from backend.app.db.session import get_db_session
from backend.app.models import User
from backend.app.services.courses import CourseService
from backend.app.services.learning_actions import LearningActionCourseNotFoundError, LearningNextActionService


router = APIRouter(prefix="/learning", tags=["learning"])


def get_learning_next_action_service(
    db=Depends(get_db_session),
    course_service: CourseService = Depends(get_course_service),
) -> LearningNextActionService:
    return LearningNextActionService(db, course_service)


@router.get("/next-action")
def get_learning_next_action(
    course_id: int | None = Query(default=None, gt=0),
    current_user: User = Depends(get_current_user),
    service: LearningNextActionService = Depends(get_learning_next_action_service),
) -> dict:
    try:
        return api_response(service.get_next_action(current_user, course_id).model_dump())
    except LearningActionCourseNotFoundError as exc:
        raise ApiError(404, "NOT_FOUND", str(exc)) from exc


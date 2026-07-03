from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.app.api.errors import api_response
from backend.app.api.v1.deps import get_current_user
from backend.app.db.session import get_db_session
from backend.app.models import User
from backend.app.services.dashboard import DashboardService, SqlAlchemyDashboardRepository


router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def get_dashboard_service(db=Depends(get_db_session)) -> DashboardService:
    return DashboardService(SqlAlchemyDashboardRepository(db))


@router.get("/summary")
def summary(
    current_user: User = Depends(get_current_user),
    service: DashboardService = Depends(get_dashboard_service),
) -> dict:
    return api_response(service.build_summary(current_user).model_dump())

from __future__ import annotations

from fastapi import APIRouter

from backend.app.api.v1.auth import router as auth_router
from backend.app.api.v1.courses import router as courses_router
from backend.app.api.v1.dashboard import router as dashboard_router
from backend.app.api.v1.materials import router as materials_router
from backend.app.api.v1.tutor import router as tutor_router


api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(courses_router)
api_router.include_router(dashboard_router)
api_router.include_router(materials_router)
api_router.include_router(tutor_router)

from __future__ import annotations

from fastapi import APIRouter

from backend.app.api.v1.agents import router as agents_router
from backend.app.api.v1.ai_jobs import router as ai_jobs_router
from backend.app.api.v1.auth import router as auth_router
from backend.app.api.v1.courses import router as courses_router
from backend.app.api.v1.dashboard import router as dashboard_router
from backend.app.api.v1.exports import router as exports_router
from backend.app.api.v1.learning import router as learning_router
from backend.app.api.v1.materials import router as materials_router
from backend.app.api.v1.paths import router as paths_router
from backend.app.api.v1.practice import router as practice_router
from backend.app.api.v1.profiles import router as profiles_router
from backend.app.api.v1.rag import router as rag_router
from backend.app.api.v1.reports import router as reports_router
from backend.app.api.v1.resources import router as resources_router
from backend.app.api.v1.settings import router as settings_router
from backend.app.api.v1.speech import router as speech_router
from backend.app.api.v1.tutor import router as tutor_router


api_router = APIRouter()
api_router.include_router(agents_router)
api_router.include_router(ai_jobs_router)
api_router.include_router(auth_router)
api_router.include_router(courses_router)
api_router.include_router(dashboard_router)
api_router.include_router(exports_router)
api_router.include_router(learning_router)
api_router.include_router(materials_router)
api_router.include_router(paths_router)
api_router.include_router(practice_router)
api_router.include_router(profiles_router)
api_router.include_router(rag_router)
api_router.include_router(reports_router)
api_router.include_router(resources_router)
api_router.include_router(settings_router)
api_router.include_router(speech_router)
api_router.include_router(tutor_router)

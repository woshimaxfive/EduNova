from __future__ import annotations

from fastapi import Depends, File, UploadFile
from starlette.concurrency import run_in_threadpool

from backend.app.api.contracts import TypedAPIRouter as APIRouter
from backend.app.api.contracts import ApiErrorEnvelope
from backend.app.api.errors import ApiError, api_response
from backend.app.api.v1.deps import get_current_user
from backend.app.core.config import get_settings
from backend.app.models import User
from backend.app.services.speech import SpeechService, SpeechServiceError


router = APIRouter(prefix="/speech", tags=["speech"])


def get_speech_service() -> SpeechService:
    return SpeechService(get_settings())


@router.post("/transcriptions")
async def transcribe_speech(
    file: UploadFile = File(...),
    _current_user: User = Depends(get_current_user),
    service: SpeechService = Depends(get_speech_service),
) -> dict:
    if file.content_type not in {"application/octet-stream", "audio/pcm", "audio/L16"}:
        raise ApiError(400, "INVALID_SPEECH_AUDIO", "仅支持16k单声道PCM录音。")
    audio = await file.read(60 * 16000 * 2 + 1)
    try:
        result = await run_in_threadpool(service.transcribe, audio)
    except SpeechServiceError as exc:
        raise ApiError(exc.status_code, exc.code, str(exc)) from exc
    return api_response(result.model_dump())


@router.post("/synthesis", deprecated=True, status_code=410, response_model=ApiErrorEnvelope)
def retired_synthesis(_current_user: User = Depends(get_current_user)) -> None:
    raise ApiError(410, "SPEECH_SYNTHESIS_RETIRED", "朗读已改为浏览器本地声音，请更新前端页面。")

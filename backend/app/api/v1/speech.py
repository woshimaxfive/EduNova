from __future__ import annotations

from fastapi import Depends, File, Response, UploadFile

from backend.app.api.contracts import TypedAPIRouter as APIRouter
from backend.app.api.errors import ApiError, api_response
from backend.app.api.v1.deps import get_current_user
from backend.app.core.config import get_settings
from backend.app.models import User
from backend.app.schemas.speech import SpeechSynthesisRequest
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
    audio = await file.read()
    try:
        result = service.transcribe(audio)
    except SpeechServiceError as exc:
        raise ApiError(exc.status_code, exc.code, str(exc)) from exc
    return api_response(result.model_dump())


@router.post(
    "/synthesis",
    response_class=Response,
    response_model=None,
    responses={200: {"content": {"audio/mpeg": {}}}},
)
def synthesize_speech(
    payload: SpeechSynthesisRequest,
    _current_user: User = Depends(get_current_user),
    service: SpeechService = Depends(get_speech_service),
) -> Response:
    try:
        audio = service.synthesize(payload.text)
    except SpeechServiceError as exc:
        raise ApiError(exc.status_code, exc.code, str(exc)) from exc
    return Response(
        content=audio,
        media_type="audio/mpeg",
        headers={"Cache-Control": "private, no-store", "X-Speech-Provider": "xfyun"},
    )

from __future__ import annotations

from backend.app.core.config import Settings
from backend.app.providers.local_speech import LocalSpeechError, LocalSpeechProvider
from backend.app.schemas.speech import SpeechTranscriptionResult


class SpeechServiceError(RuntimeError):
    def __init__(self, message: str, *, code: str, status_code: int = 502) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


class SpeechService:
    def __init__(self, settings: Settings, provider: LocalSpeechProvider | None = None) -> None:
        self.settings = settings
        self.provider = provider or LocalSpeechProvider(settings.local_speech_url, settings.speech_request_timeout_seconds)

    def transcribe(self, audio: bytes) -> SpeechTranscriptionResult:
        max_seconds = min(self.settings.speech_max_audio_seconds, 60)
        if not audio or len(audio) > max_seconds * 16000 * 2 or len(audio) % 2:
            raise SpeechServiceError(f"录音必须是最长 {max_seconds} 秒的16k单声道PCM。",
                                     code="INVALID_SPEECH_AUDIO", status_code=400)
        try:
            transcript = self.provider.transcribe_pcm(audio)
        except LocalSpeechError as exc:
            raise SpeechServiceError(str(exc), code=exc.code, status_code=exc.status_code) from exc
        return SpeechTranscriptionResult(transcript=transcript, duration_ms=round(len(audio) / 32))

    def synthesize(self, text: str) -> bytes:
        normalized = " ".join(text.split()).strip()
        if not normalized or len(normalized) > 180:
            raise SpeechServiceError("每段朗读需为1至180字，请分段朗读。", code="INVALID_SPEECH_TEXT", status_code=400)
        try:
            return self.provider.synthesize_wav(normalized)
        except LocalSpeechError as exc:
            raise SpeechServiceError(str(exc), code=exc.code, status_code=exc.status_code) from exc

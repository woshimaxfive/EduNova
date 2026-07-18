from __future__ import annotations

import re

from backend.app.core.config import Settings
from backend.app.providers.xfyun_speech import XfyunSpeechConfig, XfyunSpeechError, XfyunSpeechProvider
from backend.app.schemas.speech import SpeechTranscriptionResult


class SpeechServiceError(RuntimeError):
    def __init__(self, message: str, *, code: str, status_code: int = 502) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


class SpeechService:
    def __init__(self, settings: Settings, provider: XfyunSpeechProvider | None = None) -> None:
        self.settings = settings
        self.provider = provider or XfyunSpeechProvider()

    def transcribe(self, audio: bytes) -> SpeechTranscriptionResult:
        if self.settings.system_speech_provider.strip().lower() != "xfyun":
            raise SpeechServiceError("服务器未启用讯飞语音识别。", code="SPEECH_NOT_CONFIGURED", status_code=503)
        max_bytes = self.settings.speech_max_audio_seconds * 16000 * 2
        if not audio or len(audio) > max_bytes or len(audio) % 2:
            raise SpeechServiceError(
                f"录音必须是最长 {self.settings.speech_max_audio_seconds} 秒的16k单声道PCM。",
                code="INVALID_SPEECH_AUDIO",
                status_code=400,
            )
        try:
            transcript = self.provider.transcribe_pcm(
                self._config(),
                audio,
                timeout_seconds=self.settings.speech_request_timeout_seconds,
            )
        except XfyunSpeechError as exc:
            raise self._map_error(exc) from exc
        return SpeechTranscriptionResult(
            transcript=transcript,
            duration_ms=round(len(audio) / 32),
        )

    def synthesize(self, text: str) -> bytes:
        if self.settings.system_speech_provider.strip().lower() != "xfyun":
            raise SpeechServiceError("服务器未启用讯飞语音合成。", code="SPEECH_NOT_CONFIGURED", status_code=503)
        chunks = self._split_text(text)
        if not chunks:
            raise SpeechServiceError("朗读文本为空。", code="INVALID_SPEECH_TEXT", status_code=400)
        audio_parts: list[bytes] = []
        try:
            for chunk in chunks:
                audio_parts.append(self.provider.synthesize_mp3(
                    self._config(),
                    chunk,
                    timeout_seconds=self.settings.speech_request_timeout_seconds,
                ))
        except XfyunSpeechError as exc:
            raise self._map_error(exc) from exc
        return b"".join(audio_parts)

    def _config(self) -> XfyunSpeechConfig:
        return XfyunSpeechConfig(
            app_id=self.settings.system_speech_app_id,
            api_key=self.settings.system_speech_api_key,
            api_secret=self.settings.system_speech_api_secret,
            asr_url=self.settings.system_speech_asr_url,
            tts_url=self.settings.system_speech_tts_url,
            tts_voice=self.settings.system_speech_tts_voice,
            tts_speed=self.settings.system_speech_tts_speed,
        )

    @staticmethod
    def _split_text(text: str) -> list[str]:
        normalized = " ".join(text.split()).strip()
        if not normalized:
            return []
        pieces = [item.strip() for item in re.split(r"(?<=[。！？；.!?;])", normalized) if item.strip()]
        chunks: list[str] = []
        current = ""
        for piece in pieces or [normalized]:
            if len((current + piece).encode("utf-8")) < 7600:
                current += piece
                continue
            if current:
                chunks.append(current)
            while len(piece.encode("utf-8")) >= 7600:
                boundary = min(2400, len(piece))
                while boundary > 1 and len(piece[:boundary].encode("utf-8")) >= 7600:
                    boundary -= 1
                chunks.append(piece[:boundary])
                piece = piece[boundary:]
            current = piece
        if current:
            chunks.append(current)
        return chunks

    @staticmethod
    def _map_error(exc: XfyunSpeechError) -> SpeechServiceError:
        status_code = 503 if exc.code in {"not_configured", "authentication_failed", "rate_limited"} else 502
        if exc.code in {"invalid_audio", "invalid_text"}:
            status_code = 400
        return SpeechServiceError(str(exc), code=f"SPEECH_{exc.code.upper()}", status_code=status_code)

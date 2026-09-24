from __future__ import annotations

from pydantic import BaseModel, Field


class SpeechTranscriptionResult(BaseModel):
    transcript: str
    provider: str = "sherpa_onnx"
    duration_ms: int = Field(ge=0)

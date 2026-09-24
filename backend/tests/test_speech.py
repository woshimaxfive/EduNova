from unittest.mock import Mock

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.app.api.v1.deps import get_current_user
from backend.app.api.v1.speech import get_speech_service
from backend.app.core.config import Settings
from backend.app.main import create_app
from backend.app.models import User
from backend.app.providers.local_speech import LocalSpeechError, LocalSpeechProvider
from backend.app.services.speech import SpeechService, SpeechServiceError


def test_speech_uses_local_endpoint_without_keys():
    def handler(request):
        assert request.url.host == "speech"
        assert "authorization" not in request.headers
        assert request.url.path == "/transcriptions"
        assert request.content == b"\0\0" * 100
        return httpx.Response(200, json={"transcript": "数据结构"})
    provider = LocalSpeechProvider("http://speech:8091", 10, httpx.Client(transport=httpx.MockTransport(handler)))
    service = SpeechService(Settings(_env_file=None), provider)
    result = service.transcribe(b"\0\0" * 100)
    assert result.transcript == "数据结构" and result.provider == "sherpa_onnx"


@pytest.mark.parametrize("audio", [b"", b"x", b"\0\0" * 16001], ids=["empty", "odd", "too_long"])
def test_invalid_audio_never_reaches_provider(audio):
    provider = Mock()
    service = SpeechService(Settings(_env_file=None, speech_max_audio_seconds=1), provider)
    with pytest.raises(SpeechServiceError):
        service.transcribe(audio)
    provider.transcribe_pcm.assert_not_called()


@pytest.mark.parametrize("status,code", [(429, "SPEECH_BUSY"), (422, "SPEECH_EMPTY_TRANSCRIPT"), (503, "SPEECH_UNAVAILABLE")])
def test_failure_never_falls_back_to_cloud(status, code):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(status)
    provider = LocalSpeechProvider("http://speech:8091", 10, httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(LocalSpeechError) as caught:
        provider.transcribe_pcm(b"\0\0")
    assert caught.value.code == code and len(calls) == 1


def test_timeout_and_invalid_transcript():
    def timeout(request):
        raise httpx.ReadTimeout("synthetic", request=request)
    provider = LocalSpeechProvider("http://speech:8091", 1, httpx.Client(transport=httpx.MockTransport(timeout)))
    with pytest.raises(LocalSpeechError) as caught:
        provider.transcribe_pcm(b"\0\0")
    assert caught.value.status_code == 504
    provider.client = httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, content=b"bad")))
    with pytest.raises(LocalSpeechError, match="有效识别"):
        provider.transcribe_pcm(b"\0\0")


def test_speech_api_auth_limits_and_retired_synthesis():
    app = create_app()
    provider = Mock()
    provider.transcribe_pcm.return_value = "数据结构"
    app.dependency_overrides[get_speech_service] = lambda: SpeechService(Settings(_env_file=None), provider)
    client = TestClient(app)
    assert client.post("/api/v1/speech/synthesis", json={"text": "测试"}).status_code == 401
    app.dependency_overrides[get_current_user] = lambda: User(id=1, account="speech-test", hashed_password="x")
    response = client.post("/api/v1/speech/transcriptions", files={"file": ("a.pcm", b"\0\0" * 100, "audio/pcm")})
    assert response.status_code == 200 and response.json()["data"]["provider"] == "sherpa_onnx"
    response = client.post("/api/v1/speech/synthesis", json={"text": "测试"})
    assert response.status_code == 410
    provider.synthesize_wav.assert_not_called()
    assert client.post("/api/v1/speech/transcriptions", files={"file": ("a", b"x" * 1920001, "audio/pcm")}).status_code == 400


def test_sidecar_busy_slot_released_after_failure():
    from backend.app.speech_server import SLOT, guarded
    from fastapi import HTTPException

    SLOT.acquire()
    try:
        with pytest.raises(HTTPException) as caught:
            guarded(lambda: None)
        assert caught.value.status_code == 429
    finally:
        SLOT.release()
    with pytest.raises(ValueError):
        guarded(lambda: (_ for _ in ()).throw(ValueError()))
    assert guarded(lambda: "ok") == "ok"

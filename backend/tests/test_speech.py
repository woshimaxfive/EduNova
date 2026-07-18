from __future__ import annotations

import base64
import json

import pytest
from fastapi.testclient import TestClient

from backend.app.api.v1.deps import get_current_user
from backend.app.api.v1.speech import get_speech_service
from backend.app.core.config import Settings
from backend.app.main import create_app
from backend.app.models import User
from backend.app.providers.xfyun_speech import XfyunSpeechConfig, XfyunSpeechError, XfyunSpeechProvider
from backend.app.schemas.speech import SpeechTranscriptionResult
from backend.app.services.speech import SpeechService, SpeechServiceError


def config() -> XfyunSpeechConfig:
    return XfyunSpeechConfig(
        app_id="test-app",
        api_key="test-key",
        api_secret="test-secret",
        asr_url="wss://iat-api.xfyun.cn/v2/iat",
        tts_url="wss://tts-api.xfyun.cn/v2/tts",
        tts_voice="xiaoyan",
    )


class FakeWebSocket:
    def __init__(self, responses: list[dict]) -> None:
        self.responses = [json.dumps(item, ensure_ascii=False) for item in responses]
        self.sent: list[dict] = []

    def __enter__(self) -> "FakeWebSocket":
        return self

    def __exit__(self, *_args) -> None:
        return None

    def send(self, raw: str) -> None:
        self.sent.append(json.loads(raw))

    def recv(self, *, timeout: float) -> str:
        assert timeout > 0
        return self.responses.pop(0)


def test_xfyun_asr_sends_pcm_frames_and_applies_dynamic_replacement(monkeypatch: pytest.MonkeyPatch) -> None:
    socket = FakeWebSocket([
        {"code": 0, "data": {"status": 1, "result": {"sn": 0, "ws": [{"cw": [{"w": "数据"}]}]}}},
        {"code": 0, "data": {"status": 1, "result": {"sn": 1, "ws": [{"cw": [{"w": "结够"}]}]}}},
        {"code": 0, "data": {"status": 2, "result": {"sn": 2, "pgs": "rpl", "rg": [1, 1], "ws": [{"cw": [{"w": "结构"}]}]}}},
    ])
    monkeypatch.setattr("backend.app.providers.xfyun_speech.connect", lambda *_args, **_kwargs: socket)

    result = XfyunSpeechProvider().transcribe_pcm(
        config(),
        b"\x00\x00" * 1000,
        timeout_seconds=3,
        frame_interval_seconds=0,
    )

    assert result == "数据结构"
    assert socket.sent[0]["common"] == {"app_id": "test-app"}
    assert socket.sent[0]["business"]["dwa"] == "wpgs"
    assert socket.sent[0]["data"]["status"] == 0
    assert socket.sent[-1]["data"]["status"] == 2


def test_xfyun_tts_requests_mp3_and_combines_audio(monkeypatch: pytest.MonkeyPatch) -> None:
    socket = FakeWebSocket([
        {"code": 0, "data": {"status": 1, "audio": base64.b64encode(b"part-1").decode()}},
        {"code": 0, "data": {"status": 2, "audio": base64.b64encode(b"part-2").decode()}},
    ])
    monkeypatch.setattr("backend.app.providers.xfyun_speech.connect", lambda *_args, **_kwargs: socket)

    result = XfyunSpeechProvider().synthesize_mp3(config(), "你好，EduNova。", timeout_seconds=3)

    assert result == b"part-1part-2"
    assert socket.sent[0]["business"]["aue"] == "lame"
    assert socket.sent[0]["business"]["vcn"] == "xiaoyan"
    assert base64.b64decode(socket.sent[0]["data"]["text"]).decode() == "你好，EduNova。"


def test_speech_service_rejects_unconfigured_and_oversized_audio() -> None:
    service = SpeechService(Settings(system_speech_provider=""))
    with pytest.raises(SpeechServiceError, match="未启用"):
        service.transcribe(b"\x00\x00" * 100)

    service = SpeechService(Settings(
        system_speech_provider="xfyun",
        system_speech_app_id="app",
        system_speech_api_key="key",
        system_speech_api_secret="secret",
        speech_max_audio_seconds=1,
    ))
    with pytest.raises(SpeechServiceError, match="最长 1 秒"):
        service.transcribe(b"\x00\x00" * 16001)


def test_speech_service_splits_long_tts_without_template_fallback() -> None:
    calls: list[str] = []

    class Provider:
        def synthesize_mp3(self, _config, text: str, *, timeout_seconds: float) -> bytes:
            assert timeout_seconds > 0
            calls.append(text)
            return b"mp3"

    service = SpeechService(Settings(
        system_speech_provider="xfyun",
        system_speech_app_id="app",
        system_speech_api_key="key",
        system_speech_api_secret="secret",
    ), provider=Provider())  # type: ignore[arg-type]

    audio = service.synthesize("这是第一句。" * 700)

    assert len(calls) > 1
    assert all(len(item.encode("utf-8")) < 8000 for item in calls)
    assert audio == b"mp3" * len(calls)


def test_provider_rejects_missing_credentials_without_network() -> None:
    with pytest.raises(XfyunSpeechError, match="凭证不完整"):
        XfyunSpeechProvider().synthesize_mp3(
            XfyunSpeechConfig("", "", "", "wss://example/asr", "wss://example/tts"),
            "测试",
            timeout_seconds=3,
        )


def test_authenticated_speech_api_returns_transcript_and_private_audio() -> None:
    class StubService:
        def transcribe(self, audio: bytes) -> SpeechTranscriptionResult:
            assert audio == b"\x00\x00" * 100
            return SpeechTranscriptionResult(transcript="数据结构", duration_ms=6)

        def synthesize(self, text: str) -> bytes:
            assert text == "朗读这段回答"
            return b"fake-mp3"

    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: User(
        id=1,
        account="speech-test",
        hashed_password="x",
        display_name="语音测试",
    )
    app.dependency_overrides[get_speech_service] = lambda: StubService()
    client = TestClient(app)

    transcript = client.post(
        "/api/v1/speech/transcriptions",
        files={"file": ("speech.pcm", b"\x00\x00" * 100, "application/octet-stream")},
    )
    assert transcript.status_code == 200
    assert transcript.json()["data"]["transcript"] == "数据结构"

    audio = client.post("/api/v1/speech/synthesis", json={"text": "朗读这段回答"})
    assert audio.status_code == 200
    assert audio.content == b"fake-mp3"
    assert audio.headers["content-type"] == "audio/mpeg"
    assert audio.headers["cache-control"] == "private, no-store"

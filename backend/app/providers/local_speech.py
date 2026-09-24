from __future__ import annotations

import httpx


class LocalSpeechError(RuntimeError):
    def __init__(self, message: str, code: str, status_code: int):
        super().__init__(message)
        self.code = code
        self.status_code = status_code


class LocalSpeechProvider:
    def __init__(self, endpoint: str, timeout: float, client: httpx.Client | None = None):
        self.endpoint = endpoint.rstrip("/")
        self.timeout = timeout
        self.client = client

    def _request(self, path: str, **kwargs) -> httpx.Response:
        try:
            if self.client:
                response = self.client.post(self.endpoint + path, timeout=self.timeout, **kwargs)
            else:
                with httpx.Client(timeout=self.timeout, trust_env=False, follow_redirects=False) as client:
                    response = client.post(self.endpoint + path, **kwargs)
            if response.status_code == 429:
                raise LocalSpeechError("本地语音正在处理其他请求，请稍后重试。", "SPEECH_BUSY", 429)
            if response.status_code == 422 and path == "/transcriptions":
                raise LocalSpeechError("没有识别到有效语音，请重试。", "SPEECH_EMPTY_TRANSCRIPT", 422)
            response.raise_for_status()
            return response
        except httpx.TimeoutException as exc:
            raise LocalSpeechError("本地语音处理超时，请缩短内容后重试。", "SPEECH_TIMEOUT", 504) from exc
        except httpx.HTTPError as exc:
            raise LocalSpeechError("本地语音服务不可用，请检查服务是否启动。", "SPEECH_UNAVAILABLE", 503) from exc

    def transcribe_pcm(self, audio: bytes) -> str:
        response = self._request("/transcriptions", content=audio, headers={"Content-Type": "audio/pcm"})
        try:
            text = response.json()["transcript"]
            if not isinstance(text, str) or not text.strip():
                raise ValueError("empty transcript")
            return text.strip()
        except (KeyError, TypeError, ValueError) as exc:
            raise LocalSpeechError("本地语音未返回有效识别结果。", "SPEECH_EMPTY_TRANSCRIPT", 422) from exc

from __future__ import annotations

import base64
from dataclasses import dataclass
import json
import time

from websockets.exceptions import WebSocketException
from websockets.sync.client import connect

from backend.app.providers.xfyun_auth import XfyunAuthError, build_xfyun_signed_url


class XfyunSpeechError(RuntimeError):
    def __init__(self, message: str, *, code: str, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


@dataclass(frozen=True)
class XfyunSpeechConfig:
    app_id: str
    api_key: str
    api_secret: str
    asr_url: str
    tts_url: str
    tts_voice: str = "x4_yezi"
    tts_speed: int = 50


class XfyunSpeechProvider:
    def transcribe_pcm(
        self,
        config: XfyunSpeechConfig,
        audio: bytes,
        *,
        timeout_seconds: float,
        frame_interval_seconds: float = 0.04,
    ) -> str:
        self._require_config(config)
        if not audio or len(audio) % 2:
            raise XfyunSpeechError("录音数据无效。", code="invalid_audio")
        signed_url = self._signed_url(config.asr_url, config)
        segments: dict[int, str] = {}
        try:
            with connect(signed_url, open_timeout=timeout_seconds, close_timeout=3) as websocket:
                chunks = [audio[index:index + 1280] for index in range(0, len(audio), 1280)]
                for index, chunk in enumerate(chunks):
                    status = 0 if index == 0 else 1
                    payload: dict[str, object] = {
                        "data": {
                            "status": status,
                            "format": "audio/L16;rate=16000",
                            "encoding": "raw",
                            "audio": base64.b64encode(chunk).decode("ascii"),
                        }
                    }
                    if status == 0:
                        payload["common"] = {"app_id": config.app_id}
                        payload["business"] = {
                            "language": "zh_cn",
                            "domain": "iat",
                            "accent": "mandarin",
                            "dwa": "wpgs",
                            "ptt": 1,
                        }
                    websocket.send(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
                    if frame_interval_seconds > 0:
                        time.sleep(frame_interval_seconds)
                websocket.send(json.dumps({
                    "data": {
                        "status": 2,
                        "format": "audio/L16;rate=16000",
                        "encoding": "raw",
                        "audio": "",
                    }
                }, separators=(",", ":")))
                while True:
                    raw = websocket.recv(timeout=timeout_seconds)
                    data = json.loads(raw)
                    code = int(data.get("code", -1))
                    if code != 0:
                        raise self._provider_error(code, "语音识别")
                    result = data.get("data", {}).get("result", {})
                    if isinstance(result, dict):
                        self._merge_result(segments, result)
                    if int(data.get("data", {}).get("status", 2)) == 2:
                        break
        except XfyunSpeechError:
            raise
        except TimeoutError as exc:
            raise XfyunSpeechError("语音识别请求超时。", code="timeout", retryable=True) from exc
        except (WebSocketException, OSError) as exc:
            raise XfyunSpeechError("语音识别服务暂不可用。", code="network_error", retryable=True) from exc
        except (TypeError, ValueError, KeyError, json.JSONDecodeError) as exc:
            raise XfyunSpeechError("语音识别服务返回了无法解析的响应。", code="invalid_response") from exc
        transcript = "".join(segments[key] for key in sorted(segments)).strip()
        if not transcript:
            raise XfyunSpeechError("没有识别到有效语音，请重试。", code="empty_transcript")
        return transcript

    def synthesize_mp3(
        self,
        config: XfyunSpeechConfig,
        text: str,
        *,
        timeout_seconds: float,
    ) -> bytes:
        self._require_config(config)
        content = text.strip()
        if not content or len(content.encode("utf-8")) >= 8000:
            raise XfyunSpeechError("朗读文本为空或过长。", code="invalid_text")
        signed_url = self._signed_url(config.tts_url, config)
        payload = {
            "common": {"app_id": config.app_id},
            "business": {
                "aue": "lame",
                "sfl": 1,
                "auf": "audio/L16;rate=16000",
                "vcn": config.tts_voice,
                "speed": max(0, min(100, config.tts_speed)),
                "volume": 50,
                "pitch": 50,
                "tte": "UTF8",
            },
            "data": {
                "status": 2,
                "text": base64.b64encode(content.encode("utf-8")).decode("ascii"),
            },
        }
        chunks: list[bytes] = []
        try:
            with connect(signed_url, open_timeout=timeout_seconds, close_timeout=3) as websocket:
                websocket.send(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
                while True:
                    raw = websocket.recv(timeout=timeout_seconds)
                    data = json.loads(raw)
                    code = int(data.get("code", -1))
                    if code != 0:
                        raise self._provider_error(code, "语音合成")
                    audio = data.get("data", {}).get("audio")
                    if isinstance(audio, str) and audio:
                        chunks.append(base64.b64decode(audio))
                    if int(data.get("data", {}).get("status", 2)) == 2:
                        break
        except XfyunSpeechError:
            raise
        except TimeoutError as exc:
            raise XfyunSpeechError("语音合成请求超时。", code="timeout", retryable=True) from exc
        except (WebSocketException, OSError) as exc:
            raise XfyunSpeechError("语音合成服务暂不可用。", code="network_error", retryable=True) from exc
        except (TypeError, ValueError, KeyError, json.JSONDecodeError) as exc:
            raise XfyunSpeechError("语音合成服务返回了无法解析的响应。", code="invalid_response") from exc
        audio_bytes = b"".join(chunks)
        if not audio_bytes:
            raise XfyunSpeechError("语音合成服务返回了空音频。", code="invalid_response")
        return audio_bytes

    @staticmethod
    def _merge_result(segments: dict[int, str], result: dict[str, object]) -> None:
        replace_range = result.get("rg")
        if result.get("pgs") == "rpl" and isinstance(replace_range, list) and len(replace_range) == 2:
            start, end = int(replace_range[0]), int(replace_range[1])
            for key in range(start, end + 1):
                segments.pop(key, None)
        words: list[str] = []
        for item in result.get("ws", []) if isinstance(result.get("ws"), list) else []:
            if not isinstance(item, dict):
                continue
            candidates = item.get("cw")
            if isinstance(candidates, list) and candidates and isinstance(candidates[0], dict):
                words.append(str(candidates[0].get("w") or ""))
        sn = int(result.get("sn", max(segments, default=-1) + 1))
        segments[sn] = "".join(words)

    @staticmethod
    def _require_config(config: XfyunSpeechConfig) -> None:
        if not config.app_id or not config.api_key or not config.api_secret:
            raise XfyunSpeechError("讯飞语音凭证不完整。", code="not_configured")

    @staticmethod
    def _signed_url(url: str, config: XfyunSpeechConfig) -> str:
        try:
            return build_xfyun_signed_url(url, config.api_key, config.api_secret)
        except XfyunAuthError as exc:
            raise XfyunSpeechError(str(exc), code="invalid_config") from exc

    @staticmethod
    def _provider_error(code: int, service: str) -> XfyunSpeechError:
        if code in {10005, 10105}:
            return XfyunSpeechError(f"{service}认证失败。", code="authentication_failed")
        if code in {10006, 10007, 10009, 10043, 10044, 10109, 10139, 10160, 10161, 10163, 10165}:
            return XfyunSpeechError(f"{service}收到的录音格式无效。", code="invalid_audio")
        if code in {10014, 10019, 10114, 10200, 10700}:
            return XfyunSpeechError(f"{service}请求超时。", code="timeout", retryable=True)
        if code in {11200, 11201, 11202}:
            return XfyunSpeechError(f"{service}额度不足或请求过于频繁。", code="rate_limited", retryable=True)
        return XfyunSpeechError(f"{service}拒绝了本次请求。", code="provider_rejected")

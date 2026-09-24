"""Offline-only speech sidecar. No host port, credentials, database or outbound network."""
from contextlib import asynccontextmanager
import os
from pathlib import Path
from threading import BoundedSemaphore

from fastapi import FastAPI, HTTPException, Request
from starlette.concurrency import run_in_threadpool

from backend.app.providers.local_speech_worker import engine, transcribe

ROOT = Path(os.environ.get("LOCAL_SPEECH_MODEL_DIR", "/models"))
THREADS = max(1, min(int(os.environ.get("LOCAL_SPEECH_THREADS", "2")), 4))
SLOT = BoundedSemaphore(1)
MAX_PCM_BYTES = 60 * 16000 * 2


@asynccontextmanager
async def lifespan(_app):
    # Fail startup when files are missing; never auto-download or contact a provider.
    await run_in_threadpool(engine, "asr", ROOT, THREADS)
    yield


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


def guarded(operation, *args):
    if not SLOT.acquire(blocking=False):
        raise HTTPException(429, "本地语音正在处理其他请求，请稍后重试。")
    try:
        return operation(*args)
    finally:
        SLOT.release()


@app.get("/health")
def health():
    return {"status": "ok", "provider": "sherpa_onnx", "offline": True}


@app.post("/transcriptions")
async def transcription(request: Request):
    audio = bytearray()
    async for chunk in request.stream():
        if len(audio) + len(chunk) > MAX_PCM_BYTES:
            raise HTTPException(413, "录音超过60秒。")
        audio.extend(chunk)
    if not audio or len(audio) % 2:
        raise HTTPException(400, "无效的16k单声道PCM录音。")
    text = await run_in_threadpool(guarded, transcribe, bytes(audio), ROOT, THREADS)
    if not text:
        raise HTTPException(422, "没有识别到有效语音，请重试。")
    return {"transcript": text}

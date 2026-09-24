"""Real offline speech smoke check with synthetic text and official public sample."""
from __future__ import annotations

import io
import json
import os
from pathlib import Path
import time
import wave

import numpy as np

from backend.app.providers.local_speech_worker import engine, synthesize, transcribe


def main() -> None:
    root = Path(os.environ.get("LOCAL_SPEECH_MODEL_DIR", "storage/models/speech"))
    started = time.monotonic()
    engine("asr", root, 2)
    engine("tts", root, 2)
    warmup = time.monotonic() - started
    text = "数据结构是一门课程。队列遵循先进先出。"
    started = time.monotonic()
    audio = synthesize(text, root)
    tts_seconds = time.monotonic() - started
    with wave.open(io.BytesIO(audio), "rb") as source:
        assert source.getnchannels() == 1 and source.getsampwidth() == 2
        rate = source.getframerate()
        samples = np.frombuffer(source.readframes(source.getnframes()), dtype="<i2")
    assert len(samples) > rate and np.max(np.abs(samples.astype(np.int32))) > 100
    pcm = np.interp(np.arange(0, len(samples), rate / 16000), np.arange(len(samples)), samples).astype("<i2")
    started = time.monotonic()
    result = transcribe(pcm.tobytes(), root)
    asr_seconds = time.monotonic() - started
    assert "数据结构" in result and "先进先出" in result, result
    assert transcribe(b"\0\0" * 16000, root) == ""
    with wave.open(str(root / "sensevoice/test_wavs/zh.wav"), "rb") as sample:
        assert sample.getframerate() == 16000 and sample.getsampwidth() == 2
        real = transcribe(sample.readframes(sample.getnframes()), root)
    assert len(real) >= 10
    print(json.dumps({"warmup_seconds": round(warmup, 2), "tts_seconds": round(tts_seconds, 2),
                      "asr_seconds": round(asr_seconds, 2), "audio_seconds": round(len(samples) / rate, 2),
                      "transcript": result, "public_sample_transcript": real,
                      "silence_rejected": True}, ensure_ascii=False))


if __name__ == "__main__":
    main()

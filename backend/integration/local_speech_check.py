"""Real offline recognition check with an official public sample."""
import json
import os
from pathlib import Path
import time
import wave

from backend.app.providers.local_speech_worker import engine, transcribe


def main() -> None:
    root = Path(os.environ.get("LOCAL_SPEECH_MODEL_DIR", "storage/models/speech"))
    started = time.monotonic()
    engine("asr", root, 2)
    warmup = time.monotonic() - started
    with wave.open(str(root / "sensevoice/test_wavs/zh.wav"), "rb") as sample:
        assert sample.getframerate() == 16000 and sample.getsampwidth() == 2
        audio = sample.readframes(sample.getnframes())
    started = time.monotonic()
    result = transcribe(audio, root)
    elapsed = time.monotonic() - started
    assert "九点" in result and "下午五点" in result, result
    assert transcribe(b"\0\0" * 16000, root) == ""
    print(json.dumps({"warmup_seconds": round(warmup, 2), "asr_seconds": round(elapsed, 2),
                      "public_sample_transcript": result, "silence_rejected": True}, ensure_ascii=False))


if __name__ == "__main__":
    main()

"""Private offline process entrypoint; native inference stays outside the API process."""
from __future__ import annotations

import argparse
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=2)
def engine(operation: str, root: Path, threads: int):
    import sherpa_onnx

    if operation == "asr":
        model = root / "sensevoice"
        return sherpa_onnx.OfflineRecognizer.from_sense_voice(
            model=str(model / "model.int8.onnx"), tokens=str(model / "tokens.txt"),
            num_threads=threads, use_itn=True, language="auto", provider="cpu",
        )


def transcribe(audio: bytes, root: Path, threads: int = 2) -> str:
    import numpy as np

    samples = np.frombuffer(audio, dtype="<i2").astype(np.float32) / 32768
    if not np.any(samples):
        return ""
    recognizer = engine("asr", root, threads)
    stream = recognizer.create_stream()
    stream.accept_waveform(16000, samples)
    recognizer.decode_stream(stream)
    return stream.result.text.strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=("asr",))
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--threads", type=int, default=2)
    args = parser.parse_args()
    args.output.write_text(transcribe(args.input.read_bytes(), args.model_dir, args.threads), encoding="utf-8")


if __name__ == "__main__":
    main()

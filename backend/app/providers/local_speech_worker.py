"""Private offline process entrypoint; native inference stays outside the API process."""
from __future__ import annotations

import argparse
from functools import lru_cache
import io
from pathlib import Path
import wave


@lru_cache(maxsize=2)
def engine(operation: str, root: Path, threads: int):
    import sherpa_onnx

    if operation == "asr":
        model = root / "sensevoice"
        return sherpa_onnx.OfflineRecognizer.from_sense_voice(
            model=str(model / "model.int8.onnx"), tokens=str(model / "tokens.txt"),
            num_threads=threads, use_itn=True, language="auto", provider="cpu",
        )
    else:
        model = root / "kokoro"
        config = sherpa_onnx.OfflineTtsConfig(
            model=sherpa_onnx.OfflineTtsModelConfig(
                kokoro=sherpa_onnx.OfflineTtsKokoroModelConfig(
                    model=str(model / "model.int8.onnx"),
                    voices=str(model / "voices.bin"),
                    tokens=str(model / "tokens.txt"), data_dir=str(model / "espeak-ng-data"),
                    lexicon=f"{model / 'lexicon-us-en.txt'},{model / 'lexicon-zh.txt'}",
                ), num_threads=threads, provider="cpu",
            ), rule_fsts=",".join(str(model / name) for name in ("date-zh.fst", "number-zh.fst", "phone-zh.fst")),
        )
        if not config.validate():
            raise ValueError("Invalid local speech model files")
        return sherpa_onnx.OfflineTts(config)


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


def synthesize(text: str, root: Path, threads: int = 2, speaker: int = 3) -> bytes:
    import numpy as np

    audio = engine("tts", root, threads).generate(text, sid=speaker, speed=1.0)
    samples = (np.clip(audio.samples, -1, 1) * 32767).astype("<i2")
    output = io.BytesIO()
    with wave.open(output, "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(audio.sample_rate)
        target.writeframes(samples.tobytes())
    return output.getvalue()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=("asr", "tts"))
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--threads", type=int, default=2)
    parser.add_argument("--speaker", type=int, default=3)
    args = parser.parse_args()
    if args.operation == "asr":
        args.output.write_text(transcribe(args.input.read_bytes(), args.model_dir, args.threads), encoding="utf-8")
    else:
        args.output.write_bytes(synthesize(args.input.read_text(encoding="utf-8"), args.model_dir, args.threads, args.speaker))


if __name__ == "__main__":
    main()

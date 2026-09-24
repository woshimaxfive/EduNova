"""Explicit, pinned download step. Runtime speech never downloads weights."""
from __future__ import annotations

import argparse
from hashlib import file_digest
from pathlib import Path

from huggingface_hub import snapshot_download
import httpx


MODELS = (
    ("sensevoice", "csukuangfj/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2025-09-09",
     "355f4d4884d8afd08aef04b9007a8556d7b463b2", ["model.int8.onnx", "tokens.txt", "README.md", "test_wavs/zh.wav"],
     {"model.int8.onnx": "12ca1a2ae7ecf3e0019ef2822307ee0b5cadc9196569e379b4c4026f8205276d"}),
    ("kokoro", "csukuangfj/kokoro-int8-multi-lang-v1_1",
     "155831f1b4ba23b1f5c058be6a61df90cefb2a37", ["*"],
     {"model.int8.onnx": "bda15858163726a492d02a9a727bc263551b86ac77f90812c4b30ff41d380e26",
      "voices.bin": "e64a5a581d8c2a350d848f51c3121657cd83aa07ed6109172177345874a7244c"}),
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", default="storage/models/speech")
    args = parser.parse_args()
    root = Path(args.model_dir)
    for name, repo, revision, patterns, hashes in MODELS:
        target = root / name
        marker = target / ".prepared-revision"
        required = ["tokens.txt", "model.int8.onnx"]
        if name == "kokoro":
            required += ["voices.bin", "lexicon-us-en.txt", "lexicon-zh.txt", "espeak-ng-data/phondata",
                         "date-zh.fst", "number-zh.fst", "phone-zh.fst", "LICENSE"]
        else:
            required += ["test_wavs/zh.wav"]
        ready = marker.is_file() and marker.read_text(encoding="utf-8") == revision
        ready = ready and all((target / filename).is_file() for filename in required)
        if ready:
            for filename, expected in hashes.items():
                with (target / filename).open("rb") as stream:
                    ready = ready and file_digest(stream, "sha256").hexdigest() == expected
        if not ready:
            snapshot_download(repo, revision=revision, allow_patterns=patterns,
                              local_dir=target, token=False, max_workers=4)
        for filename, expected in hashes.items():
            with (target / filename).open("rb") as stream:
                if file_digest(stream, "sha256").hexdigest() != expected:
                    raise RuntimeError(f"Speech model checksum mismatch: {name}/{filename}")
        marker.write_text(revision, encoding="utf-8")
        print(f"Verified local speech weights: {name}", flush=True)
    license_path = root / "sensevoice" / "MODEL_LICENSE"
    if not license_path.exists():
        url = "https://raw.githubusercontent.com/modelscope/FunASR/3ff9259aade4f7e4360645df28cad8f81959ee91/MODEL_LICENSE"
        response = httpx.get(url, timeout=30, follow_redirects=True)
        response.raise_for_status()
        license_path.write_text(response.text, encoding="utf-8")


if __name__ == "__main__":
    main()

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

)

# The desktop distribution uses the original SenseVoice conversion with an
# explicit upstream model-license pointer. Local tuned weights remain opt-in
# through the existing default; preparing a release uses a separate directory.
RELEASE_MODELS = (
    ("sensevoice", "csukuangfj/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17",
     "2365baeacb507f821a0c8120fcee3d484dba7a07",
     ["model.int8.onnx", "tokens.txt", "README.md", "LICENSE", "test_wavs/zh.wav"],
     {"model.int8.onnx": "c71f0ce00bec95b07744e116345e33d8cbbe08cef896382cf907bf4b51a2cd51",
      "tokens.txt": "f449eb28dc567533d7fa59be34e2abca8784f771850c78a47fb731a31429a1dc",
      "LICENSE": "221c6df10b0931a5629adad671ea48fb7747e034c414b6d2bfa275bc3dd4ea17"}),
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", default="storage/models/speech")
    parser.add_argument("--release-model", action="store_true",
                        help="Prepare the explicitly licensed 2024 model in a separate --model-dir")
    args = parser.parse_args()
    root = Path(args.model_dir)
    if args.release_model and root.resolve() == Path("storage/models/speech").resolve():
        parser.error("--release-model requires a separate --model-dir; local weights are preserved")
    for name, repo, revision, patterns, hashes in RELEASE_MODELS if args.release_model else MODELS:
        target = root / name
        marker = target / ".prepared-revision"
        required = ["tokens.txt", "model.int8.onnx", "test_wavs/zh.wav"]
        if args.release_model:
            required.append("LICENSE")
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

"""Prepare fixed public weights explicitly; serving code never downloads models."""
from __future__ import annotations

import argparse
from hashlib import file_digest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.providers.local_embeddings import LocalEmbeddingProvider, MODEL_REVISION, MODEL_SHA256


def main() -> None:
    from huggingface_hub import snapshot_download

    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", default="storage/models/bge-small-zh-v1.5")
    args = parser.parse_args()
    if LocalEmbeddingProvider.prepared(args.model_dir):
        with (Path(args.model_dir) / "model_optimized.onnx").open("rb") as stream:
            if file_digest(stream, "sha256").hexdigest() == MODEL_SHA256:
                print("本地模型已存在并通过校验，无需下载。")
                return
    destination = snapshot_download(
        "Qdrant/bge-small-zh-v1.5", revision=MODEL_REVISION,
        allow_patterns=["*.json", "*.txt", "model_optimized.onnx", "README.md"],
        local_dir=args.model_dir, token=False, max_workers=2,
    )
    with (Path(destination) / "model_optimized.onnx").open("rb") as stream:
        if file_digest(stream, "sha256").hexdigest() != MODEL_SHA256:
            raise RuntimeError("模型权重校验失败，未启用。")
    print(f"本地模型已准备并通过 SHA-256 校验：{destination}")


if __name__ == "__main__":
    main()

"""Opt-in CPU embedding adapter. Weights must be prepared before serving requests."""
from __future__ import annotations

from hashlib import file_digest
from pathlib import Path
from threading import Lock
from typing import Literal

import numpy as np

from backend.app.providers.openai_compatible import ModelProviderError


MODEL_NAME = "BAAI/bge-small-zh-v1.5"
MODEL_REVISION = "46fbe35fd4374a00fee7de77dfddaeb6dd6a2c59"
MODEL_SHA256 = "1294ea4b6331115a353d81f96b85e8c8d7fdcc284453d5b2fab5b016230aad38"
MODEL_DIMENSION = 512
MODEL_FILES = ("model_optimized.onnx", "config.json", "tokenizer.json", "tokenizer_config.json", "special_tokens_map.json")


class LocalEmbeddingProvider:
    # One model per process, shared across requests. Deployment must account for
    # one copy per worker; this is not a claim of one copy across all containers.
    _lock = Lock()
    _model = None
    _identity: tuple[str, int] | None = None

    @staticmethod
    def prepared(model_path: str) -> bool:
        directory = Path(model_path)
        return all((directory / name).is_file() for name in MODEL_FILES)

    @classmethod
    def _load(cls, model_path: str, threads: int):
        identity = (str(Path(model_path).resolve()), threads)
        if cls._model is not None and cls._identity == identity:
            return cls._model
        if not cls.prepared(model_path):
            raise ModelProviderError("本地向量模型尚未准备，请先下载模型文件。", code="not_configured")
        with (Path(model_path) / "model_optimized.onnx").open("rb") as model_file:
            if file_digest(model_file, "sha256").hexdigest() != MODEL_SHA256:
                raise ModelProviderError("本地向量模型校验失败，请重新准备固定版本。", code="invalid_response")
        try:
            from fastembed import TextEmbedding

            model = TextEmbedding(
                model_name=MODEL_NAME, specific_model_path=identity[0],
                local_files_only=True, threads=threads,
                providers=["CPUExecutionProvider"], cuda=False,
            )
        except ImportError as exc:
            raise ModelProviderError("未安装本地向量推理依赖。", code="not_configured") from exc
        except Exception as exc:
            raise ModelProviderError("本地向量模型加载失败。", code="provider_error") from exc
        cls._model, cls._identity = model, identity
        return model

    def embed(
        self, texts: list[str], *, model_path: str, threads: int = 2,
        input_type: Literal["document", "query"] = "document",
    ) -> list[list[float]]:
        if not texts:
            return []
        if not 1 <= threads <= 8:
            raise ValueError("本地向量线程数必须在 1 到 8 之间。")
        if input_type not in {"document", "query"}:
            raise ValueError("未知向量输入类型。")
        try:
            # Bounded CPU work and serialized inference prevent request fan-out
            # from multiplying ONNX sessions or thread pools.
            with self._lock:
                model = self._load(model_path, threads)
                if input_type == "query":
                    vectors = list(model.query_embed(texts, batch_size=8))
                else:
                    vectors = list(model.passage_embed(texts, batch_size=8))
        except ModelProviderError:
            raise
        except Exception as exc:
            raise ModelProviderError("本地向量推理失败。", code="provider_error") from exc
        values = np.asarray(vectors, dtype=np.float32)
        if values.shape != (len(texts), MODEL_DIMENSION) or not np.isfinite(values).all():
            raise ModelProviderError("本地向量输出维度或数值无效。", code="invalid_response")
        return values.tolist()

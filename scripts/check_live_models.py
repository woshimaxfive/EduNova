"""Probe configured providers with synthetic inputs; never print credentials or raw errors."""

from __future__ import annotations

import json
import argparse
from pathlib import Path
from time import perf_counter

from backend.app.core.config import get_settings
from backend.app.providers.capabilities import provider_capabilities
from backend.app.providers.openai_compatible import (
    ModelProviderError,
    OpenAICompatibleChatProvider,
    OpenAICompatibleConfig,
    OpenAICompatibleEmbeddingConfig,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("output/release-readiness/provider-probe.json"))
    args = parser.parse_args()
    settings = get_settings()
    provider = OpenAICompatibleChatProvider()
    results = []
    for operation in ("chat", "generation", "embedding"):
        started = perf_counter()
        result = {"operation": operation, "ok": False}
        try:
            if operation == "embedding":
                separate = bool(settings.system_embedding_base_url.strip())
                result["model"] = settings.system_embedding_model
                vectors = provider.embed_texts(
                    OpenAICompatibleEmbeddingConfig(
                        settings.system_embedding_base_url if separate else settings.system_model_base_url,
                        settings.system_embedding_api_key if separate else settings.system_model_api_key,
                        settings.system_embedding_model,
                    ),
                    texts=["二叉树的前序遍历按照根、左子树、右子树的顺序访问。"],
                    timeout_seconds=30,
                    dimensions=settings.system_embedding_dimension,
                )
                result["ok"] = bool(vectors and vectors[0])
                result["dimension"] = len(vectors[0]) if vectors else 0
            else:
                generation = operation == "generation"
                result["model"] = settings.system_generation_model if generation else settings.system_chat_model
                base_url = settings.system_generation_base_url if generation else settings.system_model_base_url
                capabilities = provider_capabilities(preset_id=None, base_url=base_url)
                completion = provider.chat_completion_result(
                    OpenAICompatibleConfig(
                        base_url,
                        settings.system_generation_api_key if generation else settings.system_model_api_key,
                        result["model"],
                        thinking_type="disabled" if capabilities.reasoning_protocol == "qwen_enable_thinking" else None,
                        reasoning_protocol=capabilities.reasoning_protocol,
                    ),
                    [{"role": "user", "content": "请用一句话说明二叉树前序遍历的访问顺序。"}],
                    timeout_seconds=30,
                )
                result.update(ok=bool(completion.content), input_tokens=completion.input_tokens,
                              output_tokens=completion.output_tokens)
        except ModelProviderError as exc:
            result.update(error_code=exc.code, http_status=exc.status_code, retryable=exc.retryable)
        except Exception as exc:
            result.update(error_code=type(exc).__name__)
        result["latency_ms"] = round((perf_counter() - started) * 1000, 2)
        results.append(result)
        print(json.dumps(result, ensure_ascii=False), flush=True)
    output = args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if all(item["ok"] for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

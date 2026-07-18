"""Measure RAG stages in the live backend without retaining query or model content."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from statistics import median
from time import perf_counter
from uuid import uuid4

import requests
from sqlalchemy import select

from backend.app.core.config import get_settings
from backend.app.db.session import SessionLocal
from backend.app.models import Course, User
from backend.app.providers.openai_compatible import OpenAICompatibleChatProvider
from backend.app.providers.openai_compatible import ModelProviderError
from backend.app.services.embeddings import EmbeddingService
from backend.app.services.model_settings import ModelSettingsService, SqlAlchemyModelSettingsRepository
from backend.app.services.rag import RagService, SqlAlchemyRagRepository


QUERY = "二叉树遍历的基本顺序是什么？"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Diagnose live RAG stage latency.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--samples", type=int, default=3, choices=range(1, 11))
    return parser.parse_args()


def api_data(response: requests.Response) -> object:
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict) or "data" not in payload:
        raise RuntimeError("API 响应不包含 data。")
    return payload["data"]


class Timings:
    def __init__(self) -> None:
        self.values: dict[str, float] = defaultdict(float)
        self.embedding: dict[str, object] = {}

    def measure(self, name: str, action):  # type: ignore[no-untyped-def]
        started_at = perf_counter()
        result = action()
        self.values[name] += (perf_counter() - started_at) * 1000
        return result


class TimingRepository:
    def __init__(self, delegate: SqlAlchemyRagRepository, timings: Timings) -> None:
        self.delegate = delegate
        self.timings = timings

    def get_course_for_user(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        return self.timings.measure("course_lookup_ms", lambda: self.delegate.get_course_for_user(*args, **kwargs))

    def list_searchable_chunks(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        return self.timings.measure("chunk_load_ms", lambda: self.delegate.list_searchable_chunks(*args, **kwargs))

    def save_chunk_embeddings(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        try:
            result = self.timings.measure("embedding_persist_ms", lambda: self.delegate.save_chunk_embeddings(*args, **kwargs))
        except Exception as exc:
            self.timings.embedding["persist_error_type"] = type(exc).__name__
            raise
        self.timings.embedding["persisted"] = True
        return result

    def vector_candidates(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        return self.timings.measure("pgvector_ms", lambda: self.delegate.vector_candidates(*args, **kwargs))


class TimingEmbeddingService:
    def __init__(self, delegate: EmbeddingService, timings: Timings) -> None:
        self.delegate = delegate
        self.timings = timings

    def expected_metadata(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        return self.delegate.expected_metadata(*args, **kwargs)

    def chunk_needs_embedding(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        needs_embedding = self.delegate.chunk_needs_embedding(*args, **kwargs)
        if needs_embedding:
            self.timings.embedding["target_chunk_count"] = int(self.timings.embedding.get("target_chunk_count", 0)) + 1
        return needs_embedding

    def apply_embeddings(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        batch = self.timings.measure("chunk_embedding_ms", lambda: self.delegate.apply_embeddings(*args, **kwargs))
        self.timings.embedding.update(
            {
                "batch_status": str(getattr(batch, "status", "unknown")),
                "vector_count": len(list(getattr(batch, "vectors", []))),
                "dimension": int(getattr(batch, "dimension", 0)),
            }
        )
        return batch

    def embed_query(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        return self.timings.measure("query_embedding_ms", lambda: self.delegate.embed_query(*args, **kwargs))

    def embed_texts(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        return self.timings.measure("query_embedding_ms", lambda: self.delegate.embed_texts(*args, **kwargs))


class TimingRerankService:
    def __init__(self, delegate: ModelSettingsService, timings: Timings) -> None:
        self.delegate = delegate
        self.timings = timings

    def rerank_documents(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        return self.timings.measure("rerank_ms", lambda: self.delegate.rerank_documents(*args, **kwargs))


def summarize(values: list[float]) -> dict[str, object]:
    return {"p50_ms": round(float(median(values)), 2), "max_ms": round(max(values), 2), "values_ms": [round(item, 2) for item in values]}


def main() -> int:
    args = parse_args()
    account = f"ragdiag_{uuid4().hex[:12]}"
    password = f"RagDiag-{uuid4().hex[:16]}"
    registered = api_data(
        requests.post(
            f"{args.base_url.rstrip('/')}/api/v1/auth/register",
            json={"account": account, "password": password, "display_name": "RAG 诊断", "starter_mode": "data_structures"},
            timeout=30,
        )
    )
    if not isinstance(registered, dict) or not isinstance(registered.get("id"), int):
        raise RuntimeError("一次性账号创建失败。")
    user_id = int(registered["id"])
    db = SessionLocal()
    try:
        user = db.get(User, user_id)
        course = db.scalar(select(Course).where(Course.owner_id == user_id).order_by(Course.id))
        if user is None or course is None:
            raise RuntimeError("示例课程不可用。")
        model_settings = ModelSettingsService(
            repository=SqlAlchemyModelSettingsRepository(db),
            settings=get_settings(),
            provider=OpenAICompatibleChatProvider(),
        )
        embedding_service = EmbeddingService(model_settings)

        def probe_document_embedding() -> dict[str, object]:
            chunks = SqlAlchemyRagRepository(db).list_searchable_chunks(course.id)
            targets = [chunk for chunk in chunks if embedding_service.chunk_needs_embedding(user, chunk)][:24]
            if not targets:
                return {"status": "not_needed"}
            runtime = model_settings.resolve_embedding_runtime_config(user)
            started_at = perf_counter()
            try:
                vectors = model_settings.embedding_vectors(
                    user,
                    [chunk.content for chunk in targets],
                    dimensions=runtime.dimensions,
                    input_type="document",
                )
            except ModelProviderError as exc:
                return {
                    "status": "error",
                    "error_code": exc.code,
                    "retryable": bool(exc.retryable),
                    "elapsed_ms": round((perf_counter() - started_at) * 1000, 2),
                    "requested_count": len(targets),
                }
            return {
                "status": "completed",
                "vector_count": len(vectors),
                "dimension": len(vectors[0]) if vectors else 0,
                "elapsed_ms": round((perf_counter() - started_at) * 1000, 2),
                "requested_count": len(targets),
            }

        def run_once() -> tuple[float, dict[str, float], dict[str, object]]:
            timings = Timings()
            service = RagService(
                TimingRepository(SqlAlchemyRagRepository(db), timings),
                embedding_service=TimingEmbeddingService(EmbeddingService(model_settings), timings),
                rerank_service=TimingRerankService(model_settings, timings),
            )
            started_at = perf_counter()
            service.search(user, course.id, QUERY, top_k=3)
            return (perf_counter() - started_at) * 1000, dict(timings.values), dict(timings.embedding)

        # Warm-up handles any first-read/course-embedding cost and is excluded.
        run_once()
        samples = [run_once() for _ in range(args.samples)]
        stage_names = sorted({name for _, values, _ in samples for name in values} | {"end_to_end_ms"})
        output = {
            "schema_version": 1,
            "sample_count": args.samples,
            "warmup_excluded": True,
            "stages": {
                name: summarize([total if name == "end_to_end_ms" else values.get(name, 0.0) for total, values, _ in samples])
                for name in stage_names
            },
            "embedding_outcomes": [outcome for _, _, outcome in samples],
            "single_document_probe": probe_document_embedding(),
            "privacy": "未输出查询、检索结果、模型回答、资料、密码、令牌或密钥。",
        }
        print(json.dumps({"account": account, "user_id": user_id, "diagnostic": output}, ensure_ascii=False))
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

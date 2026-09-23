"""Offline retrieval comparison on built-in course data; no user DB or API keys."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from time import perf_counter
from types import SimpleNamespace

import numpy as np

from backend.app.data.builtin_courses.data_structures import PACKAGE_DIR
from backend.app.providers.local_embeddings import LocalEmbeddingProvider, MODEL_NAME, MODEL_REVISION
from backend.app.services.rag import RagService


def run(model_dir: str) -> dict:
    points = []
    for path in sorted((PACKAGE_DIR / "chapters").glob("*.json")):
        points.extend(json.loads(path.read_text(encoding="utf-8"))["knowledge_points"])
    guidance = json.loads((PACKAGE_DIR / "quality-benchmarks.json").read_text(encoding="utf-8"))["point_guidance"]
    # Do not embed guidance/check questions: they are held out as queries.
    texts = [
        "\n".join([point["title"], point["summary"], *[
            point[section]["content"] for section in ("concept", "process", "pitfall")
        ]]) for point in points
    ]
    queries = [guidance[point["key"]]["check_question"] for point in points]
    provider = LocalEmbeddingProvider()
    started = perf_counter()
    vectors = np.asarray(provider.embed(texts, model_path=model_dir))
    document_seconds = perf_counter() - started
    started = perf_counter()
    query_vectors = np.asarray(provider.embed(queries, model_path=model_dir, input_type="query"))
    query_seconds = perf_counter() - started
    similarities = query_vectors @ vectors.T
    scores = {mode: {"recall_at_1": 0, "recall_at_5": 0} for mode in ("keyword", "vector", "hybrid")}
    misses = []
    chunks = [SimpleNamespace(
        content=text, section_title=point["title"], material=None, knowledge_point=None,
    ) for point, text in zip(points, texts, strict=True)]
    for expected, query in enumerate(queries):
        terms = RagService._query_terms(query)
        keyword_scores = [RagService._score_chunk(chunk, query, terms) for chunk in chunks]
        keyword = sorted(range(len(points)), key=lambda i: (-keyword_scores[i], i))
        keyword = [i for i in keyword if keyword_scores[i] > 0][:30]
        vector = sorted(range(len(points)), key=lambda i: (-similarities[expected, i], i))[:30]
        rrf = {}
        for ranking in (keyword, vector):
            for rank, index in enumerate(ranking, 1):
                rrf[index] = rrf.get(index, 0) + 1 / (60 + rank)
        hybrid = sorted(rrf, key=lambda i: (-rrf[i], i))
        for mode, ranking in (("keyword", keyword), ("vector", vector), ("hybrid", hybrid)):
            scores[mode]["recall_at_1"] += int(expected in ranking[:1])
            scores[mode]["recall_at_5"] += int(expected in ranking[:5])
        if expected not in hybrid[:5]:
            misses.append({"key": points[expected]["key"], "query": query,
                           "top5": [points[i]["key"] for i in hybrid[:5]]})
    return {
        "model": MODEL_NAME, "revision": MODEL_REVISION,
        "corpus": "built-in course, one document per knowledge point; held-out check questions",
        "case_count": len(points), "dimension": vectors.shape[1],
        "document_seconds_including_load": round(document_seconds, 3),
        "query_batch_seconds": round(query_seconds, 3),
        "scores": scores, "hybrid_top5_misses": misses,
        "limits": "Offline diagnostic only; no external baseline, DB index migration or full-service memory acceptance.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", default="storage/models/bge-small-zh-v1.5")
    parser.add_argument("--output")
    args = parser.parse_args()
    result = json.dumps(run(args.model_dir), ensure_ascii=False, indent=2)
    if args.output:
        target = Path(args.output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(result + "\n", encoding="utf-8")
    print(result)


if __name__ == "__main__":
    main()

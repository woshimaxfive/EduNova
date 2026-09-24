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


def evaluate_rankings(keys: list[str], queries: list[str], chunks: list, similarities: np.ndarray) -> dict:
    """Keep per-case evidence, including regressions hidden by aggregate recall."""
    if len(keys) != len(queries) or len(keys) != len(chunks) or similarities.shape != (len(keys), len(keys)):
        raise ValueError("评测查询、文档与相似度矩阵不对应")
    if not np.isfinite(similarities).all():
        raise ValueError("相似度包含无效数值")
    scores = {mode: {"recall_at_1": 0, "recall_at_5": 0} for mode in ("keyword", "vector", "hybrid")}
    cases = []
    for expected, query in enumerate(queries):
        terms = RagService._query_terms(query)
        keyword_scores = [RagService._score_chunk(chunk, query, terms) for chunk in chunks]
        keyword = sorted(range(len(keys)), key=lambda i: (-keyword_scores[i], i))
        keyword = [i for i in keyword if keyword_scores[i] > 0][:30]
        # Match the production cosine-distance candidate ordering and RRF limits.
        vector = sorted(range(len(keys)), key=lambda i: (-max(0.0, similarities[expected, i]), i))[:30]
        rrf = {}
        for ranking in (keyword, vector):
            for rank, index in enumerate(ranking, 1):
                rrf[index] = rrf.get(index, 0) + 1 / (60 + rank)
        hybrid = sorted(rrf, key=lambda i: (-rrf[i], -keyword_scores[i], i))[:20]
        rankings = {"keyword": keyword, "vector": vector, "hybrid": hybrid}
        for mode, ranking in rankings.items():
            scores[mode]["recall_at_1"] += int(expected in ranking[:1])
            scores[mode]["recall_at_5"] += int(expected in ranking[:5])
        cases.append({
            "key": keys[expected], "query": query,
            "expected_ranks": {mode: ranking.index(expected) + 1 if expected in ranking else None
                               for mode, ranking in rankings.items()},
            "top5": {mode: [{"key": keys[i], "keyword_score": keyword_scores[i],
                             "cosine": round(float(similarities[expected, i]), 6),
                             "rrf_score": round(rrf.get(i, 0), 8)} for i in ranking[:5]]
                     for mode, ranking in rankings.items()},
        })
    regressions = [case["key"] for case in cases
                   if case["expected_ranks"]["keyword"] == 1 and case["expected_ranks"]["hybrid"] != 1]
    gains = [case["key"] for case in cases
             if case["expected_ranks"]["keyword"] != 1 and case["expected_ranks"]["hybrid"] == 1]
    return {"scores": scores, "cases": cases, "hybrid_top1_regressions": regressions,
            "hybrid_top1_gains": gains,
            "hybrid_top5_misses": [case for case in cases if case["expected_ranks"]["hybrid"] is None
                                   or case["expected_ranks"]["hybrid"] > 5]}


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
    # Explicit normalization makes this comparison match pgvector cosine distance
    # even when the inference adapter changes its normalization policy.
    similarities = (query_vectors / np.linalg.norm(query_vectors, axis=1, keepdims=True)) @ (
        vectors / np.linalg.norm(vectors, axis=1, keepdims=True)).T
    chunks = [SimpleNamespace(
        content=text, section_title=point["title"], material=None, knowledge_point=None,
    ) for point, text in zip(points, texts, strict=True)]
    from tokenizers import Tokenizer

    tokenizer = Tokenizer.from_file(str(Path(model_dir) / "tokenizer.json"))
    tokenizer.no_truncation()
    tokenizer.no_padding()
    lengths = [len(item.ids) for item in tokenizer.encode_batch(texts)]
    ranking_report = evaluate_rankings([point["key"] for point in points], queries, chunks, similarities)
    return {
        "model": MODEL_NAME, "revision": MODEL_REVISION,
        "corpus": "built-in course, one document per knowledge point; held-out check questions",
        "case_count": len(points), "dimension": vectors.shape[1],
        "document_seconds_including_load": round(document_seconds, 3),
        "query_batch_seconds": round(query_seconds, 3),
        **ranking_report,
        "token_lengths": {"max": max(lengths), "over_512": sum(length > 512 for length in lengths),
                          "by_key": dict(zip([point["key"] for point in points], lengths, strict=True))},
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

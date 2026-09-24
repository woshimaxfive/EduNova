from types import SimpleNamespace

import numpy as np
import pytest

from backend.evals.local_embedding_check import evaluate_rankings
from backend.app.services.rag import RagService
from backend.app.models import MaterialChunk
from backend.app.services.material_retrieval import MaterialRetrievalService
from backend.tests.test_material_retrieval import FakeMaterialRetrievalRepository, make_material
from backend.tests.test_rag_search import make_repository, make_user


def test_diagnostic_reports_top1_regression_even_when_top5_passes(monkeypatch):
    chunks = [SimpleNamespace(index=i) for i in range(3)]
    monkeypatch.setattr(RagService, "_score_chunk", lambda chunk, query, terms: [10, 9, 8][chunk.index])
    report = evaluate_rankings(["a", "b", "c"], ["q"] * 3, chunks,
                               np.array([[0.1, 0.9, 0.8]] * 3))
    assert "a" in report["hybrid_top1_regressions"]
    assert report["hybrid_top5_misses"] == []
    assert report["cases"][0]["expected_ranks"]["keyword"] == 1
    assert report["cases"][0]["expected_ranks"]["hybrid"] == 2


@pytest.mark.parametrize("matrix", [np.zeros((2, 1)), np.array([[np.nan]])])
def test_diagnostic_rejects_mismatched_or_invalid_similarity(matrix):
    with pytest.raises(ValueError):
        evaluate_rankings(["a"], ["q"], [SimpleNamespace()], matrix)


@pytest.mark.parametrize("ids", [(10, 20), (20, 10)])
def test_course_rrf_tie_prefers_lexical_evidence_not_insertion_id(monkeypatch, ids):
    repo = make_repository()
    repo.chunks = repo.chunks[:2]
    preferred, semantic = repo.chunks
    preferred.id, semantic.id = ids
    service = RagService(repo)
    monkeypatch.setattr(service, "_score_chunk", lambda chunk, *args: 10 if chunk is preferred else 7)
    monkeypatch.setattr(service, "_query_embedding", lambda *args: {
        "status": "completed", "vector": [1], "source": "test", "model": "test",
        "dimension": 1, "profile_hash": "test",
    })
    monkeypatch.setattr(repo, "vector_candidates", lambda *args, **kwargs: [(semantic, 0.1), (preferred, 0.2)])
    result = service.search(make_user(), 101, "测试")
    assert result.results[0].chunk_id == preferred.id


@pytest.mark.parametrize("ids", [(10, 20), (20, 10)])
def test_material_rrf_tie_prefers_lexical_evidence_not_insertion_id(monkeypatch, ids):
    material = make_material(material_id=21, user_id=1, text="合成资料")
    preferred = MaterialChunk(id=ids[0], material_id=21, chunk_index=0, content="精确匹配", metadata_json={})
    semantic = MaterialChunk(id=ids[1], material_id=21, chunk_index=1, content="相近主题", metadata_json={})
    repo = FakeMaterialRetrievalRepository(materials=[material], chunks=[preferred, semantic])
    service = MaterialRetrievalService(repo)
    monkeypatch.setattr(service, "_keyword_score", lambda chunk, *args: 10 if chunk is preferred else 7)
    monkeypatch.setattr(service, "_ensure_embeddings", lambda *args: ("completed", [1], ("test", "test", 1, "test")))
    monkeypatch.setattr(repo, "vector_candidates", lambda *args, **kwargs: [(semantic, 0.1), (preferred, 0.2)])
    result = service.search(make_user(), [21], "测试")
    assert result.citations[0]["snippet"] == "精确匹配"

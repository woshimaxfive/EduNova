from types import SimpleNamespace

import numpy as np
import pytest

from backend.app.providers.local_embeddings import LocalEmbeddingProvider, MODEL_FILES
from backend.app.providers.openai_compatible import ModelProviderError
from backend.app.services.embeddings import EmbeddingBatch, EmbeddingProfile
from backend.app.services.material_retrieval import MaterialRetrievalService
from backend.app.services.rag import RagService
from backend.tests.test_rag_search import make_repository, make_user
from backend.tests.test_material_retrieval import FakeMaterialRetrievalRepository


def test_missing_local_weights_fail_without_downloading(tmp_path):
    provider = LocalEmbeddingProvider()
    with pytest.raises(ModelProviderError, match="尚未准备"):
        provider.embed(["学习"], model_path=str(tmp_path))
    assert list(tmp_path.iterdir()) == []


def test_corrupt_local_weights_are_rejected_before_loading(tmp_path):
    for name in MODEL_FILES:
        (tmp_path / name).write_bytes(b"invalid")
    with pytest.raises(ModelProviderError, match="校验失败"):
        LocalEmbeddingProvider().embed(["学习"], model_path=str(tmp_path))


def test_local_adapter_routes_queries_and_documents_with_bounded_cpu(monkeypatch):
    calls = []

    class Model:
        def query_embed(self, texts, batch_size):
            calls.append(("query", texts, batch_size))
            return np.ones((len(texts), 512), dtype=np.float32)

        def passage_embed(self, texts, batch_size):
            calls.append(("document", texts, batch_size))
            return np.ones((len(texts), 512), dtype=np.float32)

    monkeypatch.setattr(LocalEmbeddingProvider, "_load", lambda *args: Model())
    provider = LocalEmbeddingProvider()
    assert len(provider.embed(["课程"], model_path="test")[0]) == 512
    assert len(provider.embed(["问题"], model_path="test", input_type="query")[0]) == 512
    assert [call[0] for call in calls] == ["document", "query"]
    assert all(call[2] == 8 for call in calls)
    with pytest.raises(ValueError):
        provider.embed(["课程"], model_path="test", threads=100)


@pytest.mark.parametrize("vectors", [np.ones((1, 3)), np.full((1, 512), np.nan)])
def test_local_adapter_rejects_invalid_vectors(monkeypatch, vectors):
    monkeypatch.setattr(LocalEmbeddingProvider, "_load", lambda *args: SimpleNamespace(
        passage_embed=lambda *args, **kwargs: vectors,
    ))
    with pytest.raises(ModelProviderError, match="维度或数值无效"):
        LocalEmbeddingProvider().embed(["课程"], model_path="test")


class NewProfileEmbedding:
    def expected_metadata(self, user):
        return "fastembed_local", "new-model", 2

    def expected_profile(self, user):
        return EmbeddingProfile("fastembed_local", "new-model", 2, "new-profile")

    def chunk_needs_embedding(self, user, chunk):
        return True

    def apply_embeddings(self, user, chunks):
        raise AssertionError("不得因模型切换自动覆盖已有向量")

    def embed_documents(self, user, texts):
        raise AssertionError("不得因模型切换自动覆盖已有向量")

    def embed_query(self, user, text):
        return EmbeddingBatch([[1.0, 0.0]], "fastembed_local", "new-model", 2, "completed", "new-profile")


def test_course_lazy_retrieval_preserves_old_profile_and_uses_keyword():
    repository = make_repository()
    for chunk in repository.chunks:
        chunk.embedding = np.array([0.0, 1.0], dtype=np.float32)
        chunk.embedding_provider = "old-provider"
        chunk.embedding_model = "old-model"
        chunk.embedding_dimension = 2
        chunk.embedding_profile_hash = "old-profile"
    result = RagService(repository, NewProfileEmbedding()).search(make_user(), 101, "启发式搜索")
    assert result.results
    assert not repository.saved_chunks
    assert all(chunk.embedding_profile_hash == "old-profile" for chunk in repository.chunks)
    assert all(np.array_equal(chunk.embedding, [0.0, 1.0]) for chunk in repository.chunks)


def test_material_lazy_retrieval_preserves_old_profile():
    repository = FakeMaterialRetrievalRepository()
    chunk = SimpleNamespace(
        content="课程资料", embedding=np.array([0.0, 1.0], dtype=np.float32),
        embedding_provider="old-provider", embedding_model="old-model",
        embedding_dimension=2, embedding_profile_hash="old-profile",
    )
    service = MaterialRetrievalService(repository, embedding_service=NewProfileEmbedding())
    status, vector, profile = service._ensure_embeddings(make_user(), [chunk], "课程")
    assert status == "completed" and vector == [1.0, 0.0]
    assert profile[-1] == "new-profile"
    assert chunk.embedding_profile_hash == "old-profile"
    assert np.array_equal(chunk.embedding, [0.0, 1.0])
    assert not repository.save_count

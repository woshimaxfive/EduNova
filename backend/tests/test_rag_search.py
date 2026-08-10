from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from fastapi.testclient import TestClient

from backend.app.api.v1.deps import get_auth_service
from backend.app.api.v1.rag import get_rag_service
from backend.app.core.config import Settings
from backend.app.core.security import create_access_token
from backend.app.main import create_app
from backend.app.models import Course, CourseMaterial, KnowledgeChunk, KnowledgePoint, User
from backend.app.providers.retrieval import RerankItem
from backend.app.services.auth import AuthService
from backend.app.services.rag import RagCourseNotFoundError, RagService


@dataclass
class TokenAuthRepository:
    user: User

    def get_user_by_id(self, user_id: int) -> User | None:
        return self.user if self.user.id == user_id else None


@dataclass
class FakeRagRepository:
    courses: list[Course] = field(default_factory=list)
    chunks: list[KnowledgeChunk] = field(default_factory=list)
    saved_chunks: list[KnowledgeChunk] = field(default_factory=list)

    def get_course_for_user(self, user_id: int, course_id: int) -> Course | None:
        return next((course for course in self.courses if course.id == course_id and course.owner_id == user_id), None)

    def list_searchable_chunks(self, course_id: int) -> list[KnowledgeChunk]:
        return sorted((chunk for chunk in self.chunks if chunk.course_id == course_id), key=lambda chunk: chunk.id)

    def save_chunk_embeddings(self, chunks: list[KnowledgeChunk]) -> None:
        self.saved_chunks.extend(chunks)

    def vector_candidates(
        self,
        course_id: int,
        query_vector: list[float],
        *,
        embedding_source: str,
        embedding_model: str,
        embedding_dimension: int,
        embedding_profile_hash: str,
        limit: int,
    ) -> list[tuple[KnowledgeChunk, float]]:
        candidates: list[tuple[KnowledgeChunk, float]] = []
        for chunk in self.chunks:
            metadata = chunk.metadata_json or {}
            if (
                chunk.course_id != course_id
                or metadata.get("embedding_source") != embedding_source
                or metadata.get("embedding_model") != embedding_model
                or chunk.embedding_dimension != embedding_dimension
                or chunk.embedding_profile_hash != embedding_profile_hash
            ):
                continue
            vector = chunk.embedding or []
            similarity = sum(left * right for left, right in zip(query_vector, vector, strict=True))
            candidates.append((chunk, 1.0 - similarity))
        return sorted(candidates, key=lambda item: (item[1], item[0].id))[:limit]


@dataclass
class FakeEmbeddingBatch:
    vectors: list[list[float]]
    source: str
    model: str
    dimension: int
    status: str
    profile_hash: str = "test-embedding-profile"


@dataclass
class FakeEmbeddingService:
    batches: list[FakeEmbeddingBatch]
    calls: list[list[str]] = field(default_factory=list)

    def embed_texts(self, _user: User, texts: list[str]) -> FakeEmbeddingBatch:
        self.calls.append(texts)
        return self.batches.pop(0)

    def embed_query(self, user: User, text: str) -> FakeEmbeddingBatch:
        return self.embed_texts(user, [text])

    def apply_embeddings(self, user: User, chunks: list[KnowledgeChunk]) -> FakeEmbeddingBatch:
        batch = self.embed_texts(user, [chunk.content for chunk in chunks])
        RagService._apply_batch_to_chunks(batch, chunks)
        return batch

    def chunk_needs_embedding(self, _user: User, chunk: KnowledgeChunk) -> bool:
        return chunk.embedding is None

    def expected_metadata(self, _user: User) -> tuple[str, str, int]:
        batch = self.batches[0]
        return batch.source, batch.model, batch.dimension


@dataclass
class FakeRerankService:
    items: list[RerankItem] = field(default_factory=list)
    error: Exception | None = None
    calls: list[tuple[str, list[str], int]] = field(default_factory=list)

    def rerank_documents(self, _user: User, query: str, documents: list[str], top_n: int = 5) -> list[RerankItem]:
        self.calls.append((query, documents, top_n))
        if self.error is not None:
            raise self.error
        return self.items


def make_user(user_id: int = 1) -> User:
    return User(
        id=user_id,
        account=f"user{user_id}",
        hashed_password="not-used",
        display_name=f"用户 {user_id}",
        role="student",
        starter_mode="blank",
    )


def make_chunk(
    chunk_id: int,
    course_id: int,
    material: CourseMaterial,
    point: KnowledgePoint,
    content: str,
    section_title: str,
) -> KnowledgeChunk:
    chunk = KnowledgeChunk(
        id=chunk_id,
        course_id=course_id,
        material_id=material.id,
        knowledge_point_id=point.id,
        content=content,
        page_number=None,
        section_title=section_title,
        embedding=None,
        metadata_json={},
    )
    chunk.material = material
    chunk.knowledge_point = point
    return chunk


def make_repository() -> FakeRagRepository:
    course = Course(id=101, owner_id=1, title="AI 搜索复习", source_type="uploaded", status="ready")
    other_course = Course(id=202, owner_id=2, title="别人的课", source_type="uploaded", status="ready")
    material = CourseMaterial(
        id=301,
        user_id=1,
        course_id=101,
        filename="人工智能导论讲义.md",
        content_type="text/markdown",
        storage_path="user_1/ai.md",
        parse_status="completed",
        extracted_text="",
        metadata_json={},
    )
    txt_material = CourseMaterial(
        id=302,
        user_id=1,
        course_id=101,
        filename="期末复习题.txt",
        content_type="text/plain",
        storage_path="user_1/exam.txt",
        parse_status="completed",
        extracted_text="",
        metadata_json={},
    )
    heuristic = KnowledgePoint(id=401, course_id=101, title="启发式搜索", summary="A* 和启发函数", chapter="搜索问题", order_index=1)
    blind = KnowledgePoint(id=402, course_id=101, title="盲目搜索", summary="无额外信息", chapter="搜索问题", order_index=2)
    return FakeRagRepository(
        courses=[course, other_course],
        chunks=[
            make_chunk(
                501,
                101,
                material,
                heuristic,
                "启发式搜索利用启发函数估计路径代价，A* 会结合实际代价和预估代价。",
                "启发式搜索",
            ),
            make_chunk(
                502,
                101,
                txt_material,
                blind,
                "盲目搜索不使用问题领域的额外信息，只按固定策略展开节点。",
                "第 1 部分",
            ),
            make_chunk(
                503,
                101,
                txt_material,
                heuristic,
                "期末题常问 A* 的可采纳性以及启发函数为什么不能高估真实代价。",
                "第 2 部分",
            ),
        ],
    )


def make_service(repo: FakeRagRepository | None = None) -> RagService:
    return RagService(repository=repo or make_repository())


def unit_vector(index: int) -> list[float]:
    vector = [0.0] * 1536
    vector[index] = 1.0
    return vector


def test_rag_route_requires_login() -> None:
    client = TestClient(create_app())

    response = client.post("/api/v1/rag/search", json={"course_id": 101, "query": "启发式搜索", "top_k": 5})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_rag_search_returns_current_user_citations_sorted_by_score() -> None:
    result = make_service().search(make_user(), course_id=101, query="启发式搜索 A*", top_k=2)

    assert len(result.results) == 2
    assert result.results[0].chunk_id == 501
    assert result.results[0].course_id == 101
    assert result.results[0].material_id == 301
    assert result.results[0].knowledge_point_id == 401
    assert result.results[0].source_title == "人工智能导论讲义.md"
    assert result.results[0].section_title == "启发式搜索"
    assert "启发函数" in result.results[0].content
    assert result.results[0].score >= result.results[1].score


def test_keyword_scoring_prioritizes_english_algorithm_names_over_generic_question_words() -> None:
    repository = make_repository()
    algorithm = repository.chunks[0]
    algorithm.content = "Dijkstra 算法通过松弛边计算单源最短路径，不能直接处理负权边。"
    generic = repository.chunks[1]
    generic.content = "为什么这个问题不能使用一般处理方式，需要继续分析。"
    query = "Dijkstra 为什么不能处理负权边"
    terms = RagService._query_terms(query)

    assert RagService._score_chunk(algorithm, query, terms) > RagService._score_chunk(generic, query, terms)


def test_rag_search_uses_external_embedding_sql_candidates_and_returns_metadata() -> None:
    repo = make_repository()
    embedding_service = FakeEmbeddingService(
        batches=[
            FakeEmbeddingBatch(
                vectors=[unit_vector(1), unit_vector(0), unit_vector(0)],
                source="user",
                model="text-embedding-3-small",
                dimension=1536,
                status="completed",
            ),
            FakeEmbeddingBatch(
                vectors=[unit_vector(1)],
                source="user",
                model="text-embedding-3-small",
                dimension=1536,
                status="completed",
            ),
        ]
    )
    service = RagService(repository=repo, embedding_service=embedding_service)

    result = service.search(make_user(), course_id=101, query="语义向量问题", top_k=3)

    assert result.retrieval_mode == "hybrid"
    assert result.embedding_status == "completed"
    assert result.results[0].chunk_id == 501
    assert result.results[0].retrieval_source == "vector"
    assert result.results[0].keyword_score == 0
    assert result.results[0].vector_score > 0
    assert repo.saved_chunks == repo.chunks
    assert repo.chunks[0].metadata_json["embedding_model"] == "text-embedding-3-small"
    assert repo.chunks[0].metadata_json["embedding_dimension"] == 1536


def test_rag_search_keeps_local_hash_as_keyword_fallback_only() -> None:
    repo = make_repository()
    embedding_service = FakeEmbeddingService(
        batches=[
            FakeEmbeddingBatch(
                vectors=[unit_vector(1)],
                source="local",
                model="local-hash-1536",
                dimension=1536,
                status="local_fallback",
            )
        ]
    )

    result = RagService(repository=repo, embedding_service=embedding_service).search(
        make_user(),
        course_id=101,
        query="启发式搜索",
        top_k=3,
    )

    assert result.retrieval_mode == "keyword"
    assert result.embedding_status == "local_fallback"
    assert result.results[0].retrieval_source == "keyword"
    assert result.results[0].vector_score == 0
    assert repo.saved_chunks == []


def test_rag_search_reranks_rrf_candidates_and_exposes_safe_metadata() -> None:
    rerank_service = FakeRerankService(
        items=[RerankItem(index=1, score=0.96), RerankItem(index=0, score=0.72)]
    )

    result = RagService(repository=make_repository(), rerank_service=rerank_service).search(
        make_user(),
        course_id=101,
        query="启发式搜索",
        top_k=2,
    )

    assert [item.chunk_id for item in result.results] == [503, 501]
    assert result.results[0].rerank_score == pytest.approx(0.96)
    assert result.results[0].rerank_status == "completed"
    assert rerank_service.calls[0][0] == "启发式搜索"
    assert len(rerank_service.calls[0][1]) == 3
    assert rerank_service.calls[0][2] == 2


def test_rag_search_keeps_rrf_order_when_rerank_provider_fails() -> None:
    result = RagService(
        repository=make_repository(),
        rerank_service=FakeRerankService(error=RuntimeError("provider failed")),
    ).search(make_user(), course_id=101, query="启发式搜索", top_k=2)

    assert [item.chunk_id for item in result.results] == [501, 503]
    assert all(item.rerank_score is None for item in result.results)
    assert all(item.rerank_status == "provider_failed" for item in result.results)


def test_rag_search_denies_other_user_course() -> None:
    with pytest.raises(RagCourseNotFoundError):
        make_service().search(make_user(2), course_id=101, query="启发式搜索", top_k=5)


def test_rag_search_validates_query_and_top_k() -> None:
    user = make_user()
    service = make_service()

    with pytest.raises(ValueError, match="检索问题不能为空"):
        service.search(user, course_id=101, query="  ", top_k=5)

    with pytest.raises(ValueError, match="top_k 必须在 1 到 10 之间"):
        service.search(user, course_id=101, query="启发式搜索", top_k=0)

    with pytest.raises(ValueError, match="top_k 必须在 1 到 10 之间"):
        service.search(user, course_id=101, query="启发式搜索", top_k=99)


def test_rag_search_returns_empty_results_without_fabricating_sources() -> None:
    result = make_service().search(make_user(), course_id=101, query="量子通信", top_k=5)

    assert result.course_id == 101
    assert result.query == "量子通信"
    assert result.results == []


def test_rag_search_matches_markdown_titles_txt_content_and_chinese_terms() -> None:
    service = make_service()

    title_result = service.search(make_user(), course_id=101, query="搜索问题", top_k=5)
    txt_result = service.search(make_user(), course_id=101, query="固定策略展开节点", top_k=5)
    chinese_bigram_result = service.search(make_user(), course_id=101, query="高估代价", top_k=5)

    assert [item.chunk_id for item in title_result.results][:2] == [501, 502]
    assert txt_result.results[0].chunk_id == 502
    assert chinese_bigram_result.results[0].chunk_id == 503


def test_rag_search_route_returns_documented_envelope() -> None:
    repo = make_repository()
    user = make_user()
    settings = Settings(_env_file=None, jwt_secret="rag-test-secret-with-more-than-32-bytes", jwt_expire_minutes=30)
    app = create_app()
    app.dependency_overrides[get_auth_service] = lambda: AuthService(
        repository=TokenAuthRepository(user),
        settings=settings,
    )
    app.dependency_overrides[get_rag_service] = lambda: RagService(repository=repo)
    client = TestClient(app)
    token = create_access_token(str(user.id), settings=settings)

    response = client.post(
        "/api/v1/rag/search",
        headers={"Authorization": f"Bearer {token}"},
        json={"course_id": 101, "query": "启发式搜索", "top_k": 1},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["results"][0]["chunk_id"] == 501
    assert body["data"]["results"][0]["source_title"] == "人工智能导论讲义.md"
    assert body["data"]["retrieval_mode"] in {"keyword", "hybrid"}
    assert "embedding_status" in body["data"]
    assert "keyword_score" in body["data"]["results"][0]
    assert body["trace_id"].startswith("trace_")

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.app.models import Course, KnowledgeChunk, User
from backend.app.schemas.rag import RagSearchResponse, RagSearchResultItem
from backend.app.services.embeddings import EMBEDDING_DIMENSION


class RagCourseNotFoundError(Exception):
    pass


class RagValidationError(ValueError):
    pass


@dataclass(frozen=True)
class ScoredChunk:
    chunk: KnowledgeChunk
    score: float
    keyword_score: float = 0.0
    vector_score: float = 0.0
    retrieval_source: str = "keyword"
    embedding_status: str = "unavailable"


class RagEmbeddingService(Protocol):
    def embed_texts(self, user: User, texts: list[str]) -> Any: ...

    def apply_embeddings(self, user: User, chunks: list[KnowledgeChunk]) -> Any: ...

    def chunk_needs_embedding(self, user: User, chunk: KnowledgeChunk) -> bool: ...


class SqlAlchemyRagRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_course_for_user(self, user_id: int, course_id: int) -> Course | None:
        return self.db.scalar(select(Course).where(Course.id == course_id, Course.owner_id == user_id))

    def list_searchable_chunks(self, course_id: int) -> list[KnowledgeChunk]:
        statement = (
            select(KnowledgeChunk)
            .where(KnowledgeChunk.course_id == course_id)
            .options(selectinload(KnowledgeChunk.material), selectinload(KnowledgeChunk.knowledge_point))
            .order_by(KnowledgeChunk.id)
        )
        return list(self.db.scalars(statement))

    def save_chunk_embeddings(self, chunks: list[KnowledgeChunk]) -> None:
        for chunk in chunks:
            self.db.add(chunk)
        self.db.commit()

    def vector_candidates(
        self,
        course_id: int,
        query_vector: list[float],
        *,
        embedding_source: str,
        embedding_model: str,
        limit: int,
    ) -> list[tuple[KnowledgeChunk, float]]:
        distance = KnowledgeChunk.embedding.cosine_distance(query_vector)
        statement = (
            select(KnowledgeChunk, distance.label("distance"))
            .where(
                KnowledgeChunk.course_id == course_id,
                KnowledgeChunk.embedding.is_not(None),
                KnowledgeChunk.metadata_json["embedding_source"].as_string() == embedding_source,
                KnowledgeChunk.metadata_json["embedding_model"].as_string() == embedding_model,
            )
            .options(selectinload(KnowledgeChunk.material), selectinload(KnowledgeChunk.knowledge_point))
            .order_by(distance.asc(), KnowledgeChunk.id.asc())
            .limit(limit)
        )
        return [(row[0], float(row[1])) for row in self.db.execute(statement).all()]


class RagService:
    generic_terms = {"问题", "这个", "那个", "什么"}

    def __init__(self, repository: SqlAlchemyRagRepository, embedding_service: RagEmbeddingService | None = None) -> None:
        self.repository = repository
        self.embedding_service = embedding_service

    def search(self, user: User, course_id: int, query: str, top_k: int = 5) -> RagSearchResponse:
        cleaned_query = query.strip()
        if not cleaned_query:
            raise RagValidationError("检索问题不能为空。")
        if top_k < 1 or top_k > 10:
            raise RagValidationError("top_k 必须在 1 到 10 之间。")

        course = self.repository.get_course_for_user(user.id, course_id)
        if course is None:
            raise RagCourseNotFoundError("课程不存在或无权访问。")

        terms = self._query_terms(cleaned_query)
        chunks = self.repository.list_searchable_chunks(course.id)
        embedding_status = "unavailable"
        retrieval_mode = "keyword"
        if self.embedding_service is not None:
            self._ensure_chunk_embeddings(user, chunks)
        query_embedding = self._query_embedding(user, cleaned_query)
        vector_candidates: dict[int, tuple[KnowledgeChunk, float]] = {}
        if query_embedding is not None:
            embedding_status = query_embedding["status"]
        if query_embedding is not None and query_embedding.get("vector") is not None:
            embedding_status = query_embedding["status"]
            retrieval_mode = "hybrid"
            vector_search = getattr(self.repository, "vector_candidates", None)
            if callable(vector_search):
                rows = vector_search(
                    course.id,
                    query_embedding["vector"],
                    embedding_source=query_embedding["source"],
                    embedding_model=query_embedding["model"],
                    limit=max(top_k * 4, 12),
                )
                vector_candidates = {chunk.id: (chunk, max(0.0, 1.0 - distance)) for chunk, distance in rows}

        chunks_by_id = {chunk.id: chunk for chunk in chunks}
        chunks_by_id.update({chunk_id: row[0] for chunk_id, row in vector_candidates.items()})
        scored_chunks = []
        for chunk in chunks_by_id.values():
            keyword_score = self._score_chunk(chunk, cleaned_query, terms)
            vector_score = round(vector_candidates.get(chunk.id, (chunk, 0.0))[1] * 6.0, 4)
            score = round(keyword_score + vector_score, 4)
            if keyword_score <= 0 and vector_score < 0.25:
                continue
            scored_chunks.append(
                ScoredChunk(
                    chunk=chunk,
                    score=score,
                    keyword_score=keyword_score,
                    vector_score=vector_score,
                    retrieval_source=self._retrieval_source(keyword_score, vector_score),
                    embedding_status=embedding_status,
                )
            )
        scored_chunks.sort(key=lambda item: (-item.score, -item.vector_score, item.chunk.id))

        return RagSearchResponse(
            course_id=course.id,
            query=cleaned_query,
            top_k=top_k,
            results=[
                self._build_result(
                    item.chunk,
                    item.score,
                    keyword_score=item.keyword_score,
                    vector_score=item.vector_score,
                    retrieval_source=item.retrieval_source,
                    embedding_status=item.embedding_status,
                )
                for item in scored_chunks[:top_k]
            ],
            retrieval_mode=retrieval_mode,
            embedding_status=embedding_status,
        )

    def _query_embedding(self, user: User, query: str) -> dict[str, Any] | None:
        if self.embedding_service is None:
            return None
        try:
            batch = self.embedding_service.embed_texts(user, [query])
        except Exception:
            return None
        vectors = list(getattr(batch, "vectors", []))
        status = str(getattr(batch, "status", "unavailable"))
        source = str(getattr(batch, "source", "unknown"))
        model = str(getattr(batch, "model", "unknown"))
        dimension = int(getattr(batch, "dimension", EMBEDDING_DIMENSION))
        if status != "completed":
            return {"vector": None, "status": status, "source": source, "model": model}
        if len(vectors) != 1 or dimension != EMBEDDING_DIMENSION or not self._valid_vector(vectors[0]):
            return {"vector": None, "status": "provider_failed", "source": source, "model": model}
        return {"vector": vectors[0], "status": status, "source": source, "model": model}

    def _ensure_chunk_embeddings(self, user: User, chunks: list[KnowledgeChunk]) -> None:
        if self.embedding_service is None or not chunks:
            return
        try:
            expected_metadata = getattr(self.embedding_service, "expected_metadata", None)
            if callable(expected_metadata):
                expected_source, expected_model, _ = expected_metadata(user)
                if expected_source == "local" or expected_model == "local-hash-1536":
                    return
            needs_embedding = getattr(self.embedding_service, "chunk_needs_embedding", None)
            if callable(needs_embedding):
                target_chunks = [chunk for chunk in chunks if needs_embedding(user, chunk)]
            else:
                target_chunks = [chunk for chunk in chunks if not self._valid_vector(chunk.embedding)]
            if not target_chunks:
                return

            apply_embeddings = getattr(self.embedding_service, "apply_embeddings", None)
            if callable(apply_embeddings):
                batch = apply_embeddings(user, target_chunks)
            else:
                batch = self.embedding_service.embed_texts(user, [chunk.content for chunk in target_chunks])
                self._apply_batch_to_chunks(batch, target_chunks)
            vectors = list(getattr(batch, "vectors", []))
            if len(vectors) == len(target_chunks):
                self.repository.save_chunk_embeddings(target_chunks)
        except Exception:
            return

    @staticmethod
    def _apply_batch_to_chunks(batch: Any, chunks: list[KnowledgeChunk]) -> None:
        vectors = list(getattr(batch, "vectors", []))
        if len(vectors) != len(chunks):
            return
        source = str(getattr(batch, "source", "unknown"))
        model = str(getattr(batch, "model", "unknown"))
        dimension = int(getattr(batch, "dimension", EMBEDDING_DIMENSION))
        for chunk, vector in zip(chunks, vectors, strict=True):
            if len(vector) != dimension:
                continue
            chunk.embedding = vector
            chunk.metadata_json = {
                **(chunk.metadata_json or {}),
                "embedding_source": source,
                "embedding_model": model,
                "embedding_dimension": dimension,
            }

    @staticmethod
    def _valid_vector(vector: list[float] | None) -> bool:
        return isinstance(vector, list) and len(vector) == EMBEDDING_DIMENSION

    @classmethod
    def _vector_score(cls, query_vector: list[float], chunk_vector: list[float] | None) -> float:
        if not cls._valid_vector(chunk_vector):
            return 0.0
        similarity = cls._cosine_similarity(query_vector, chunk_vector)
        return round(max(similarity, 0.0) * 6.0, 4)

    @staticmethod
    def _cosine_similarity(left: list[float], right: list[float]) -> float:
        dot = sum(a * b for a, b in zip(left, right, strict=True))
        left_norm = math.sqrt(sum(value * value for value in left))
        right_norm = math.sqrt(sum(value * value for value in right))
        if left_norm == 0 or right_norm == 0:
            return 0.0
        return dot / (left_norm * right_norm)

    @staticmethod
    def _retrieval_source(keyword_score: float, vector_score: float) -> str:
        if keyword_score > 0 and vector_score > 0:
            return "hybrid"
        if vector_score > 0:
            return "vector"
        return "keyword"

    @classmethod
    def _query_terms(cls, query: str) -> list[str]:
        normalized = query.lower()
        terms: list[str] = []

        for term in cls._split_terms(normalized):
            if term not in cls.generic_terms and term not in terms:
                terms.append(term)
            if cls._is_chinese_text(term):
                for index in range(0, len(term) - 1):
                    bigram = term[index : index + 2]
                    if bigram not in cls.generic_terms and bigram not in terms:
                        terms.append(bigram)
        return terms

    @classmethod
    def _split_terms(cls, value: str) -> list[str]:
        terms: list[str] = []
        buffer: list[str] = []
        buffer_kind: str | None = None

        def flush() -> None:
            nonlocal buffer, buffer_kind
            if buffer:
                terms.append("".join(buffer))
            buffer = []
            buffer_kind = None

        for char in value:
            if char.isascii() and char.isalnum():
                kind = "ascii"
            elif cls._is_chinese_char(char):
                kind = "chinese"
            else:
                flush()
                continue

            if buffer_kind is not None and buffer_kind != kind:
                flush()
            buffer_kind = kind
            buffer.append(char)

        flush()
        return terms

    @staticmethod
    def _is_chinese_char(value: str) -> bool:
        code_point = ord(value)
        return 0x4E00 <= code_point <= 0x9FFF

    @staticmethod
    def _is_chinese_text(value: str) -> bool:
        return all(RagService._is_chinese_char(char) for char in value)

    @classmethod
    def _score_chunk(cls, chunk: KnowledgeChunk, query: str, terms: list[str]) -> float:
        haystack = cls._search_text(chunk)
        score = 0.0
        if query.lower() in haystack:
            score += 4.0

        for term in terms:
            if term and term in haystack:
                score += 1.0 if len(term) <= 2 else 2.0

        if cls._ordered_chinese_query_matches(query, haystack):
            score += 1.5
        if chunk.section_title and query.lower() in chunk.section_title.lower():
            score += 1.5
        if chunk.knowledge_point and query.lower() in chunk.knowledge_point.title.lower():
            score += 1.5

        return round(score, 4)

    @classmethod
    def _ordered_chinese_query_matches(cls, query: str, haystack: str) -> bool:
        chars = [char for char in query if cls._is_chinese_char(char)]
        if len(chars) < 3:
            return False

        start = 0
        for char in chars:
            found_at = haystack.find(char, start)
            if found_at < 0:
                return False
            start = found_at + 1
        return True

    @staticmethod
    def _search_text(chunk: KnowledgeChunk) -> str:
        parts = [
            chunk.content,
            chunk.section_title or "",
            chunk.material.filename if chunk.material else "",
            chunk.knowledge_point.title if chunk.knowledge_point else "",
            chunk.knowledge_point.chapter if chunk.knowledge_point and chunk.knowledge_point.chapter else "",
        ]
        return " ".join(parts).lower()

    @staticmethod
    def _build_result(
        chunk: KnowledgeChunk,
        score: float,
        keyword_score: float = 0.0,
        vector_score: float = 0.0,
        retrieval_source: str = "keyword",
        embedding_status: str = "unavailable",
    ) -> RagSearchResultItem:
        source_title = ""
        if chunk.material is not None:
            source_title = chunk.material.filename
        if not source_title:
            source_title = str((chunk.metadata_json or {}).get("source_filename") or f"资料 {chunk.material_id}")

        return RagSearchResultItem(
            chunk_id=chunk.id,
            course_id=chunk.course_id,
            material_id=chunk.material_id,
            knowledge_point_id=chunk.knowledge_point_id,
            content=chunk.content,
            source_title=source_title,
            page_number=chunk.page_number,
            section_title=chunk.section_title,
            score=score,
            keyword_score=keyword_score,
            vector_score=vector_score,
            retrieval_source=retrieval_source,
            embedding_status=embedding_status,
        )

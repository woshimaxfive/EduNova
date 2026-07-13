from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
import re
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import Material, MaterialChunk, User
from backend.app.services.embeddings import EmbeddingService
from backend.app.services.model_settings import ModelNotConfiguredError


MATERIAL_CHUNK_SIZE = 800
MATERIAL_CHUNK_OVERLAP = 120


@dataclass(frozen=True)
class MaterialRetrievalResult:
    citations: list[dict[str, Any]]
    retrieval_mode: str
    embedding_status: str
    rerank_status: str = "not_configured"


class MaterialChunkingService:
    def build_chunks(self, material: Material) -> list[MaterialChunk]:
        text = str(material.extracted_text or "").strip()
        if material.parse_status != "completed" or not text or material.id is None:
            return []

        sections = (
            self._markdown_sections(text)
            if Path(material.filename).suffix.lower() in {".md", ".markdown"}
            else self._plain_sections(text)
        )
        chunks: list[MaterialChunk] = []
        for section_title, section_text, section_metadata in sections:
            for content in self._split_text(section_text):
                chunks.append(
                    MaterialChunk(
                        material_id=material.id,
                        chunk_index=len(chunks),
                        section_title=section_title,
                        page_number=None,
                        content=content,
                        embedding=None,
                        metadata_json={"source_filename": material.filename, **section_metadata},
                    )
                )
        return chunks

    def _markdown_sections(self, text: str) -> list[tuple[str | None, str, dict[str, Any]]]:
        lines = text.replace("\r\n", "\n").splitlines()
        sections: list[tuple[str | None, str, dict[str, Any]]] = []
        current_title: str | None = None
        current_level = 1
        current_chapter: str | None = None
        current_lines: list[str] = []

        def flush() -> None:
            content = self._normalize_text("\n".join(current_lines))
            if content:
                sections.append(
                    (
                        current_title,
                        content,
                        {"section_level": current_level, "chapter_title": current_chapter},
                    )
                )

        for line in lines:
            match = re.match(r"^\s{0,3}#{1,3}\s+(.+?)\s*$", line)
            if match is None:
                current_lines.append(line)
                continue
            flush()
            current_title = match.group(1).strip()[:255]
            marker = line.lstrip().split(" ", 1)[0]
            current_level = len(marker)
            if current_level == 1:
                current_chapter = current_title
            current_lines = []
        flush()
        return sections or [(None, self._normalize_text(text), {})]

    def _plain_sections(self, text: str) -> list[tuple[str | None, str, dict[str, Any]]]:
        paragraphs = [self._normalize_text(part) for part in text.replace("\r\n", "\n").split("\n\n")]
        paragraphs = [paragraph for paragraph in paragraphs if paragraph]
        return [
            (f"第 {index} 部分", paragraph, {"section_level": 2, "chapter_title": None})
            for index, paragraph in enumerate(paragraphs, start=1)
        ] or [(None, self._normalize_text(text), {})]

    def _split_text(self, text: str) -> list[str]:
        normalized = self._normalize_text(text)
        if not normalized:
            return []
        if len(normalized) <= MATERIAL_CHUNK_SIZE:
            return [normalized]

        chunks: list[str] = []
        start = 0
        while start < len(normalized):
            hard_end = min(start + MATERIAL_CHUNK_SIZE, len(normalized))
            end = hard_end
            if hard_end < len(normalized):
                search_start = start + int(MATERIAL_CHUNK_SIZE * 0.6)
                punctuation = max(
                    normalized.rfind("。", search_start, hard_end),
                    normalized.rfind("！", search_start, hard_end),
                    normalized.rfind("？", search_start, hard_end),
                    normalized.rfind("；", search_start, hard_end),
                    normalized.rfind(" ", search_start, hard_end),
                )
                if punctuation > start:
                    end = punctuation + 1
            chunk = normalized[start:end].strip()
            if chunk:
                chunks.append(chunk)
            if end >= len(normalized):
                break
            start = max(end - MATERIAL_CHUNK_OVERLAP, start + 1)
        return chunks

    @staticmethod
    def _normalize_text(text: str) -> str:
        return re.sub(r"\s+", " ", text).strip()


class MaterialRetrievalRepository(Protocol):
    def list_materials(self, user_id: int, material_ids: list[int]) -> list[Material]: ...

    def list_chunks(self, material_ids: list[int]) -> list[MaterialChunk]: ...

    def add_chunks(self, chunks: list[MaterialChunk]) -> None: ...

    def save_chunks(self) -> None: ...

    def vector_candidates(
        self,
        user_id: int,
        material_ids: list[int],
        query_vector: list[float],
        embedding_provider: str,
        embedding_model: str,
        embedding_dimension: int,
        embedding_profile_hash: str,
        limit: int,
    ) -> list[tuple[MaterialChunk, float]]: ...


class SqlAlchemyMaterialRetrievalRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_materials(self, user_id: int, material_ids: list[int]) -> list[Material]:
        if not material_ids:
            return []
        return list(
            self.db.scalars(
                select(Material)
                .where(Material.user_id == user_id, Material.id.in_(material_ids))
                .order_by(Material.id)
            )
        )

    def list_chunks(self, material_ids: list[int]) -> list[MaterialChunk]:
        if not material_ids:
            return []
        return list(
            self.db.scalars(
                select(MaterialChunk)
                .where(MaterialChunk.material_id.in_(material_ids))
                .order_by(MaterialChunk.material_id, MaterialChunk.chunk_index)
            )
        )

    def add_chunks(self, chunks: list[MaterialChunk]) -> None:
        self.db.add_all(chunks)
        self.db.flush()

    def save_chunks(self) -> None:
        self.db.commit()

    def vector_candidates(
        self,
        user_id: int,
        material_ids: list[int],
        query_vector: list[float],
        *,
        embedding_provider: str,
        embedding_model: str,
        embedding_dimension: int,
        embedding_profile_hash: str,
        limit: int,
    ) -> list[tuple[MaterialChunk, float]]:
        if not material_ids:
            return []
        distance = MaterialChunk.embedding.cosine_distance(query_vector)
        rows = self.db.execute(
            select(MaterialChunk, distance.label("distance"))
            .join(Material, Material.id == MaterialChunk.material_id)
            .where(
                Material.user_id == user_id,
                Material.id.in_(material_ids),
                MaterialChunk.embedding.is_not(None),
                MaterialChunk.embedding_provider == embedding_provider,
                MaterialChunk.embedding_model == embedding_model,
                MaterialChunk.embedding_dimension == embedding_dimension,
                MaterialChunk.embedding_profile_hash == embedding_profile_hash,
            )
            .order_by(distance)
            .limit(limit)
        ).all()
        return [(row[0], float(row[1])) for row in rows]


class MaterialRetrievalService:
    def __init__(
        self,
        repository: MaterialRetrievalRepository,
        embedding_service: EmbeddingService | None = None,
        chunking_service: MaterialChunkingService | None = None,
        rerank_service: Any | None = None,
    ) -> None:
        self.repository = repository
        self.embedding_service = embedding_service
        self.chunking_service = chunking_service or MaterialChunkingService()
        self.rerank_service = rerank_service

    def search(
        self,
        user: User,
        material_ids: list[int],
        query: str,
        top_k: int = 5,
    ) -> MaterialRetrievalResult:
        unique_ids = list(dict.fromkeys(item for item in material_ids if item > 0))[:10]
        cleaned_query = query.strip()
        if not unique_ids or not cleaned_query:
            return MaterialRetrievalResult(citations=[], retrieval_mode="none", embedding_status="unavailable")

        materials = self.repository.list_materials(user.id, unique_ids)
        searchable_materials = [
            item for item in materials if item.parse_status == "completed" and str(item.extracted_text or "").strip()
        ]
        searchable_ids = [item.id for item in searchable_materials if item.id is not None]
        chunks = self.repository.list_chunks(searchable_ids)
        existing_ids = {chunk.material_id for chunk in chunks}
        new_chunks = [
            chunk
            for material in searchable_materials
            if material.id not in existing_ids
            for chunk in self.chunking_service.build_chunks(material)
        ]
        if new_chunks:
            self.repository.add_chunks(new_chunks)
            self.repository.save_chunks()
            chunks.extend(new_chunks)
        if not chunks:
            return MaterialRetrievalResult(citations=[], retrieval_mode="keyword", embedding_status="unavailable")

        embedding_status, query_vector, embedding_profile = self._ensure_embeddings(user, chunks, cleaned_query)
        vector_candidates: dict[int, float] = {}
        if query_vector is not None:
            for chunk, distance in self.repository.vector_candidates(
                user.id,
                searchable_ids,
                query_vector,
                embedding_provider=embedding_profile[0],
                embedding_model=embedding_profile[1],
                embedding_dimension=embedding_profile[2],
                embedding_profile_hash=embedding_profile[3],
                limit=30,
            ):
                if chunk.id is not None:
                    vector_candidates[chunk.id] = max(0.0, min(1.0, 1.0 - distance))

        terms = self._query_terms(cleaned_query)
        keyword_rows = sorted(
            [(chunk, self._keyword_score(chunk, cleaned_query, terms)) for chunk in chunks],
            key=lambda item: (-item[1], item[0].material_id, item[0].chunk_index),
        )
        keyword_rows = [item for item in keyword_rows if item[1] > 0][:30]
        vector_rows = sorted(
            [(chunk, vector_candidates.get(chunk.id or -1, 0.0)) for chunk in chunks if (chunk.id or -1) in vector_candidates],
            key=lambda item: (-item[1], item[0].material_id, item[0].chunk_index),
        )[:30]
        rrf: dict[int, float] = {}
        by_id: dict[int, MaterialChunk] = {}
        keyword_scores = {chunk.id: score for chunk, score in keyword_rows}
        vector_scores = {chunk.id: score for chunk, score in vector_rows}
        for rank, (chunk, _) in enumerate(keyword_rows, start=1):
            if chunk.id is None:
                continue
            by_id[chunk.id] = chunk
            rrf[chunk.id] = rrf.get(chunk.id, 0.0) + 1.0 / (60 + rank)
        for rank, (chunk, _) in enumerate(vector_rows, start=1):
            if chunk.id is None:
                continue
            by_id[chunk.id] = chunk
            rrf[chunk.id] = rrf.get(chunk.id, 0.0) + 1.0 / (60 + rank)
        merged = sorted(rrf, key=lambda chunk_id: (-rrf[chunk_id], chunk_id))[:20]
        rerank_scores: dict[int, float] = {}
        rerank_status = "not_configured"
        if self.rerank_service is not None and merged:
            try:
                items = self.rerank_service.rerank_documents(
                    user,
                    cleaned_query,
                    [by_id[chunk_id].content for chunk_id in merged],
                    top_n=max(1, min(top_k, 5)),
                )
                rerank_scores = {merged[item.index]: float(item.score) for item in items}
                merged = [merged[item.index] for item in items]
                rerank_status = "completed"
            except ModelNotConfiguredError:
                rerank_status = "not_configured"
            except Exception:
                rerank_status = "provider_failed"
        scored = [
            (
                rerank_scores.get(chunk_id, rrf[chunk_id]),
                keyword_scores.get(chunk_id, 0.0),
                vector_scores.get(chunk_id, 0.0),
                by_id[chunk_id],
                rerank_scores.get(chunk_id),
            )
            for chunk_id in merged
        ]

        by_material = {item.id: item for item in searchable_materials}
        citations = [
            self._citation(
                by_material[item[3].material_id],
                item[3],
                item[0],
                item[1],
                item[2],
                embedding_status,
                embedding_profile,
                item[4],
                rerank_status,
            )
            for item in scored[: max(1, min(top_k, 10))]
        ]
        mode = "hybrid" if query_vector is not None else "keyword"
        return MaterialRetrievalResult(
            citations=citations,
            retrieval_mode=mode,
            embedding_status=embedding_status,
            rerank_status=rerank_status,
        )

    def _ensure_embeddings(
        self,
        user: User,
        chunks: list[MaterialChunk],
        query: str,
    ) -> tuple[str, list[float] | None, tuple[str, str, int, str]]:
        if self.embedding_service is None:
            return "unavailable", None, ("", "", 0, "")
        try:
            profile = self.embedding_service.expected_profile(user)
            if profile is None:
                return "local_fallback", None, ("", "", 0, "")
            expected_source, expected_model, expected_dimension = profile.provider, profile.model, profile.dimension
            targets = [
                chunk
                for chunk in chunks
                if not self._valid_vector(chunk.embedding)
                or chunk.embedding_provider != expected_source
                or chunk.embedding_model != expected_model
                or chunk.embedding_dimension != expected_dimension
                or chunk.embedding_profile_hash != profile.profile_hash
            ]
            if targets:
                batch = self.embedding_service.embed_documents(user, [chunk.content for chunk in targets])
                self._apply_embeddings(targets, batch)
                if len(getattr(batch, "vectors", [])) == len(targets):
                    self.repository.save_chunks()
            query_batch = self.embedding_service.embed_query(user, query)
            vectors = list(getattr(query_batch, "vectors", []))
            status = str(getattr(query_batch, "status", "unavailable"))
            if len(vectors) == 1 and self._valid_vector(vectors[0]):
                return status, vectors[0], (profile.provider, profile.model, profile.dimension, profile.profile_hash)
            return status, None, (profile.provider, profile.model, profile.dimension, profile.profile_hash)
        except Exception:
            return "provider_failed", None, ("", "", 0, "")

    @staticmethod
    def _apply_embeddings(chunks: list[MaterialChunk], batch: Any) -> None:
        vectors = list(getattr(batch, "vectors", []))
        dimension = int(getattr(batch, "dimension", 0))
        profile_hash = str(getattr(batch, "profile_hash", ""))
        if len(vectors) != len(chunks) or dimension <= 0:
            return
        embedded_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        for chunk, vector in zip(chunks, vectors, strict=True):
            if not MaterialRetrievalService._valid_vector(vector):
                continue
            chunk.embedding = vector
            chunk.embedding_provider = str(getattr(batch, "source", "unknown"))
            chunk.embedding_model = str(getattr(batch, "model", "unknown"))
            chunk.embedding_dimension = dimension
            chunk.embedding_profile_hash = profile_hash
            chunk.embedding_updated_at = datetime.now(UTC)
            chunk.metadata_json = {
                **(chunk.metadata_json or {}),
                "embedding_source": str(getattr(batch, "source", "unknown")),
                "embedding_model": str(getattr(batch, "model", "unknown")),
                "embedding_dimension": dimension,
                "embedded_at": embedded_at,
            }

    @staticmethod
    def _keyword_score(chunk: MaterialChunk, query: str, terms: list[str]) -> float:
        content = chunk.content.lower()
        title = str(chunk.section_title or "").lower()
        normalized_query = query.lower()
        score = 0.0
        if normalized_query in title:
            score += 5.0
        if normalized_query in content:
            score += 4.0
        for term in terms:
            if term in title:
                score += 1.5
            score += min(content.count(term), 3) * 0.35
        return round(score, 4)

    @staticmethod
    def _query_terms(query: str) -> list[str]:
        lowered = query.lower()
        ascii_terms = re.findall(r"[a-z0-9]+", lowered)
        chinese_groups = re.findall(r"[一-鿿]+", lowered)
        terms = list(ascii_terms)
        for group in chinese_groups:
            terms.append(group)
            if len(group) > 2:
                terms.extend(group[index : index + 2] for index in range(len(group) - 1))
        return list(dict.fromkeys(term for term in terms if term))

    @staticmethod
    def _valid_vector(vector: Any) -> bool:
        return isinstance(vector, list) and bool(vector)

    @staticmethod
    def _citation(
        material: Material,
        chunk: MaterialChunk,
        score: float,
        keyword_score: float,
        vector_score: float,
        embedding_status: str,
        embedding_profile: tuple[str, str, int, str],
        rerank_score: float | None,
        rerank_status: str,
    ) -> dict[str, Any]:
        if keyword_score > 0 and vector_score > 0:
            retrieval_source = "hybrid"
        elif vector_score > 0:
            retrieval_source = "vector"
        else:
            retrieval_source = "keyword"
        return {
            "source_type": "material",
            "material_id": str(material.id),
            "title": material.filename,
            "section_title": chunk.section_title,
            "page_number": chunk.page_number,
            "snippet": chunk.content[:500],
            "score": round(score, 4),
            "retrieval_source": retrieval_source,
            "embedding_status": embedding_status,
            "embedding_provider": embedding_profile[0] or None,
            "embedding_dimension": embedding_profile[2] or None,
            "rerank_score": round(rerank_score, 6) if rerank_score is not None else None,
            "rerank_status": rerank_status,
        }

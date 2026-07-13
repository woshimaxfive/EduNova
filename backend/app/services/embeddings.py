from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from backend.app.models import KnowledgeChunk, User
from backend.app.providers.openai_compatible import ModelProviderError
from backend.app.services.model_settings import ModelNotConfiguredError, ModelSettingsService


# Legacy compatibility only. New vector profiles use their actual Provider dimension.
EMBEDDING_DIMENSION = 1536
LOCAL_EMBEDDING_MODEL = "keyword-only"


@dataclass(frozen=True)
class EmbeddingProfile:
    provider: str
    model: str
    dimension: int
    profile_hash: str


@dataclass(frozen=True)
class EmbeddingBatch:
    vectors: list[list[float]]
    source: str
    model: str
    dimension: int
    status: str
    profile_hash: str = ""


class EmbeddingService:
    def __init__(self, model_settings_service: ModelSettingsService | None = None) -> None:
        self.model_settings_service = model_settings_service

    def embed_documents(self, user: User, texts: list[str]) -> EmbeddingBatch:
        return self._embed(user, texts, input_type="document")

    def embed_query(self, user: User, text: str) -> EmbeddingBatch:
        return self._embed(user, [text], input_type="query")

    def embed_texts(self, user: User, texts: list[str]) -> EmbeddingBatch:
        return self.embed_documents(user, texts)

    def _embed(self, user: User, texts: list[str], *, input_type: str) -> EmbeddingBatch:
        cleaned_texts = [text for text in texts if text.strip()]
        if not cleaned_texts:
            return EmbeddingBatch(vectors=[], source="none", model="", dimension=0, status="empty")
        if self.model_settings_service is None:
            return self._keyword_fallback()

        runtime = self.model_settings_service.resolve_embedding_runtime_config(user)
        if not runtime.can_use_model or not runtime.embedding_model:
            return self._keyword_fallback()
        try:
            vectors = self.model_settings_service.embedding_vectors(
                user,
                cleaned_texts,
                dimensions=runtime.dimensions,
                input_type="query" if input_type == "query" else "document",
            )
        except ModelNotConfiguredError:
            return self._keyword_fallback()
        except ModelProviderError:
            return EmbeddingBatch(
                vectors=[],
                source=runtime.provider,
                model=runtime.embedding_model,
                dimension=runtime.dimensions or 0,
                status="provider_failed",
                profile_hash=runtime.profile_hash,
            )
        dimension = len(vectors[0]) if vectors else 0
        return EmbeddingBatch(
            vectors=vectors,
            source=runtime.provider,
            model=runtime.embedding_model,
            dimension=dimension,
            status="completed",
            profile_hash=runtime.profile_hash,
        )

    def apply_embeddings(self, user: User, chunks: list[KnowledgeChunk]) -> EmbeddingBatch:
        target_chunks = [chunk for chunk in chunks if chunk.content.strip()]
        batch = self.embed_documents(user, [chunk.content for chunk in target_chunks])
        if not batch.vectors or len(batch.vectors) != len(target_chunks) or batch.dimension <= 0:
            return batch

        embedded_at = datetime.now(UTC)
        embedded_at_text = embedded_at.replace(microsecond=0).isoformat().replace("+00:00", "Z")
        for chunk, vector in zip(target_chunks, batch.vectors, strict=True):
            if len(vector) != batch.dimension:
                continue
            chunk.embedding = vector
            chunk.embedding_provider = batch.source
            chunk.embedding_model = batch.model
            chunk.embedding_dimension = batch.dimension
            chunk.embedding_profile_hash = batch.profile_hash
            chunk.embedding_updated_at = embedded_at
            chunk.metadata_json = {
                **(chunk.metadata_json or {}),
                "embedding_source": batch.source,
                "embedding_model": batch.model,
                "embedding_dimension": batch.dimension,
                "embedding_profile_hash": batch.profile_hash,
                "embedded_at": embedded_at_text,
            }
        return batch

    def chunk_needs_embedding(self, user: User, chunk: KnowledgeChunk) -> bool:
        profile = self.expected_profile(user)
        if profile is None:
            return False
        return (
            not self._valid_vector(chunk.embedding, chunk.embedding_dimension)
            or chunk.embedding_provider != profile.provider
            or chunk.embedding_model != profile.model
            or chunk.embedding_dimension != profile.dimension
            or chunk.embedding_profile_hash != profile.profile_hash
        )

    def expected_profile(self, user: User) -> EmbeddingProfile | None:
        if self.model_settings_service is None:
            return None
        runtime = self.model_settings_service.resolve_embedding_runtime_config(user)
        if not runtime.can_use_model or not runtime.embedding_model:
            return None
        dimension = runtime.dimensions or EMBEDDING_DIMENSION
        return EmbeddingProfile(runtime.provider, runtime.embedding_model, dimension, runtime.profile_hash)

    def expected_metadata(self, user: User) -> tuple[str, str, int]:
        profile = self.expected_profile(user)
        if profile is None:
            return "local", LOCAL_EMBEDDING_MODEL, 0
        return profile.provider, profile.model, profile.dimension

    @staticmethod
    def _valid_vector(vector: list[float] | None, dimension: int | None = None) -> bool:
        return isinstance(vector, list) and bool(vector) and (dimension is None or len(vector) == dimension)

    @staticmethod
    def _keyword_fallback() -> EmbeddingBatch:
        return EmbeddingBatch(
            vectors=[],
            source="local",
            model=LOCAL_EMBEDDING_MODEL,
            dimension=0,
            status="local_fallback",
        )

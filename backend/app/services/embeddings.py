from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import math

from backend.app.models import KnowledgeChunk, User
from backend.app.providers.openai_compatible import ModelProviderError
from backend.app.services.model_settings import ModelNotConfiguredError, ModelSettingsService


EMBEDDING_DIMENSION = 1536
LOCAL_EMBEDDING_MODEL = "local-hash-1536"


@dataclass(frozen=True)
class EmbeddingBatch:
    vectors: list[list[float]]
    source: str
    model: str
    dimension: int
    status: str


class EmbeddingService:
    def __init__(self, model_settings_service: ModelSettingsService | None = None) -> None:
        self.model_settings_service = model_settings_service

    def embed_texts(self, user: User, texts: list[str]) -> EmbeddingBatch:
        cleaned_texts = [text for text in texts if text.strip()]
        if not cleaned_texts:
            return EmbeddingBatch(vectors=[], source="none", model="", dimension=EMBEDDING_DIMENSION, status="empty")

        if self.model_settings_service is not None:
            runtime = self.model_settings_service.resolve_embedding_runtime_config(user)
            if runtime.can_use_model and runtime.embedding_model:
                try:
                    vectors = self.model_settings_service.embedding_vectors(user, cleaned_texts, dimensions=EMBEDDING_DIMENSION)
                except ModelNotConfiguredError:
                    pass
                except ModelProviderError:
                    return EmbeddingBatch(
                        vectors=[],
                        source=runtime.source,
                        model=runtime.embedding_model,
                        dimension=EMBEDDING_DIMENSION,
                        status="provider_failed",
                    )
                else:
                    return EmbeddingBatch(
                        vectors=vectors,
                        source=runtime.source,
                        model=runtime.embedding_model,
                        dimension=EMBEDDING_DIMENSION,
                        status="completed",
                    )

        return EmbeddingBatch(
            vectors=[self._local_hash_vector(text) for text in cleaned_texts],
            source="local",
            model=LOCAL_EMBEDDING_MODEL,
            dimension=EMBEDDING_DIMENSION,
            status="local_fallback",
        )

    def apply_embeddings(self, user: User, chunks: list[KnowledgeChunk]) -> EmbeddingBatch:
        target_chunks = [chunk for chunk in chunks if chunk.content.strip()]
        batch = self.embed_texts(user, [chunk.content for chunk in target_chunks])
        if len(batch.vectors) != len(target_chunks) or batch.dimension != EMBEDDING_DIMENSION:
            return batch

        embedded_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        for chunk, vector in zip(target_chunks, batch.vectors, strict=True):
            if len(vector) != EMBEDDING_DIMENSION:
                continue
            chunk.embedding = vector
            chunk.metadata_json = {
                **(chunk.metadata_json or {}),
                "embedding_source": batch.source,
                "embedding_model": batch.model,
                "embedding_dimension": batch.dimension,
                "embedded_at": embedded_at,
            }
        return batch

    def chunk_needs_embedding(self, user: User, chunk: KnowledgeChunk) -> bool:
        if not self._valid_vector(chunk.embedding):
            return True
        source, model, dimension = self.expected_metadata(user)
        metadata = chunk.metadata_json or {}
        return (
            metadata.get("embedding_source") != source
            or metadata.get("embedding_model") != model
            or metadata.get("embedding_dimension") != dimension
        )

    def expected_metadata(self, user: User) -> tuple[str, str, int]:
        if self.model_settings_service is not None:
            runtime = self.model_settings_service.resolve_embedding_runtime_config(user)
            if runtime.can_use_model and runtime.embedding_model:
                return runtime.source, runtime.embedding_model, EMBEDDING_DIMENSION
        return "local", LOCAL_EMBEDDING_MODEL, EMBEDDING_DIMENSION

    @staticmethod
    def _valid_vector(vector: list[float] | None) -> bool:
        return isinstance(vector, list) and len(vector) == EMBEDDING_DIMENSION

    @classmethod
    def _local_hash_vector(cls, text: str) -> list[float]:
        vector = [0.0] * EMBEDDING_DIMENSION
        tokens = cls._tokens(text)
        if not tokens:
            tokens = [text.strip().lower() or "empty"]

        for token in tokens:
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=16).digest()
            index = int.from_bytes(digest[:4], "big") % EMBEDDING_DIMENSION
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            weight = 1.0 + (digest[5] / 255.0)
            vector[index] += sign * weight

        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [round(value / norm, 8) for value in vector]

    @classmethod
    def _tokens(cls, value: str) -> list[str]:
        normalized = value.lower()
        terms: list[str] = []
        buffer: list[str] = []
        buffer_kind: str | None = None

        def flush() -> None:
            nonlocal buffer, buffer_kind
            if buffer:
                terms.append("".join(buffer))
            buffer = []
            buffer_kind = None

        for char in normalized:
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
        expanded: list[str] = []
        for term in terms:
            expanded.append(term)
            if cls._is_chinese_text(term):
                expanded.extend(term[index : index + 2] for index in range(0, len(term) - 1))
        return expanded

    @staticmethod
    def _is_chinese_char(value: str) -> bool:
        code_point = ord(value)
        return 0x4E00 <= code_point <= 0x9FFF

    @classmethod
    def _is_chinese_text(cls, value: str) -> bool:
        return all(cls._is_chinese_char(char) for char in value)

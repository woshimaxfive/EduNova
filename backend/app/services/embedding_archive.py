"""Transactional vector replacement using existing SQLAlchemy/pgvector storage."""
from datetime import UTC, datetime
from hashlib import sha256

import numpy as np
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from backend.app.models import ChunkEmbeddingArchive, Course, KnowledgeChunk, Material, MaterialChunk
from backend.app.services.embeddings import EmbeddingProfile
from backend.app.services.ai_job_contracts import AiJobValidationError


class EmbeddingArchiveService:
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def content_hash(content: str) -> str:
        return sha256(content.encode("utf-8")).hexdigest()

    @staticmethod
    def _field(chunk):
        if isinstance(chunk, KnowledgeChunk):
            return ChunkEmbeddingArchive.knowledge_chunk_id
        if isinstance(chunk, MaterialChunk):
            return ChunkEmbeddingArchive.material_chunk_id
        raise TypeError("未知资料片段类型")

    def owned_chunk(self, user_id: int, chunk, *, lock: bool = False):
        model = type(chunk)
        if model is KnowledgeChunk:
            parent, condition, owner = Course, Course.id == KnowledgeChunk.course_id, Course.owner_id
        elif model is MaterialChunk:
            parent, condition, owner = Material, Material.id == MaterialChunk.material_id, Material.user_id
        else:
            raise TypeError("未知资料片段类型")
        statement = select(model).join(parent, condition).where(model.id == chunk.id, owner == user_id)
        if lock:
            statement = statement.with_for_update(of=(model, parent))
        result = self.db.scalar(statement.execution_options(populate_existing=True))
        if result is None:
            raise AiJobValidationError("资料片段不存在或无权重建。")
        return result

    def cached(self, user_id: int, chunk, profile: EmbeddingProfile, *, content_hash: str) -> list[float] | None:
        chunk = self.owned_chunk(user_id, chunk)
        if self.content_hash(chunk.content) != content_hash:
            raise AiJobValidationError("资料发生变化，请重新提交重建。")
        archive = self.db.scalar(select(ChunkEmbeddingArchive).where(
            self._field(chunk) == chunk.id,
            ChunkEmbeddingArchive.content_hash == content_hash,
            ChunkEmbeddingArchive.profile_hash == profile.profile_hash,
            ChunkEmbeddingArchive.provider == profile.provider,
            ChunkEmbeddingArchive.model == profile.model,
            ChunkEmbeddingArchive.dimension == profile.dimension,
        ))
        return list(archive.embedding) if archive is not None else None

    @staticmethod
    def validate_vector(vector, dimension: int):
        values = np.asarray(vector, dtype=np.float32)
        if dimension <= 0 or values.shape != (dimension,) or not np.isfinite(values).all() or not np.any(values):
            raise AiJobValidationError("向量维度或数值无效，未替换旧索引。")
        return values.tolist()

    def replace(self, user_id: int, chunk, *, content_hash: str, profile: EmbeddingProfile, vector) -> None:
        values = self.validate_vector(vector, profile.dimension)
        current = self.owned_chunk(user_id, chunk, lock=True)
        if self.content_hash(current.content) != content_hash:
            raise AiJobValidationError("向量生成期间资料发生变化，请重新提交重建。")
        if current.embedding is not None:
            # Refuse to destroy ambiguous historical vectors rather than invent
            # their model identity or a restoration promise.
            if not all((current.embedding_provider, current.embedding_model,
                        current.embedding_dimension, current.embedding_profile_hash)):
                raise AiJobValidationError("旧向量缺少模型信息，不能安全归档，请先核对历史数据。")
            previous = self.validate_vector(current.embedding, current.embedding_dimension)
            self.db.execute(insert(ChunkEmbeddingArchive).values(
                **{self._field(current).key: current.id},
                content_hash=content_hash, profile_hash=current.embedding_profile_hash,
                provider=current.embedding_provider, model=current.embedding_model,
                dimension=current.embedding_dimension, embedding=previous,
                embedded_at=current.embedding_updated_at,
            ).on_conflict_do_nothing())
        current.embedding = values
        # pgvector hydrates numpy arrays; ORM equality cannot compare different
        # dimensions. This is an explicit replacement, so mark it unconditionally.
        flag_modified(current, "embedding")
        current.embedding_provider = profile.provider
        current.embedding_model = profile.model
        current.embedding_dimension = profile.dimension
        current.embedding_profile_hash = profile.profile_hash
        current.embedding_updated_at = datetime.now(UTC)
        current.metadata_json = {
            **(current.metadata_json or {}), "embedding_source": profile.provider,
            "embedding_model": profile.model, "embedding_dimension": profile.dimension,
            "embedding_profile_hash": profile.profile_hash,
            "embedded_at": current.embedding_updated_at.isoformat(),
        }
        self.db.add(current)
        # The caller owns the batch transaction, including rollback on cancel.
        self.db.flush()

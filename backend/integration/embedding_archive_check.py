"""Exercise reindex transactions on synthetic data in the isolated E2E database."""
from concurrent.futures import ThreadPoolExecutor
from importlib import import_module
from threading import Barrier
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import numpy as np
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import delete, func, select

from backend.app.core.config import get_settings
from backend.app.db.session import SessionLocal
from backend.app.models import ChunkEmbeddingArchive, Course, CourseMaterial, KnowledgeChunk, Material, MaterialChunk, User
from backend.app.services.ai_job_contracts import AiJobCancelled, AiJobValidationError
from backend.app.services.ai_job_execution import AiJobExecutionMixin
from backend.app.services.embedding_archive import EmbeddingArchiveService
from backend.app.services.embeddings import EmbeddingBatch, EmbeddingProfile, EmbeddingService


def run_check() -> None:
    old = EmbeddingProfile("test", "old", 3, "old-profile")
    new = EmbeddingProfile("test", "new", 2, "new-profile")
    third = EmbeddingProfile("test", "third", 2, "third-profile")
    db = SessionLocal()
    user_id = None
    try:
        owner = User(account=f"archive_{uuid4().hex[:12]}", hashed_password="integration-only",
                     display_name="archive fixture", role="student", starter_mode="blank")
        db.add(owner)
        db.flush()
        user_id = owner.id
        course = Course(owner_id=owner.id, title="archive fixture", status="ready")
        material = Material(user_id=owner.id, filename="archive.md", content_type="text/markdown",
                            storage_path="builtin://archive")
        db.add_all([course, material])
        db.flush()
        source = CourseMaterial(user_id=owner.id, course_id=course.id, filename="archive.md",
                                content_type="text/markdown", storage_path="builtin://archive")
        db.add(source)
        db.flush()
        fields = dict(content="队列按先进先出顺序处理元素。", embedding=[1, 0, 0],
                      embedding_provider=old.provider, embedding_model=old.model,
                      embedding_dimension=old.dimension, embedding_profile_hash=old.profile_hash)
        knowledge = KnowledgeChunk(course_id=course.id, material_id=source.id, **fields)
        standalone = MaterialChunk(material_id=material.id, chunk_index=0, **fields)
        db.add_all([knowledge, standalone])
        db.commit()
        service = EmbeddingArchiveService(db)
        digest = service.content_hash(knowledge.content)
        runner = SimpleNamespace(repository=SimpleNamespace(db=db), settings=get_settings())
        context = SimpleNamespace(check_cancelled=lambda: None, after_node=lambda **kwargs: None)

        def reindex(profile, vector=None, context_override=None):
            batch = EmbeddingBatch([vector, vector], profile.provider, profile.model, profile.dimension,
                                   "completed", profile.profile_hash)
            with patch.object(EmbeddingService, "expected_profile", return_value=profile), \
                    patch.object(EmbeddingService, "embed_documents", return_value=batch) as provider:
                result = AiJobExecutionMixin._run_embedding_reindex(runner, owner, None, context_override or context)
                assert result["embedded_chunk_count"] == 2
                return provider.call_count

        assert reindex(new, [0, 1]) == 1
        assert db.scalar(select(func.count()).select_from(ChunkEmbeddingArchive)) == 2
        assert reindex(old) == 0  # Cached restoration must not call an external model.
        for chunk in (knowledge, standalone):
            db.refresh(chunk)
            assert chunk.embedding_profile_hash == old.profile_hash
            assert np.allclose(chunk.embedding, [1, 0, 0])
        assert db.scalar(select(func.count()).select_from(ChunkEmbeddingArchive)) == 4

        # Cancellation after all writes but before commit rolls back this batch,
        # matching run_job's existing exception handler.
        calls = 0

        def cancel_before_commit():
            nonlocal calls
            calls += 1
            if calls == 3:
                raise AiJobCancelled()

        try:
            reindex(third, [1, 1], SimpleNamespace(check_cancelled=cancel_before_commit, after_node=context.after_node))
            raise AssertionError("cancellation was ignored")
        except AiJobCancelled:
            db.rollback()
        db.refresh(knowledge)
        assert knowledge.embedding_profile_hash == old.profile_hash
        assert db.scalar(select(func.count()).select_from(ChunkEmbeddingArchive)) == 4

        for action in (
            lambda: service.cached(user_id + 1, knowledge, old, content_hash=digest),
            lambda: service.replace(user_id, knowledge, content_hash="changed", profile=new, vector=[1, 0]),
            lambda: service.replace(user_id, knowledge, content_hash=digest, profile=new, vector=[float("nan"), 0]),
        ):
            try:
                action()
                raise AssertionError("unsafe replacement was accepted")
            except AiJobValidationError:
                db.rollback()

        # Two independent writers serialize on the same owned chunk. Both old
        # and intermediate vectors remain recoverable without duplicate rows.
        chunk_id = knowledge.id
        db.rollback()
        barrier = Barrier(2)

        def concurrent_replace(profile, vector):
            with SessionLocal() as session:
                chunk = session.get(KnowledgeChunk, chunk_id)
                barrier.wait(timeout=15)
                EmbeddingArchiveService(session).replace(user_id, chunk, content_hash=digest,
                                                         profile=profile, vector=vector)
                session.commit()

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(concurrent_replace, new, [0, 1]),
                       pool.submit(concurrent_replace, third, [1, 1])]
            for future in futures:
                future.result(timeout=20)
        db.refresh(knowledge)
        assert service.cached(user_id, knowledge, old, content_hash=digest) == [1, 0, 0]
        other = third if knowledge.embedding_profile_hash == new.profile_hash else new
        assert service.cached(user_id, knowledge, other, content_hash=digest) is not None

        migration = import_module("backend.migrations.versions.20260923_0037_embedding_archive")
        with patch.object(migration, "op", Operations(MigrationContext.configure(db.connection()))):
            try:
                migration.downgrade()
                raise AssertionError("nonempty archive was dropped")
            except RuntimeError as error:
                assert "禁止降级" in str(error)
        print("embedding archive reindex, restore, cancellation, ownership, concurrency and downgrade guard passed")
    finally:
        db.rollback()
        if user_id is not None:
            db.execute(delete(User).where(User.id == user_id))
            db.commit()
        db.close()


if __name__ == "__main__":
    run_check()

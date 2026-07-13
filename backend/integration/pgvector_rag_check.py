from __future__ import annotations

from sqlalchemy import delete

from backend.app.db.session import SessionLocal
from backend.app.models import Course, CourseMaterial, KnowledgeChunk, KnowledgePoint, User
from backend.app.services.rag import SqlAlchemyRagRepository


def _vector(first: float, second: float = 0.0) -> list[float]:
    return [first, second, *([0.0] * 1534)]


def run_check() -> None:
    db = SessionLocal()
    user_ids: list[int] = []
    course_ids: list[int] = []
    try:
        owner = User(
            email="pgvector-owner@edunova.local",
            hashed_password="integration-only",
            display_name="pgvector owner",
            role="student",
            starter_mode="blank",
        )
        other_user = User(
            email="pgvector-other@edunova.local",
            hashed_password="integration-only",
            display_name="pgvector other",
            role="student",
            starter_mode="blank",
        )
        db.add_all([owner, other_user])
        db.flush()
        user_ids = [owner.id, other_user.id]

        course = Course(owner_id=owner.id, title="pgvector integration course", status="ready")
        other_course = Course(owner_id=other_user.id, title="pgvector isolated course", status="ready")
        db.add_all([course, other_course])
        db.flush()
        course_ids = [course.id, other_course.id]

        material = CourseMaterial(
            user_id=owner.id,
            course_id=course.id,
            filename="pgvector.md",
            content_type="text/markdown",
            storage_path="builtin://pgvector",
            parse_status="completed",
            extracted_text="pgvector integration",
            metadata_json={},
        )
        other_material = CourseMaterial(
            user_id=other_user.id,
            course_id=other_course.id,
            filename="isolated.md",
            content_type="text/markdown",
            storage_path="builtin://pgvector-isolated",
            parse_status="completed",
            extracted_text="isolated",
            metadata_json={},
        )
        point = KnowledgePoint(course_id=course.id, title="向量排序", order_index=1, prerequisites_json=[])
        db.add_all([material, other_material, point])
        db.flush()

        metadata = {"embedding_source": "openai_compatible", "embedding_model": "test-embedding"}
        profile_hash = "integration-openai-compatible-1536"
        embedding_columns = {
            "embedding_provider": "openai_compatible",
            "embedding_model": "test-embedding",
            "embedding_dimension": 1536,
            "embedding_profile_hash": profile_hash,
        }
        near = KnowledgeChunk(
            course_id=course.id,
            material_id=material.id,
            knowledge_point_id=point.id,
            content="nearest",
            embedding=_vector(1.0),
            metadata_json=metadata,
            **embedding_columns,
        )
        middle = KnowledgeChunk(
            course_id=course.id,
            material_id=material.id,
            knowledge_point_id=point.id,
            content="middle",
            embedding=_vector(0.8, 0.6),
            metadata_json=metadata,
            **embedding_columns,
        )
        far = KnowledgeChunk(
            course_id=course.id,
            material_id=material.id,
            knowledge_point_id=point.id,
            content="far",
            embedding=_vector(0.0, 1.0),
            metadata_json=metadata,
            **embedding_columns,
        )
        wrong_model = KnowledgeChunk(
            course_id=course.id,
            material_id=material.id,
            knowledge_point_id=point.id,
            content="wrong model",
            embedding=_vector(1.0),
            metadata_json={**metadata, "embedding_model": "other-model"},
            **{**embedding_columns, "embedding_model": "other-model"},
        )
        isolated = KnowledgeChunk(
            course_id=other_course.id,
            material_id=other_material.id,
            content="other user",
            embedding=_vector(1.0),
            metadata_json=metadata,
            **embedding_columns,
        )
        db.add_all([near, middle, far, wrong_model, isolated])
        db.commit()

        repository = SqlAlchemyRagRepository(db)
        rows = repository.vector_candidates(
            course.id,
            _vector(1.0),
            embedding_source="openai_compatible",
            embedding_model="test-embedding",
            embedding_dimension=1536,
            embedding_profile_hash=profile_hash,
            limit=10,
        )

        assert [chunk.id for chunk, _distance in rows] == [near.id, middle.id, far.id]
        assert [distance for _chunk, distance in rows] == sorted(distance for _chunk, distance in rows)
        assert repository.get_course_for_user(owner.id, other_course.id) is None
        persisted = db.get(KnowledgeChunk, near.id)
        assert persisted is not None and len(persisted.embedding or []) == 1536
        print("pgvector cosine ranking and isolation check passed")
    finally:
        db.rollback()
        if course_ids:
            db.execute(delete(Course).where(Course.id.in_(course_ids)))
        if user_ids:
            db.execute(delete(User).where(User.id.in_(user_ids)))
        db.commit()
        db.close()


if __name__ == "__main__":
    run_check()

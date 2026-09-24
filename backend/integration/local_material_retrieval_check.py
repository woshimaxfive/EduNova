"""Real local vectors, PostgreSQL retrieval and citations on synthetic material."""
from types import SimpleNamespace
from uuid import uuid4

from sqlalchemy import delete

from backend.app.core.config import Settings
from backend.app.db.session import SessionLocal
from backend.app.models import Material, User
from backend.app.services.embeddings import EmbeddingService
from backend.app.services.material_retrieval import MaterialRetrievalService, SqlAlchemyMaterialRetrievalRepository
from backend.app.services.model_settings import ModelSettingsService


def run_check():
    with SessionLocal() as db:
        owner_id = None
        try:
            user = User(account=f"local_{uuid4().hex[:12]}", hashed_password="synthetic-only",
                        display_name="本地检索测试", role="student", starter_mode="blank")
            db.add(user)
            db.flush()
            owner_id = user.id
            material = Material(
                user_id=user.id, filename="synthetic.md", content_type="text/markdown",
                storage_path="integration://local-material", parse_status="completed",
                ingestion_status="confirmed", outline_json={}, quality_json={}, metadata_json={},
                extracted_text="# 虚拟内存\n页表把虚拟地址映射到物理地址。\n\n"
                               "# 事务原子性\n数据库事务的原子性保证操作全部完成或者全部撤销。\n\n"
                               "# 网络路由\n路由器根据目的地址转发不同网络之间的数据包。",
            )
            db.add(material)
            db.commit()
            models = ModelSettingsService(
                repository=SimpleNamespace(),
                settings=Settings(_env_file=None, system_embedding_provider="fastembed_local"),
                execution_runtime=SimpleNamespace(execute=lambda *, call, **kwargs: call()),
            )
            repository = SqlAlchemyMaterialRetrievalRepository(db)
            retrieval = MaterialRetrievalService(repository, embedding_service=EmbeddingService(models))
            result = retrieval.search(user, [material.id], "虚拟地址如何找到物理内存？")
            assert result.embedding_status == "completed"
            assert result.citations[0]["section_title"] == "虚拟内存"
            chunks = repository.list_chunks([material.id])
            assert len(chunks) == 3 and all(chunk.embedding_dimension == 512 for chunk in chunks)
            db.expire_all()
            assert retrieval.search(user, [material.id], "事务执行失败如何撤销？").citations[0]["section_title"] == "事务原子性"
            assert retrieval.search(User(id=-1), [material.id], "虚拟内存").citations == []
            print("local material retrieval passed: persisted 512d vectors, citations, reload, owner isolation")
        finally:
            db.rollback()
            if owner_id is not None:
                db.execute(delete(User).where(User.id == owner_id))
                db.commit()


if __name__ == "__main__":
    run_check()

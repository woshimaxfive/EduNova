"""No database, Redis, credentials or network: exercise real configured inference."""
from types import SimpleNamespace

import numpy as np

from backend.app.core.config import Settings
from backend.app.models import User
from backend.app.services.embeddings import EmbeddingService
from backend.app.services.model_settings import ModelSettingsService


def run_check():
    settings = Settings(_env_file=None, system_embedding_provider="fastembed_local")
    service = ModelSettingsService(
        repository=SimpleNamespace(), settings=settings,
        # Substitute audit/Redis coordination only, not the real inference adapter.
        execution_runtime=SimpleNamespace(execute=lambda *, call, **kwargs: call()),
    )
    embeddings = EmbeddingService(service)
    user = User(id=1)
    documents = ["操作系统使用页表把虚拟地址映射到物理地址。", "数据库事务的原子性保证操作要么全部完成要么全部撤销。",
                 "计算机网络的路由器根据目的地址转发数据包。"]
    queries = ["虚拟内存地址怎样找到物理内存位置？", "一笔事务执行一半失败，如何避免留下半成品？", "跨网络的数据包由哪种设备转发？"]
    batch = embeddings.embed_documents(user, documents)
    assert batch.status == "completed" and batch.dimension == 512 and len(batch.vectors) == 3
    query_vectors = np.asarray([embeddings.embed_query(user, query).vectors[0] for query in queries])
    scores = query_vectors @ np.asarray(batch.vectors).T
    assert scores.argmax(axis=1).tolist() == [0, 1, 2]
    assert service.resolve_embedding_runtime_config(user).api_key is None
    print("configured local inference passed: 3 synthetic cross-topic queries, 512 dimensions, no model key")


if __name__ == "__main__":
    run_check()

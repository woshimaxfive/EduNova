from __future__ import annotations

from dataclasses import dataclass, field

from backend.app.models import Material, MaterialChunk, User
from backend.app.services.material_retrieval import MaterialChunkingService, MaterialRetrievalService


@dataclass
class FakeMaterialRetrievalRepository:
    materials: list[Material] = field(default_factory=list)
    chunks: list[MaterialChunk] = field(default_factory=list)
    save_count: int = 0

    def list_materials(self, user_id: int, material_ids: list[int]) -> list[Material]:
        return [item for item in self.materials if item.user_id == user_id and item.id in material_ids]

    def list_chunks(self, material_ids: list[int]) -> list[MaterialChunk]:
        return [item for item in self.chunks if item.material_id in material_ids]

    def add_chunks(self, chunks: list[MaterialChunk]) -> None:
        next_id = max((item.id or 0 for item in self.chunks), default=0) + 1
        for chunk in chunks:
            chunk.id = next_id
            next_id += 1
        self.chunks.extend(chunks)

    def save_chunks(self) -> None:
        self.save_count += 1

    def vector_candidates(
        self,
        user_id: int,
        material_ids: list[int],
        query_vector: list[float],
        limit: int,
    ) -> list[tuple[MaterialChunk, float]]:
        return []


def test_markdown_chunking_preserves_section_titles_and_stable_indexes() -> None:
    material = make_material(
        material_id=11,
        user_id=1,
        text=(
            "# 人工智能概述\n人工智能关注感知、推理和行动。\n\n"
            "## 机器学习\n机器学习让系统从数据中学习规律，包括监督学习和无监督学习。\n\n"
            "## 搜索\n搜索算法在状态空间中寻找路径。"
        ),
    )

    chunks = MaterialChunkingService().build_chunks(material)

    assert [item.chunk_index for item in chunks] == list(range(len(chunks)))
    assert [item.section_title for item in chunks] == ["人工智能概述", "机器学习", "搜索"]
    assert chunks[1].content.startswith("机器学习让系统")


def test_long_plain_text_chunks_use_overlap_and_size_limit() -> None:
    material = make_material(material_id=12, user_id=1, filename="notes.txt", text="机器学习内容。" * 250)

    chunks = MaterialChunkingService().build_chunks(material)

    assert len(chunks) > 2
    assert all(len(item.content) <= 800 for item in chunks)
    assert chunks[0].content[-80:] in chunks[1].content


def test_material_retrieval_lazily_chunks_and_hits_relevant_section() -> None:
    material = make_material(
        material_id=21,
        user_id=1,
        text=(
            "# 人工智能概述\n人工智能研究智能行为。\n"
            "## 搜索问题\n搜索在状态空间中寻找路径。\n"
            "## 机器学习\n机器学习是让计算机从数据中学习规律的方法，常见类型包括监督学习和无监督学习。"
        ),
    )
    repo = FakeMaterialRetrievalRepository(materials=[material])
    service = MaterialRetrievalService(repo)

    result = service.search(user=make_user(1), material_ids=[21], query="什么是机器学习？")

    assert repo.save_count == 1
    assert result.retrieval_mode == "keyword"
    assert result.citations
    assert result.citations[0]["section_title"] == "机器学习"
    assert "机器学习是让计算机" in result.citations[0]["snippet"]
    assert result.citations[0]["retrieval_source"] == "keyword"


def test_material_retrieval_does_not_expose_other_users_materials() -> None:
    repo = FakeMaterialRetrievalRepository(
        materials=[make_material(material_id=31, user_id=2, text="# 机器学习\n其他用户资料。")]
    )

    result = MaterialRetrievalService(repo).search(
        user=make_user(1),
        material_ids=[31],
        query="机器学习",
    )

    assert result.citations == []
    assert repo.chunks == []


def test_material_retrieval_returns_empty_when_selected_material_has_no_relevant_chunk() -> None:
    material = make_material(material_id=41, user_id=1, text="# 数据库\n关系数据库使用表组织数据。")
    repo = FakeMaterialRetrievalRepository(materials=[material])

    result = MaterialRetrievalService(repo).search(
        user=make_user(1),
        material_ids=[41],
        query="量子纠缠实验",
    )

    assert result.citations == []


def make_material(
    *,
    material_id: int,
    user_id: int,
    text: str,
    filename: str = "人工智能导论.md",
) -> Material:
    return Material(
        id=material_id,
        user_id=user_id,
        filename=filename,
        content_type="text/markdown",
        storage_path=f"user_{user_id}/{material_id}.md",
        parse_status="completed",
        extracted_text=text,
        metadata_json={},
    )


def make_user(user_id: int) -> User:
    return User(
        id=user_id,
        email=f"student-{user_id}@example.com",
        hashed_password="not-used",
        display_name="测试学生",
        role="student",
        starter_mode="blank",
    )

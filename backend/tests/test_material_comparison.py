from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from backend.app.api.v1.deps import get_auth_service
from backend.app.api.v1.materials import get_material_service
from backend.app.core.config import Settings
from backend.app.core.security import create_access_token
from backend.app.main import create_app
from backend.app.models import Course, CourseMaterial, CourseMaterialLink, KnowledgeChunk, KnowledgePoint, Material, User
from backend.app.services.auth import AuthService
from backend.app.services.materials import MaterialService


@dataclass
class TokenAuthRepository:
    user: User

    def get_user_by_id(self, user_id: int) -> User | None:
        return self.user if self.user.id == user_id else None


@dataclass
class FakeMaterialComparisonRepository:
    materials: list[Material] = field(default_factory=list)
    courses: list[Course] = field(default_factory=list)
    links: list[CourseMaterialLink] = field(default_factory=list)
    course_materials: list[CourseMaterial] = field(default_factory=list)
    knowledge_points: list[KnowledgePoint] = field(default_factory=list)
    knowledge_chunks: list[KnowledgeChunk] = field(default_factory=list)

    def get_course_for_user(self, user_id: int, course_id: int) -> Course | None:
        return next((course for course in self.courses if course.id == course_id and course.owner_id == user_id), None)

    def add_material(self, material: Material) -> None:
        self.materials.append(material)

    def get_material_for_user(self, user_id: int, material_id: int) -> Material | None:
        return next((material for material in self.materials if material.id == material_id and material.user_id == user_id), None)

    def list_materials(self, user_id: int, course_id: int | None = None, unassigned: bool = False) -> list[Material]:
        result = [material for material in self.materials if material.user_id == user_id]
        if course_id is not None:
            linked_ids = {link.material_id for link in self.links if link.course_id == course_id}
            result = [material for material in result if material.id in linked_ids]
        if unassigned:
            linked_ids = {link.material_id for link in self.links}
            result = [material for material in result if material.id not in linked_ids]
        return result

    def get_link(self, course_id: int, material_id: int) -> CourseMaterialLink | None:
        return next((link for link in self.links if link.course_id == course_id and link.material_id == material_id), None)

    def add_link(self, link: CourseMaterialLink) -> CourseMaterialLink:
        self.links.append(link)
        return link

    def list_course_materials(self, course_id: int) -> list[CourseMaterial]:
        return [material for material in self.course_materials if material.course_id == course_id]

    def list_knowledge_points(self, course_id: int) -> list[KnowledgePoint]:
        return [point for point in self.knowledge_points if point.course_id == course_id]

    def list_knowledge_chunks(self, course_id: int) -> list[KnowledgeChunk]:
        return [chunk for chunk in self.knowledge_chunks if chunk.course_id == course_id]

    def commit(self) -> None:
        return None

    def rollback(self) -> None:
        return None

    def refresh(self, _instance: object) -> None:
        return None


def make_user(user_id: int = 1) -> User:
    return User(
        id=user_id,
        email=f"user{user_id}@edunova.local",
        hashed_password="not-used",
        display_name=f"用户 {user_id}",
        role="student",
        starter_mode="blank",
    )


def make_settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        jwt_secret="materials-compare-secret-with-32-bytes",
        jwt_expire_minutes=30,
        material_storage_dir=str(tmp_path / "uploads" / "materials"),
    )


def material(material_id: int, user_id: int, filename: str, text: str | None = None) -> Material:
    return Material(
        id=material_id,
        user_id=user_id,
        filename=filename,
        content_type="text/markdown",
        storage_path=f"user_{user_id}/{filename}",
        parse_status="completed" if text is not None else "uploaded",
        extracted_text=text,
        metadata_json={"size_label": "1 KB", "extension": "MD"},
    )


def course_material(course_material_id: int, user_id: int, course_id: int, source_material_id: int, filename: str) -> CourseMaterial:
    return CourseMaterial(
        id=course_material_id,
        user_id=user_id,
        course_id=course_id,
        filename=filename,
        content_type="text/markdown",
        storage_path=f"user_{user_id}/{filename}",
        parse_status="completed",
        extracted_text=None,
        metadata_json={"source_material_id": source_material_id, "generated_from_library": True},
    )


def chunk(
    chunk_id: int,
    course_id: int,
    course_material_id: int,
    source_material_id: int,
    content: str,
    section_title: str,
    knowledge_point_id: int | None,
) -> KnowledgeChunk:
    return KnowledgeChunk(
        id=chunk_id,
        course_id=course_id,
        material_id=course_material_id,
        knowledge_point_id=knowledge_point_id,
        content=content,
        page_number=None,
        section_title=section_title,
        embedding=None,
        metadata_json={"source_material_id": source_material_id, "source_filename": f"资料 {source_material_id}.md"},
    )


def make_repo() -> FakeMaterialComparisonRepository:
    return FakeMaterialComparisonRepository(
        materials=[
            material(1, 1, "AI 导论讲义.md", "启发式搜索 反向传播 完整资料原文禁止泄露 SECRET-COURSE-DOCUMENT-LONG"),
            material(2, 1, "期末样题.md", "启发式搜索 监督学习"),
            material(3, 2, "其他用户资料.md", "启发式搜索"),
        ],
        courses=[Course(id=101, owner_id=1, title="人工智能导论", source_type="uploaded")],
        links=[
            CourseMaterialLink(id=11, course_id=101, material_id=1, added_by_user_id=1, usage_type="course_source"),
            CourseMaterialLink(id=12, course_id=101, material_id=2, added_by_user_id=1, usage_type="course_source"),
        ],
        course_materials=[
            course_material(21, 1, 101, 1, "AI 导论讲义.md"),
            course_material(22, 1, 101, 2, "期末样题.md"),
        ],
        knowledge_points=[
            KnowledgePoint(id=31, course_id=101, title="启发式搜索", summary="启发函数与 A*。", chapter="搜索", order_index=1),
            KnowledgePoint(id=32, course_id=101, title="反向传播", summary="链式法则。", chapter="神经网络", order_index=2),
            KnowledgePoint(id=33, course_id=101, title="AI 伦理", summary="安全边界。", chapter="伦理", order_index=3),
        ],
        knowledge_chunks=[
            chunk(41, 101, 21, 1, "启发式搜索使用启发函数估计状态空间，A* 是常见算法。", "启发式搜索", 31),
            chunk(42, 101, 22, 2, "期末样题：启发式搜索、A* 和启发函数是常考选择题。", "期末样题：启发式搜索", 31),
            chunk(43, 101, 21, 1, "反向传播依赖链式法则计算梯度。完整资料原文禁止泄露 SECRET-COURSE-DOCUMENT-LONG", "反向传播", 32),
            chunk(44, 101, 22, 2, "监督学习泛化能力和过拟合经常出现在样题。", "监督学习", None),
        ],
    )


def as_dict(model: Any) -> dict[str, Any]:
    return model.model_dump() if hasattr(model, "model_dump") else model


def test_compare_materials_extracts_repeated_exam_unique_missing_and_safe_citations(tmp_path: Path) -> None:
    user = make_user()
    service = MaterialService(repository=make_repo(), settings=make_settings(tmp_path))

    result = as_dict(service.compare_materials(user, course_id=101, material_ids=[1, 2, 2]))
    serialized = str(result)

    assert result["course_id"] == "101"
    assert result["material_ids"] == ["1", "2"]
    assert result["summary"]["compared_material_count"] == 2
    assert result["summary"]["comparable_material_count"] == 2
    assert result["repeated_concepts"][0]["title"] == "启发式搜索"
    assert result["exam_likely_points"][0]["title"] == "启发式搜索"
    assert any(point["title"] == "反向传播" for point in result["materials_only_points"])
    assert any(point["title"] == "监督学习" for point in result["questions_only_points"])
    assert any(point["title"] == "AI 伦理" for point in result["missing_review_points"])
    assert result["priority_order"][0]["title"] == "启发式搜索"
    assert result["citations"][0]["source_title"]
    assert "SECRET-COURSE-DOCUMENT-LONG" not in serialized
    assert "系统提示词" not in serialized
    assert "API Key" not in serialized


def test_compare_materials_validates_user_course_material_scope_and_minimum(tmp_path: Path) -> None:
    user = make_user()
    service = MaterialService(repository=make_repo(), settings=make_settings(tmp_path))

    from backend.app.services.materials import CourseNotFoundError, MaterialNotFoundError, MaterialValidationError

    for payload in ([1], [1, 3], [1, 999]):
        try:
            service.compare_materials(user, course_id=101, material_ids=payload)
        except Exception as exc:
            if payload == [1]:
                assert isinstance(exc, MaterialValidationError)
            else:
                assert isinstance(exc, MaterialNotFoundError)

    try:
        service.compare_materials(make_user(2), course_id=101, material_ids=[1, 2])
    except Exception as exc:
        assert isinstance(exc, CourseNotFoundError)


def test_compare_materials_uses_text_fallback_when_course_chunks_are_missing(tmp_path: Path) -> None:
    repo = FakeMaterialComparisonRepository(
        materials=[
            material(1, 1, "复习提纲.md", "搜索算法\n启发式搜索\nA*"),
            material(2, 1, "期末题.md", "启发式搜索\nA*"),
        ],
        courses=[Course(id=101, owner_id=1, title="人工智能导论", source_type="uploaded")],
        links=[
            CourseMaterialLink(id=11, course_id=101, material_id=1, added_by_user_id=1, usage_type="course_source"),
            CourseMaterialLink(id=12, course_id=101, material_id=2, added_by_user_id=1, usage_type="course_source"),
        ],
        course_materials=[],
        knowledge_points=[KnowledgePoint(id=31, course_id=101, title="启发式搜索", summary=None, chapter=None, order_index=1)],
        knowledge_chunks=[],
    )
    service = MaterialService(repository=repo, settings=make_settings(tmp_path))

    result = as_dict(service.compare_materials(make_user(), course_id=101, material_ids=[1, 2]))

    assert result["summary"]["comparable_material_count"] == 2
    assert any(point["title"] == "启发式搜索" for point in result["repeated_concepts"])


def test_compare_materials_route_requires_login() -> None:
    client = TestClient(create_app())

    response = client.post("/api/v1/materials/compare", json={"course_id": 101, "material_ids": [1, 2]})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_compare_materials_route_returns_typed_envelope(tmp_path: Path) -> None:
    user = make_user()
    repo = make_repo()
    settings = make_settings(tmp_path)
    app = create_app()
    app.dependency_overrides[get_auth_service] = lambda: AuthService(repository=TokenAuthRepository(user), settings=settings)
    app.dependency_overrides[get_material_service] = lambda: MaterialService(repository=repo, settings=settings)
    client = TestClient(app)
    token = create_access_token(str(user.id), settings=settings)

    response = client.post(
        "/api/v1/materials/compare",
        headers={"Authorization": f"Bearer {token}"},
        json={"course_id": 101, "material_ids": [1, 2]},
    )

    assert response.status_code == 200
    assert response.json()["data"]["course_id"] == "101"
    assert response.json()["data"]["repeated_concepts"][0]["title"] == "启发式搜索"

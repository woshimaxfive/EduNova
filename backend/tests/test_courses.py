from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.app.api.v1.deps import get_auth_service
from backend.app.api.v1.courses import get_course_service
from backend.app.core.config import Settings
from backend.app.core.security import create_access_token
from backend.app.main import create_app
from backend.app.models import (
    Course,
    CourseEnrollment,
    CourseMaterial,
    CourseMaterialLink,
    KnowledgeChunk,
    KnowledgePoint,
    Material,
    User,
)
from backend.app.services.auth import AuthService
from backend.app.services.courses import CourseService


@dataclass
class TokenAuthRepository:
    user: User

    def get_user_by_id(self, user_id: int) -> User | None:
        return self.user if self.user.id == user_id else None


@dataclass
class FakeCourseRepository:
    materials: list[Material] = field(default_factory=list)
    courses: list[Course] = field(default_factory=list)
    enrollments: list[CourseEnrollment] = field(default_factory=list)
    course_materials: list[CourseMaterial] = field(default_factory=list)
    material_links: list[CourseMaterialLink] = field(default_factory=list)
    knowledge_points: list[KnowledgePoint] = field(default_factory=list)
    knowledge_chunks: list[KnowledgeChunk] = field(default_factory=list)
    next_course_id: int = 101
    next_enrollment_id: int = 201
    next_course_material_id: int = 301
    next_link_id: int = 401
    next_knowledge_point_id: int = 501
    next_chunk_id: int = 601

    def get_materials_for_user(self, user_id: int, material_ids: list[int]) -> list[Material]:
        material_id_set = set(material_ids)
        return [material for material in self.materials if material.user_id == user_id and material.id in material_id_set]

    def add_course_graph(
        self,
        course: Course,
        enrollment: CourseEnrollment,
        course_materials: list[CourseMaterial],
        material_links: list[CourseMaterialLink],
        knowledge_points: list[KnowledgePoint],
        knowledge_chunks: list[KnowledgeChunk],
    ) -> Course:
        course.id = self.next_course_id
        self.next_course_id += 1
        self.courses.append(course)

        enrollment.id = self.next_enrollment_id
        enrollment.course_id = course.id
        self.next_enrollment_id += 1
        self.enrollments.append(enrollment)

        for course_material in course_materials:
            course_material.id = self.next_course_material_id
            course_material.course_id = course.id
            self.next_course_material_id += 1
            self.course_materials.append(course_material)

        for link in material_links:
            link.id = self.next_link_id
            link.course_id = course.id
            self.next_link_id += 1
            self.material_links.append(link)

        for knowledge_point in knowledge_points:
            knowledge_point.id = self.next_knowledge_point_id
            knowledge_point.course_id = course.id
            self.next_knowledge_point_id += 1
            self.knowledge_points.append(knowledge_point)

        for index, chunk in enumerate(knowledge_chunks):
            chunk.id = self.next_chunk_id
            chunk.course_id = course.id
            if chunk.material_id is None:
                chunk.material_id = self.course_materials[min(index, len(self.course_materials) - 1)].id
            self.next_chunk_id += 1
            self.knowledge_chunks.append(chunk)

        return course

    def list_courses_for_user(self, user_id: int, source_type: str | None = None) -> list[Course]:
        result = [course for course in self.courses if course.owner_id == user_id]
        if source_type:
            result = [course for course in result if course.source_type == source_type]
        return result

    def get_course_for_user(self, user_id: int, course_id: int) -> Course | None:
        return next((course for course in self.courses if course.owner_id == user_id and course.id == course_id), None)

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


def make_material(
    material_id: int,
    user_id: int,
    filename: str,
    extracted_text: str | None,
    parse_status: str = "completed",
) -> Material:
    return Material(
        id=material_id,
        user_id=user_id,
        filename=filename,
        content_type="text/markdown" if filename.endswith(".md") else "text/plain",
        storage_path=f"user_{user_id}/{filename}",
        parse_status=parse_status,
        extracted_text=extracted_text,
        metadata_json={"size_label": "1 KB", "extension": filename.rsplit(".", 1)[-1].upper()},
    )


def make_service(repo: FakeCourseRepository) -> CourseService:
    return CourseService(repository=repo)


@dataclass
class FakeEmbeddingBatch:
    vectors: list[list[float]]
    source: str = "local"
    model: str = "local-hash-1536"
    dimension: int = 1536
    status: str = "local_fallback"


@dataclass
class FakeEmbeddingService:
    calls: list[list[str]] = field(default_factory=list)

    def embed_texts(self, _user: User, texts: list[str]) -> FakeEmbeddingBatch:
        self.calls.append(texts)
        vectors = []
        for index, _text in enumerate(texts):
            vector = [0.0] * 1536
            vector[index % 1536] = 1.0
            vectors.append(vector)
        return FakeEmbeddingBatch(vectors=vectors)


def as_dict(model: Any) -> dict[str, Any]:
    return model.model_dump() if hasattr(model, "model_dump") else model


def test_course_routes_require_login() -> None:
    client = TestClient(create_app())

    response = client.get("/api/v1/courses")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_create_course_from_txt_material_builds_course_graph() -> None:
    repo = FakeCourseRepository(
        materials=[
            make_material(
                1,
                1,
                "exam-notes.txt",
                "神经网络基础\n\n反向传播使用链式法则计算梯度。\n\n过拟合需要用正则化缓解。",
            )
        ]
    )
    user = make_user()

    result = make_service(repo).create_course_from_materials(
        user,
        material_ids=[1],
        course_title="神经网络期末复习",
    )

    data = as_dict(result)

    assert data["course"]["title"] == "神经网络期末复习"
    assert data["course"]["source_type"] == "uploaded"
    assert data["course"]["status"] == "ready"
    assert data["course"]["material_count"] == 1
    assert data["course"]["knowledge_point_count"] >= 2
    assert data["course"]["chunk_count"] >= 2
    assert repo.courses[0].owner_id == user.id
    assert repo.enrollments[0].progress_percent == Decimal("0")
    assert repo.course_materials[0].filename == "exam-notes.txt"
    assert repo.material_links[0].material_id == 1
    assert repo.material_links[0].usage_type == "course_source"
    assert all(chunk.embedding is None for chunk in repo.knowledge_chunks)


def test_markdown_headings_generate_chapters_and_knowledge_points() -> None:
    repo = FakeCourseRepository(
        materials=[
            make_material(
                1,
                1,
                "ai.md",
                "# 搜索问题\n状态空间是搜索的基础。\n## 启发式搜索\nA* 使用启发函数。\n## 对抗搜索\nMinimax 用于博弈。",
            )
        ]
    )

    result = make_service(repo).create_course_from_materials(make_user(), [1], "AI 搜索复习")
    points = as_dict(result)["knowledge_points"]

    assert [point["title"] for point in points] == ["搜索问题", "启发式搜索", "对抗搜索"]
    assert points[1]["chapter"] == "搜索问题"
    assert "A*" in repo.knowledge_chunks[1].content


def test_create_course_best_effort_generates_chunk_embeddings() -> None:
    repo = FakeCourseRepository(
        materials=[
            make_material(
                1,
                1,
                "ai.md",
                "# 搜索问题\n状态空间是搜索的基础。\n## 启发式搜索\nA* 使用启发函数。",
            )
        ]
    )
    embedding_service = FakeEmbeddingService()
    service = CourseService(repository=repo, embedding_service=embedding_service)

    service.create_course_from_materials(make_user(), [1], "AI 搜索复习")

    assert embedding_service.calls == [[chunk.content for chunk in repo.knowledge_chunks]]
    assert all(chunk.embedding is not None for chunk in repo.knowledge_chunks)
    assert repo.knowledge_chunks[0].metadata_json["embedding_source"] == "local"
    assert repo.knowledge_chunks[0].metadata_json["embedding_model"] == "local-hash-1536"
    assert repo.knowledge_chunks[0].metadata_json["embedding_dimension"] == 1536


def test_unheaded_txt_generates_numbered_sections() -> None:
    repo = FakeCourseRepository(
        materials=[make_material(1, 1, "plain.txt", "第一段介绍监督学习。\n\n第二段介绍泛化能力。")]
    )

    result = make_service(repo).create_course_from_materials(make_user(), [1], "")
    points = as_dict(result)["knowledge_points"]

    assert as_dict(result)["course"]["title"] == "plain"
    assert [point["title"] for point in points] == ["第 1 部分", "第 2 部分"]


def test_rejects_other_user_or_unparsed_materials() -> None:
    from backend.app.services.courses import CourseGenerationError

    repo = FakeCourseRepository(
        materials=[
            make_material(1, 2, "other.md", "# Other"),
            make_material(2, 1, "slide.pdf", None, parse_status="uploaded"),
            make_material(3, 1, "empty.md", None, parse_status="completed"),
        ]
    )
    service = make_service(repo)
    user = make_user()

    with pytest.raises(CourseGenerationError, match="资料不存在或无权访问"):
        service.create_course_from_materials(user, [1], "非法资料")

    with pytest.raises(CourseGenerationError, match="当前仅支持已解析的 TXT/Markdown 生成课程"):
        service.create_course_from_materials(user, [2], "PDF 课程")

    with pytest.raises(CourseGenerationError, match="当前仅支持已解析的 TXT/Markdown 生成课程"):
        service.create_course_from_materials(user, [3], "空资料")

    with pytest.raises(CourseGenerationError, match="至少选择一份资料"):
        service.create_course_from_materials(user, [], "空选择")


def test_course_read_apis_are_scoped_to_current_user() -> None:
    repo = FakeCourseRepository(courses=[Course(id=101, owner_id=1, title="我的课", source_type="uploaded")])
    repo.knowledge_points.append(KnowledgePoint(id=501, course_id=101, title="知识点", summary="摘要", chapter="第一章", order_index=0))
    repo.knowledge_chunks.append(KnowledgeChunk(id=601, course_id=101, material_id=301, content="知识切片", metadata_json={}))
    service = make_service(repo)

    assert [item.title for item in service.list_courses(make_user(1)).data] == ["我的课"]
    assert service.list_courses(make_user(2)).data == []
    assert service.get_course(make_user(1), 101).title == "我的课"
    assert service.get_overview(make_user(1), 101).chunk_count == 1
    assert service.get_knowledge_points(make_user(1), 101)[0].title == "知识点"

    from backend.app.services.courses import CourseNotFoundError

    with pytest.raises(CourseNotFoundError):
        service.get_course(make_user(2), 101)


def test_create_course_route_returns_envelope() -> None:
    repo = FakeCourseRepository(materials=[make_material(1, 1, "route.md", "# 路由测试\n正文")])
    user = make_user()
    settings = Settings(_env_file=None, jwt_secret="courses-test-secret-with-32-bytes", jwt_expire_minutes=30)
    app = create_app()
    app.dependency_overrides[get_auth_service] = lambda: AuthService(
        repository=TokenAuthRepository(user),
        settings=settings,
    )
    app.dependency_overrides[get_course_service] = lambda: CourseService(repository=repo)
    client = TestClient(app)
    token = create_access_token(str(user.id), settings=settings)

    response = client.post(
        "/api/v1/courses/from-materials",
        headers={"Authorization": f"Bearer {token}"},
        json={"material_ids": [1], "course_title": "路由课程"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["course"]["title"] == "路由课程"

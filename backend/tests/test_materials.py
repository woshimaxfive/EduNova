from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.app.api.v1.deps import get_auth_service
from backend.app.api.v1.materials import get_material_service
from backend.app.core.config import Settings
from backend.app.core.security import create_access_token
from backend.app.main import create_app
from backend.app.models import Course, CourseMaterialLink, Material, User
from backend.app.services.auth import AuthService
from backend.app.services.materials import MaterialService


@dataclass
class TokenAuthRepository:
    user: User

    def get_user_by_id(self, user_id: int) -> User | None:
        return self.user if self.user.id == user_id else None


@dataclass
class FakeMaterialRepository:
    materials: list[Material] = field(default_factory=list)
    links: list[CourseMaterialLink] = field(default_factory=list)
    courses: list[Course] = field(default_factory=list)
    next_material_id: int = 1
    next_link_id: int = 1

    def get_course_for_user(self, user_id: int, course_id: int) -> Course | None:
        return next((course for course in self.courses if course.id == course_id and course.owner_id == user_id), None)

    def add_material(self, material: Material) -> None:
        material.id = self.next_material_id
        self.next_material_id += 1
        self.materials.append(material)

    def get_material_for_user(self, user_id: int, material_id: int) -> Material | None:
        return next((material for material in self.materials if material.id == material_id and material.user_id == user_id), None)

    def list_materials(self, user_id: int, course_id: int | None = None, unassigned: bool = False) -> list[Material]:
        result = [material for material in self.materials if material.user_id == user_id]
        if course_id is not None:
            linked_ids = {
                link.material_id
                for link in self.links
                if link.course_id == course_id and self.get_course_for_user(user_id, course_id) is not None
            }
            result = [material for material in result if material.id in linked_ids]
        if unassigned:
            linked_ids = {link.material_id for link in self.links}
            result = [material for material in result if material.id not in linked_ids]
        return sorted(result, key=lambda material: material.created_at or material.id, reverse=True)

    def get_link(self, course_id: int, material_id: int) -> CourseMaterialLink | None:
        return next(
            (link for link in self.links if link.course_id == course_id and link.material_id == material_id),
            None,
        )

    def add_link(self, link: CourseMaterialLink) -> CourseMaterialLink:
        existing = self.get_link(link.course_id, link.material_id)
        if existing is not None:
            return existing
        link.id = self.next_link_id
        self.next_link_id += 1
        self.links.append(link)
        return link

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


def make_settings(tmp_path: Path, max_upload_mb: int = 25) -> Settings:
    return Settings(
        _env_file=None,
        jwt_secret="materials-test-secret-with-32-bytes",
        jwt_expire_minutes=30,
        material_storage_dir=str(tmp_path / "uploads" / "materials"),
        material_max_upload_mb=max_upload_mb,
    )


def make_service(repo: FakeMaterialRepository, tmp_path: Path, max_upload_mb: int = 25) -> MaterialService:
    return MaterialService(repository=repo, settings=make_settings(tmp_path, max_upload_mb=max_upload_mb))


def upload_bytes(
    service: MaterialService,
    user: User,
    filename: str,
    content: bytes,
    content_type: str,
    course_id: int | None = None,
):
    return service.upload_material(
        user=user,
        filename=filename,
        content_type=content_type,
        content=content,
        course_id=course_id,
    )


def as_dict(model: Any) -> dict[str, Any]:
    return model.model_dump() if hasattr(model, "model_dump") else model


def test_material_routes_require_login() -> None:
    client = TestClient(create_app())

    response = client.get("/api/v1/materials")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_txt_upload_creates_completed_material_with_extracted_text(tmp_path: Path) -> None:
    repo = FakeMaterialRepository()
    user = make_user()
    result = upload_bytes(
        make_service(repo, tmp_path),
        user,
        "ai-notes.txt",
        "反向传播复习重点".encode("utf-8"),
        "text/plain",
    )

    data = as_dict(result)

    assert data["filename"] == "ai-notes.txt"
    assert data["parse_status"] == "completed"
    assert data["course_id"] is None
    assert repo.materials[0].extracted_text == "反向传播复习重点"
    assert repo.materials[0].storage_path.startswith("user_1/")


def test_markdown_upload_is_lightly_parsed(tmp_path: Path) -> None:
    repo = FakeMaterialRepository()
    user = make_user()

    result = upload_bytes(
        make_service(repo, tmp_path),
        user,
        "期末复习.md",
        "# 搜索\nA* 和启发式搜索".encode("utf-8"),
        "text/markdown",
    )

    assert as_dict(result)["parse_status"] == "completed"
    assert "启发式搜索" in (repo.materials[0].extracted_text or "")


def test_image_upload_is_saved_without_ocr(tmp_path: Path) -> None:
    repo = FakeMaterialRepository()
    user = make_user()

    result = upload_bytes(make_service(repo, tmp_path), user, "board.png", b"png-bytes", "image/png")

    data = as_dict(result)

    assert data["parse_status"] == "uploaded"
    assert data["detail"] == "仅入库，暂不做 OCR"
    assert repo.materials[0].extracted_text is None


def test_rejects_unsupported_extension_and_oversized_upload(tmp_path: Path) -> None:
    from backend.app.services.materials import MaterialValidationError

    user = make_user()

    with pytest.raises(MaterialValidationError):
        upload_bytes(make_service(FakeMaterialRepository(), tmp_path), user, "run.exe", b"bad", "application/octet-stream")

    with pytest.raises(MaterialValidationError):
        upload_bytes(make_service(FakeMaterialRepository(), tmp_path, max_upload_mb=1), user, "huge.txt", b"x" * (1024 * 1024 + 1), "text/plain")


def test_list_detail_progress_and_user_isolation(tmp_path: Path) -> None:
    repo = FakeMaterialRepository()
    service = make_service(repo, tmp_path)
    user = make_user(1)
    other = make_user(2)
    own = upload_bytes(service, user, "mine.txt", b"mine", "text/plain")
    upload_bytes(service, other, "other.txt", b"other", "text/plain")

    list_result = [as_dict(material) for material in service.list_materials(user)]
    detail = as_dict(service.get_material(user, int(as_dict(own)["id"])))
    progress = as_dict(service.get_progress(user, int(as_dict(own)["id"])))

    assert [item["title"] for item in list_result] == ["mine.txt"]
    assert detail["title"] == "mine.txt"
    assert progress == {
        "status": "completed",
        "progress_percent": 100,
        "message": "轻解析已完成",
    }

    from backend.app.services.materials import MaterialNotFoundError

    with pytest.raises(MaterialNotFoundError):
        service.get_material(other, int(as_dict(own)["id"]))


def test_course_upload_and_attach_materials_create_unique_links(tmp_path: Path) -> None:
    repo = FakeMaterialRepository(courses=[Course(id=101, owner_id=1, title="AI", source_type="generated")])
    user = make_user()
    service = make_service(repo, tmp_path)

    uploaded = upload_bytes(service, user, "course.md", b"# course", "text/markdown", course_id=101)
    material_id = int(as_dict(uploaded)["id"])
    service.attach_materials_to_course(user, course_id=101, material_ids=[material_id, material_id])

    assert as_dict(uploaded)["course_id"] == 101
    assert len(repo.links) == 1
    assert repo.links[0].course_id == 101
    assert repo.links[0].material_id == material_id
    assert repo.links[0].usage_type == "reference"
    assert [as_dict(material)["id"] for material in service.list_materials(user, course_id=101)] == [str(material_id)]
    assert service.list_materials(user, unassigned=True) == []


def test_material_upload_route_accepts_multipart_and_returns_envelope(tmp_path: Path) -> None:
    repo = FakeMaterialRepository()
    user = make_user()
    settings = make_settings(tmp_path)
    app = create_app()
    app.dependency_overrides[get_auth_service] = lambda: AuthService(
        repository=TokenAuthRepository(user),
        settings=settings,
    )
    app.dependency_overrides[get_material_service] = lambda: MaterialService(repository=repo, settings=settings)
    client = TestClient(app)
    token = create_access_token(str(user.id), settings=settings)

    response = client.post(
        "/api/v1/materials/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("route-notes.txt", b"route text", "text/plain")},
    )

    assert response.status_code == 200
    assert response.json()["data"]["filename"] == "route-notes.txt"
    assert response.json()["data"]["parse_status"] == "completed"

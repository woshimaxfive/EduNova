from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from fastapi.testclient import TestClient

from backend.app.api.v1.deps import get_auth_service
from backend.app.api.v1.materials import get_material_job_service, get_material_service
from backend.app.core.config import Settings
from backend.app.core.security import create_access_token
from backend.app.main import create_app
from backend.app.models import Course, CourseMaterialLink, Material, MaterialChunk, User
from backend.app.schemas.materials import MaterialOutlineOperation, UpdateMaterialOutlineRequest
from backend.app.services.auth import AuthService
from backend.app.services.materials import MaterialService


@dataclass
class TokenAuthRepository:
    user: User

    def get_user_by_id(self, user_id: int) -> User | None:
        return self.user if self.user.id == user_id else None


class FakeMaterialJobService:
    def create_material_ingestion_job(self, *_args, **_kwargs):
        return type("Job", (), {"job_id": "901", "status": "queued"})()


@dataclass
class FakeMaterialRepository:
    materials: list[Material] = field(default_factory=list)
    chunks: list[MaterialChunk] = field(default_factory=list)
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

    def add_material_chunks(self, chunks: list[MaterialChunk]) -> None:
        for chunk in chunks:
            chunk.id = len(self.chunks) + 1
            self.chunks.append(chunk)

    def get_material_for_user(self, user_id: int, material_id: int) -> Material | None:
        return next((material for material in self.materials if material.id == material_id and material.user_id == user_id), None)

    def delete_material(self, material: Material) -> None:
        self.materials.remove(material)
        self.chunks[:] = [chunk for chunk in self.chunks if chunk.material_id != material.id]
        self.links[:] = [link for link in self.links if link.material_id != material.id]

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

    def list_material_chunks(self, user_id: int, material_id: int) -> list[MaterialChunk]:
        if self.get_material_for_user(user_id, material_id) is None:
            return []
        return sorted(
            [chunk for chunk in self.chunks if chunk.material_id == material_id],
            key=lambda chunk: chunk.chunk_index,
        )

    def list_material_course_links(self, user_id: int, material_id: int) -> list[tuple[CourseMaterialLink, Course]]:
        course_by_id = {course.id: course for course in self.courses if course.owner_id == user_id}
        return [
            (link, course_by_id[link.course_id])
            for link in self.links
            if link.material_id == material_id and link.course_id in course_by_id
        ]

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
        account=f"user{user_id}",
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


def make_minimal_pdf_bytes(text: str = "heuristic search review") -> bytes:
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 4 0 R >> >> /MediaBox [0 0 612 792] /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode("ascii")
    objects.append(b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream")

    content = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, body in enumerate(objects, start=1):
        offsets.append(len(content))
        content.extend(f"{index} 0 obj\n".encode("ascii"))
        content.extend(body)
        content.extend(b"\nendobj\n")
    xref_offset = len(content)
    content.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    content.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        content.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    content.extend(
        f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("ascii")
    )
    return bytes(content)


def make_docx_bytes(text: str = "反向传播复习重点") -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        archive.writestr(
            "word/document.xml",
            (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                f"<w:body><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:body></w:document>"
            ),
        )
    return buffer.getvalue()


def make_pptx_bytes(text: str = "启发式搜索课件重点") -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        archive.writestr(
            "ppt/slides/slide1.xml",
            (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
                'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
                f"<p:cSld><p:spTree><p:sp><p:txBody><a:p><a:r><a:t>{text}</a:t></a:r></a:p>"
                "</p:txBody></p:sp></p:spTree></p:cSld></p:sld>"
            ),
        )
    return buffer.getvalue()


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

    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
    result = upload_bytes(make_service(repo, tmp_path), user, "board.png", png, "image/png")

    data = as_dict(result)

    assert data["parse_status"] == "uploaded"
    assert data["ingestion_status"] == "stored"
    assert data["category"] == "image"
    assert data["detail"] == "已入库，可用于图片提问"
    assert repo.materials[0].extracted_text is None


@pytest.mark.parametrize(
    ("filename", "content", "expected_text"),
    [
        ("slides.pdf", make_minimal_pdf_bytes("heuristic search review"), "heuristic search review"),
        ("notes.docx", make_docx_bytes("反向传播复习重点"), "反向传播复习重点"),
        ("lecture.pptx", make_pptx_bytes("启发式搜索课件重点"), "启发式搜索课件重点"),
    ],
)
def test_pdf_docx_and_pptx_uploads_are_deep_parsed(
    tmp_path: Path,
    filename: str,
    content: bytes,
    expected_text: str,
) -> None:
    repo = FakeMaterialRepository()
    user = make_user()

    result = upload_bytes(make_service(repo, tmp_path), user, filename, content, "application/octet-stream")

    assert as_dict(result)["parse_status"] == "completed"
    assert expected_text in (repo.materials[0].extracted_text or "")


def test_broken_deep_parse_file_is_rejected_before_storage(tmp_path: Path) -> None:
    repo = FakeMaterialRepository()
    user = make_user()

    from backend.app.services.materials import MaterialValidationError

    with pytest.raises(MaterialValidationError):
        upload_bytes(make_service(repo, tmp_path), user, "broken.docx", b"not-a-zip", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    assert repo.materials == []


def test_disguised_legacy_office_files_are_rejected(tmp_path: Path) -> None:
    repo = FakeMaterialRepository()
    user = make_user()

    from backend.app.services.materials import MaterialValidationError

    with pytest.raises(MaterialValidationError):
        upload_bytes(make_service(repo, tmp_path), user, "old-slides.ppt", b"legacy", "application/vnd.ms-powerpoint")


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
    assert detail["chunk_count"] == 1
    assert detail["section_count"] == 1
    assert detail["sections"][0]["preview"] == "mine"
    assert detail["linked_courses"] == []
    assert "storage_path" not in detail
    assert "metadata_json" not in detail
    assert progress == {
        "status": "legacy",
        "progress_percent": 100,
        "message": "旧版解析，可按需重新解析",
    }

    from backend.app.services.materials import MaterialNotFoundError

    with pytest.raises(MaterialNotFoundError):
        service.get_material(other, int(as_dict(own)["id"]))


def test_delete_material_removes_owned_record_links_chunks_and_stored_file(tmp_path: Path) -> None:
    course = Course(id=101, owner_id=1, title="机器学习", source_type="generated")
    repo = FakeMaterialRepository(courses=[course])
    service = make_service(repo, tmp_path)
    uploaded = upload_bytes(service, make_user(), "delete-me.txt", b"delete", "text/plain", course_id=101)
    material_id = int(as_dict(uploaded)["id"])
    storage_path = service.storage.local_path(repo.materials[0].storage_path)

    service.delete_material(make_user(), material_id)

    assert repo.materials == []
    assert repo.chunks == []
    assert repo.links == []
    assert storage_path is not None and not storage_path.exists()

    from backend.app.services.materials import MaterialNotFoundError

    with pytest.raises(MaterialNotFoundError):
        service.delete_material(make_user(2), material_id)


def test_delete_material_keeps_database_record_when_storage_cleanup_fails(tmp_path: Path, monkeypatch) -> None:
    repo = FakeMaterialRepository()
    service = make_service(repo, tmp_path)
    uploaded = upload_bytes(service, make_user(), "retry-delete.txt", b"delete", "text/plain")
    material_id = int(as_dict(uploaded)["id"])

    def fail_delete(_path: str) -> None:
        raise OSError("storage unavailable")

    monkeypatch.setattr(service.storage, "delete", fail_delete)

    with pytest.raises(OSError, match="storage unavailable"):
        service.delete_material(make_user(), material_id)

    assert [material.id for material in repo.materials] == [material_id]


def test_material_detail_summarizes_sections_pages_and_owned_courses(tmp_path: Path) -> None:
    course = Course(id=101, owner_id=1, title="机器学习", source_type="generated")
    other_course = Course(id=202, owner_id=2, title="其他用户课程", source_type="generated")
    repo = FakeMaterialRepository(courses=[course, other_course])
    service = make_service(repo, tmp_path)
    uploaded = upload_bytes(service, make_user(), "notes.md", "# 第一章\n监督学习\n\n# 第二章\n模型评估".encode(), "text/markdown")
    material_id = int(as_dict(uploaded)["id"])
    repo.add_link(CourseMaterialLink(course_id=101, material_id=material_id, added_by_user_id=1, usage_type="reference"))
    repo.add_link(CourseMaterialLink(course_id=202, material_id=material_id, added_by_user_id=2, usage_type="reference"))
    for index, chunk in enumerate(repo.chunks, start=1):
        chunk.page_number = index

    detail = as_dict(service.get_material(make_user(), material_id))

    assert detail["chunk_count"] == len(repo.chunks)
    assert detail["section_count"] == len(repo.chunks)
    assert detail["page_count"] == len(repo.chunks)
    assert detail["linked_courses"] == [{"id": "101", "title": "机器学习", "usage_type": "reference"}]


def test_outline_edits_are_versioned_and_confirmation_controls_included_chunks(tmp_path: Path) -> None:
    material = Material(
        id=1,
        user_id=1,
        filename="notes.md",
        storage_path="user_1/notes.md",
        content_type="text/markdown",
        parse_status="completed",
        ingestion_status="awaiting_confirmation",
        outline_version=1,
        outline_json={
            "confirmed": False,
            "sections": [
                {"id": "section-1", "title": "第一章", "level": 1, "path": ["第一章"], "start_page": 1, "end_page": 2, "confidence": 0.9, "included": True, "chunk_indexes": [0, 1]},
                {"id": "section-2", "title": "附录", "level": 1, "path": ["附录"], "start_page": 3, "end_page": 3, "confidence": 0.9, "included": True, "chunk_indexes": [2]},
            ],
        },
        quality_json={"passed": True, "warnings": []},
        metadata_json={},
    )
    chunks = [
        MaterialChunk(
            id=index + 1,
            material_id=1,
            chunk_index=index,
            section_title="第一章" if index < 2 else "附录",
            page_number=index + 1,
            end_page_number=index + 1,
            section_path_json=["第一章" if index < 2 else "附录"],
            chunk_type="body",
            content=f"正文 {index}",
            metadata_json={"section_id": "section-1" if index < 2 else "section-2"},
            quality_json={},
        )
        for index in range(3)
    ]
    repo = FakeMaterialRepository(materials=[material], chunks=chunks, next_material_id=2)
    service = make_service(repo, tmp_path)

    updated = service.update_outline(
        make_user(),
        1,
        UpdateMaterialOutlineRequest(
            version=1,
            operations=[
                MaterialOutlineOperation(type="rename", section_id="section-1", title="第一章 线性表"),
                MaterialOutlineOperation(type="include", section_id="section-2", included=False),
                MaterialOutlineOperation(type="split", section_id="section-1", chunk_index=1, title="链表"),
            ],
        ),
    )

    assert updated.version == 2
    assert updated.confirmed is False
    assert [section.title for section in updated.sections] == ["第一章 线性表", "链表", "附录"]
    assert chunks[1].section_title == "链表"

    merged = service.update_outline(
        make_user(),
        1,
        UpdateMaterialOutlineRequest(
            version=2,
            operations=[
                MaterialOutlineOperation(
                    type="merge",
                    section_ids=["section-1", "section-3"],
                    title="第一章 线性表与链表",
                )
            ],
        ),
    )

    assert merged.version == 3
    assert [section.title for section in merged.sections] == ["第一章 线性表与链表", "附录"]

    confirmed = service.confirm_outline(make_user(), 1, version=3)

    assert confirmed.confirmed is True
    assert material.ingestion_status == "confirmed"
    assert chunks[0].quality_json["included"] is True
    assert chunks[1].quality_json["included"] is True
    assert chunks[2].quality_json["included"] is False

    from backend.app.services.materials import MaterialValidationError

    with pytest.raises(MaterialValidationError, match="刷新"):
        service.update_outline(
            make_user(),
            1,
            UpdateMaterialOutlineRequest(
                version=1,
                operations=[MaterialOutlineOperation(type="rename", section_id="section-1", title="过期修改")],
            ),
        )

    material.parse_status = "pending"
    material.ingestion_status = "running"
    with pytest.raises(MaterialValidationError, match="正在解析"):
        service.confirm_outline(make_user(), 1, version=3)


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
    app.dependency_overrides[get_material_job_service] = lambda: FakeMaterialJobService()
    client = TestClient(app)
    token = create_access_token(str(user.id), settings=settings)

    response = client.post(
        "/api/v1/materials/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("route-notes.txt", b"route text", "text/plain")},
    )

    assert response.status_code == 200
    assert response.json()["data"]["filename"] == "route-notes.txt"
    assert response.json()["data"]["parse_status"] == "pending"
    assert response.json()["data"]["ingestion_job_id"] == "901"
    assert response.json()["data"]["ingestion_status"] == "pending"

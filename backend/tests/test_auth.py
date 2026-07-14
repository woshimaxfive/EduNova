from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.api.v1.deps import get_auth_repository
from backend.app.core.config import Settings
from backend.app.core.security import (
    create_access_token,
    hash_password,
    parse_access_token,
    verify_password,
)
from backend.app.main import create_app
from backend.app.models import Course, CourseMaterialLink, Material, User
from backend.app.services.auth import (
    AuthService,
    DuplicateAccountError,
    InvalidDisplayNameError,
    InvalidCredentialsError,
    PasswordUnchangedError,
    UserNotFoundError,
    WeakPasswordError,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass
class InMemoryAuthRepository:
    users_by_account: dict[str, User] = field(default_factory=dict)
    users_by_id: dict[int, User] = field(default_factory=dict)
    courses: list[Course] = field(default_factory=list)
    materials: list[Material] = field(default_factory=list)
    material_links: list[CourseMaterialLink] = field(default_factory=list)
    next_user_id: int = 1
    next_course_id: int = 1
    next_material_id: int = 1
    next_material_link_id: int = 1

    def get_user_by_account(self, account: str) -> User | None:
        return self.users_by_account.get(account)

    def get_user_by_id(self, user_id: int) -> User | None:
        return self.users_by_id.get(user_id)

    def get_course_for_user(self, user: User, title: str, source_type: str) -> Course | None:
        return next(
            (
                course
                for course in self.courses
                if course.owner is user and course.title == title and course.source_type == source_type
            ),
            None,
        )

    def add_user(self, user: User) -> None:
        user.id = self.next_user_id
        self.next_user_id += 1
        self.users_by_account[user.account] = user
        self.users_by_id[user.id] = user

    def add_course(self, course: Course) -> None:
        course.id = self.next_course_id
        self.next_course_id += 1
        for index, material in enumerate(course.materials, start=1):
            material.id = index
        for index, point in enumerate(course.knowledge_points, start=1):
            point.id = index
        for index, chunk in enumerate(course.knowledge_chunks, start=1):
            chunk.id = index
        self.courses.append(course)

    def add_material(self, material: Material) -> None:
        material.id = self.next_material_id
        self.next_material_id += 1
        self.materials.append(material)

    def add_course_material_link(self, link: CourseMaterialLink) -> None:
        link.id = self.next_material_link_id
        self.next_material_link_id += 1
        self.material_links.append(link)

    def flush(self) -> None:
        return None

    def refresh(self, user: User) -> None:
        return None

    def commit(self) -> None:
        return None

    def rollback(self) -> None:
        return None


def make_service(repo: InMemoryAuthRepository | None = None) -> AuthService:
    return AuthService(
        repository=repo or InMemoryAuthRepository(),
        settings=Settings(
            _env_file=None,
            jwt_secret="test-secret-with-32-bytes-minimum",
            jwt_expire_minutes=30,
        ),
    )


def test_password_hashing_and_jwt_roundtrip() -> None:
    settings = Settings(
        _env_file=None,
        jwt_secret="test-secret-with-32-bytes-minimum",
        jwt_expire_minutes=30,
    )
    password_hash = hash_password("Password123")

    assert password_hash != "Password123"
    assert verify_password("Password123", password_hash)
    assert not verify_password("wrong-password", password_hash)

    token = create_access_token(subject="42", settings=settings)

    assert parse_access_token(token, settings=settings) == "42"


def test_register_blank_creates_user_without_starter_course() -> None:
    repo = InMemoryAuthRepository()
    user = make_service(repo).register(
        account="Blank",
        password="Password123",
        display_name="空白学习者",
        starter_mode="blank",
    )

    assert user.account == "blank"
    assert user.display_name == "空白学习者"
    assert user.starter_mode == "blank"
    assert repo.courses == []


def test_register_data_structures_copies_internal_course_without_library_materials() -> None:
    repo = InMemoryAuthRepository()
    user = make_service(repo).register(
        account="starter",
        password="Password123",
        display_name="示例学习者",
        starter_mode="data_structures",
    )

    assert user.starter_mode == "data_structures"
    assert len(repo.courses) == 1
    course = repo.courses[0]
    assert course.owner is user
    assert course.title == "数据结构与算法"
    assert len(course.materials) == 9
    assert all(material.user is user for material in course.materials)
    assert all(material.storage_path.startswith("builtin://") for material in course.materials)
    assert len(course.knowledge_points) == 54
    assert len(course.knowledge_chunks) == 178
    assert all(chunk.course is course for chunk in course.knowledge_chunks)
    assert all(
        prerequisite_id in {point.id for point in course.knowledge_points}
        for point in course.knowledge_points
        for prerequisite_id in point.prerequisites_json
    )
    assert repo.materials == []
    assert repo.material_links == []


def test_register_rejects_duplicate_account_and_weak_password() -> None:
    service = make_service()
    service.register(
        account="student",
        password="Password123",
        display_name="学生",
        starter_mode="blank",
    )

    with pytest.raises(DuplicateAccountError):
        service.register(
            account="STUDENT",
            password="Password123",
            display_name="重复学生",
            starter_mode="blank",
        )

    with pytest.raises(WeakPasswordError):
        service.register(
            account="weak",
            password="short",
            display_name="弱密码",
            starter_mode="blank",
        )


def test_login_rejects_wrong_password() -> None:
    service = make_service()
    service.register(
        account="student",
        password="Password123",
        display_name="学生",
        starter_mode="blank",
    )

    with pytest.raises(InvalidCredentialsError):
        service.login(account="student", password="WrongPassword123")


def test_update_display_name_trims_and_rejects_blank() -> None:
    repo = InMemoryAuthRepository()
    service = make_service(repo)
    user = service.register(
        account="nickname",
        password="Password123",
        display_name="旧昵称",
        starter_mode="blank",
    )

    updated_user = service.update_display_name(user, "  新昵称  ")

    assert updated_user.display_name == "新昵称"
    assert repo.users_by_id[user.id].display_name == "新昵称"

    with pytest.raises(InvalidDisplayNameError):
        service.update_display_name(user, "   ")


def test_change_password_invalidates_existing_tokens_and_accepts_new_password() -> None:
    repo = InMemoryAuthRepository()
    service = make_service(repo)
    user = service.register(
        account="password",
        password="Password123",
        display_name="密码学生",
        starter_mode="blank",
    )
    old_token = service.login(user.account, "Password123").access_token

    service.change_password(user, "Password123", "NewPassword456")

    assert user.auth_version == 1
    assert verify_password("NewPassword456", user.hashed_password)
    assert not verify_password("Password123", user.hashed_password)
    with pytest.raises(UserNotFoundError, match="登录状态已失效"):
        service.get_user_by_token(old_token)
    with pytest.raises(InvalidCredentialsError):
        service.login(user.account, "Password123")
    assert service.get_user_by_token(service.login(user.account, "NewPassword456").access_token) is user


def test_change_password_rejects_wrong_current_weak_and_unchanged_passwords() -> None:
    service = make_service()
    user = service.register(
        account="password_rules",
        password="Password123",
        display_name="密码规则学生",
        starter_mode="blank",
    )

    with pytest.raises(InvalidCredentialsError, match="当前密码不正确"):
        service.change_password(user, "WrongPassword123", "NewPassword456")
    with pytest.raises(WeakPasswordError):
        service.change_password(user, "Password123", "weak")
    with pytest.raises(PasswordUnchangedError):
        service.change_password(user, "Password123", "Password123")


def test_auth_routes_register_login_me_and_logout() -> None:
    repo = InMemoryAuthRepository()
    app = create_app()
    app.dependency_overrides[get_auth_repository] = lambda: repo
    client = TestClient(app)

    register_response = client.post(
        "/api/v1/auth/register",
        json={
            "account": "api_user",
            "password": "Password123",
            "display_name": "接口学生",
            "starter_mode": "data_structures",
        },
    )

    assert register_response.status_code == 200
    assert register_response.json()["data"] == {
        "id": 1,
        "account": "api_user",
        "display_name": "接口学生",
        "role": "student",
        "starter_mode": "data_structures",
    }
    assert len(repo.courses) == 1

    login_response = client.post(
        "/api/v1/auth/login",
        json={"account": "api_user", "password": "Password123"},
    )

    assert login_response.status_code == 200
    login_data = login_response.json()["data"]
    assert login_data["token_type"] == "bearer"
    assert login_data["access_token"]
    assert login_data["user"]["display_name"] == "接口学生"

    me_response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {login_data['access_token']}"},
    )

    assert me_response.status_code == 200
    assert me_response.json()["data"]["account"] == "api_user"

    update_response = client.patch(
        "/api/v1/auth/me",
        json={"display_name": "  新接口学生  "},
        headers={"Authorization": f"Bearer {login_data['access_token']}"},
    )

    assert update_response.status_code == 200
    assert update_response.json()["data"]["display_name"] == "新接口学生"

    updated_me_response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {login_data['access_token']}"},
    )

    assert updated_me_response.status_code == 200
    assert updated_me_response.json()["data"]["display_name"] == "新接口学生"

    wrong_password_response = client.patch(
        "/api/v1/auth/me/password",
        json={"current_password": "WrongPassword123", "new_password": "NewPassword456"},
        headers={"Authorization": f"Bearer {login_data['access_token']}"},
    )

    assert wrong_password_response.status_code == 400
    assert wrong_password_response.json()["error"]["code"] == "INVALID_CURRENT_PASSWORD"

    password_response = client.patch(
        "/api/v1/auth/me/password",
        json={"current_password": "Password123", "new_password": "NewPassword456"},
        headers={"Authorization": f"Bearer {login_data['access_token']}"},
    )

    assert password_response.status_code == 200
    assert password_response.json()["data"] == {"ok": True}

    expired_token_response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {login_data['access_token']}"},
    )
    assert expired_token_response.status_code == 401

    replacement_login_response = client.post(
        "/api/v1/auth/login",
        json={"account": "api_user", "password": "NewPassword456"},
    )
    assert replacement_login_response.status_code == 200
    replacement_token = replacement_login_response.json()["data"]["access_token"]

    logout_response = client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {replacement_token}"},
    )

    assert logout_response.status_code == 200
    assert logout_response.json()["data"] == {"ok": True}

    missing_token_response = client.get("/api/v1/auth/me")

    assert missing_token_response.status_code == 401
    assert missing_token_response.json()["error"]["code"] == "UNAUTHORIZED"


def test_user_starter_mode_model_and_migration_contract() -> None:
    assert User.__table__.c.starter_mode.default.arg == "blank"
    assert User.__table__.c.starter_mode.nullable is False

    migration_text = (
        REPO_ROOT
        / "backend"
        / "migrations"
        / "versions"
        / "20260701_0004_add_user_starter_mode.py"
    ).read_text(encoding="utf-8")

    assert "starter_mode" in migration_text
    assert "server_default=\"blank\"" in migration_text

    settings_migration_text = (
        REPO_ROOT
        / "backend"
        / "migrations"
        / "versions"
        / "20260713_0017_complete_settings_center.py"
    ).read_text(encoding="utf-8")

    assert "auth_version" in settings_migration_text
    assert "connection_test_json" in settings_migration_text

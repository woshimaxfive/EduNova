from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.config import Settings, get_settings
from backend.app.core.security import (
    create_access_token,
    hash_password,
    parse_access_token,
    verify_password,
)
from backend.app.data.builtin_courses.ai_intro import BUILTIN_AI_INTRO_COURSE
from backend.app.models import Course, User
from backend.app.services.course_seed import build_builtin_ai_intro_course_graph


class DuplicateEmailError(Exception):
    pass


class WeakPasswordError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


class UserNotFoundError(Exception):
    pass


class AuthRepository(Protocol):
    def get_user_by_email(self, email: str) -> User | None:
        ...

    def get_user_by_id(self, user_id: int) -> User | None:
        ...

    def get_course_for_user(
        self,
        user: User,
        title: str,
        source_type: str,
    ) -> Course | None:
        ...

    def add_user(self, user: User) -> None:
        ...

    def add_course(self, course: Course) -> None:
        ...

    def flush(self) -> None:
        ...

    def refresh(self, instance: object) -> None:
        ...

    def commit(self) -> None:
        ...

    def rollback(self) -> None:
        ...


class SqlAlchemyAuthRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_user_by_email(self, email: str) -> User | None:
        return self.db.scalar(select(User).where(User.email == email))

    def get_user_by_id(self, user_id: int) -> User | None:
        return self.db.get(User, user_id)

    def get_course_for_user(
        self,
        user: User,
        title: str,
        source_type: str,
    ) -> Course | None:
        return self.db.scalar(
            select(Course).where(
                Course.owner_id == user.id,
                Course.title == title,
                Course.source_type == source_type,
            )
        )

    def add_user(self, user: User) -> None:
        self.db.add(user)

    def add_course(self, course: Course) -> None:
        self.db.add(course)

    def flush(self) -> None:
        self.db.flush()

    def refresh(self, instance: object) -> None:
        self.db.refresh(instance)

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()


@dataclass(frozen=True)
class LoginResult:
    access_token: str
    user: User


class AuthService:
    def __init__(
        self,
        repository: AuthRepository,
        settings: Settings | None = None,
    ) -> None:
        self.repository = repository
        self.settings = settings or get_settings()

    def register(
        self,
        email: str,
        password: str,
        display_name: str,
        starter_mode: str = "ai_intro",
    ) -> User:
        normalized_email = email.strip().lower()
        normalized_name = display_name.strip() or normalized_email.split("@", 1)[0]
        mode = starter_mode or "ai_intro"

        self._validate_starter_mode(mode)
        self._validate_password(password)
        if self.repository.get_user_by_email(normalized_email) is not None:
            raise DuplicateEmailError("邮箱已注册。")

        user = User(
            email=normalized_email,
            hashed_password=hash_password(password),
            display_name=normalized_name,
            role="student",
            starter_mode=mode,
        )

        try:
            self.repository.add_user(user)
            self.repository.flush()
            if mode == "ai_intro":
                self._copy_ai_intro_course(user)
            self.repository.commit()
            self.repository.refresh(user)
        except Exception:
            self.repository.rollback()
            raise

        return user

    def login(self, email: str, password: str) -> LoginResult:
        user = self.repository.get_user_by_email(email.strip().lower())
        if user is None or not verify_password(password, user.hashed_password):
            raise InvalidCredentialsError("邮箱或密码不正确。")

        return LoginResult(
            access_token=create_access_token(str(user.id), settings=self.settings),
            user=user,
        )

    def get_user_by_token(self, token: str) -> User:
        subject = parse_access_token(token, settings=self.settings)
        try:
            user_id = int(subject)
        except ValueError as exc:
            raise UserNotFoundError("登录凭证中的用户不存在。") from exc

        user = self.repository.get_user_by_id(user_id)
        if user is None:
            raise UserNotFoundError("登录凭证中的用户不存在。")
        return user

    def _copy_ai_intro_course(self, user: User) -> Course:
        existing = self.repository.get_course_for_user(
            user,
            title=BUILTIN_AI_INTRO_COURSE["title"],
            source_type=BUILTIN_AI_INTRO_COURSE["source_type"],
        )
        if existing is not None:
            return existing

        course = build_builtin_ai_intro_course_graph(user)
        course.visibility = "private"
        for material in course.materials:
            material.metadata_json = {
                **material.metadata_json,
                "owner_scope": "registered_user",
            }
        for chunk in course.knowledge_chunks:
            chunk.metadata_json = {
                **chunk.metadata_json,
                "source": "starter_copy",
            }
        self.repository.add_course(course)
        self.repository.flush()
        return course

    @staticmethod
    def _validate_starter_mode(mode: str) -> None:
        if mode not in {"blank", "ai_intro"}:
            raise ValueError("starter_mode 只能是 blank 或 ai_intro。")

    @staticmethod
    def _validate_password(password: str) -> None:
        has_letter = any(char.isalpha() for char in password)
        has_digit = any(char.isdigit() for char in password)
        if len(password) < 8 or not has_letter or not has_digit:
            raise WeakPasswordError("密码至少 8 位，并同时包含字母和数字。")

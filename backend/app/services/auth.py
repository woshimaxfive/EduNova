from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import re
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.config import Settings, get_settings
from backend.app.core.security import (
    create_access_token,
    hash_password,
    parse_access_token_claims,
    verify_password,
)
from backend.app.data.builtin_courses.data_structures import BUILTIN_DATA_STRUCTURES_COURSE
from backend.app.models import Course, CourseEnrollment, User
from backend.app.services.course_seed import (
    build_builtin_data_structures_course_graph,
    finalize_builtin_course_graph,
)


class DuplicateAccountError(Exception):
    pass


class WeakPasswordError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


class UserNotFoundError(Exception):
    pass


class InvalidDisplayNameError(Exception):
    pass


class PasswordUnchangedError(Exception):
    pass


class AuthRepository(Protocol):
    def get_user_by_account(self, account: str) -> User | None:
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

    def get_user_by_account(self, account: str) -> User | None:
        return self.db.scalar(select(User).where(User.account == account))

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
        account: str,
        password: str,
        display_name: str,
        starter_mode: str = "blank",
    ) -> User:
        normalized_account = account.strip().lower()
        normalized_name = display_name.strip() or normalized_account
        mode = starter_mode or "blank"

        self._validate_starter_mode(mode)
        self._validate_account(normalized_account)
        self._validate_password(password)
        if self.repository.get_user_by_account(normalized_account) is not None:
            raise DuplicateAccountError("账号已被使用。")

        user = User(
            account=normalized_account,
            hashed_password=hash_password(password),
            display_name=normalized_name,
            role="student",
            starter_mode=mode,
        )

        try:
            self.repository.add_user(user)
            self.repository.flush()
            if mode == "data_structures":
                self._copy_data_structures_course(user)
            self.repository.commit()
            self.repository.refresh(user)
        except Exception:
            self.repository.rollback()
            raise

        return user

    def login(self, account: str, password: str) -> LoginResult:
        user = self.repository.get_user_by_account(account.strip().lower())
        if user is None or not verify_password(password, user.hashed_password):
            raise InvalidCredentialsError("账号或密码不正确。")

        return LoginResult(
            access_token=create_access_token(
                str(user.id),
                settings=self.settings,
                auth_version=int(user.auth_version or 0),
            ),
            user=user,
        )

    def get_user_by_token(self, token: str) -> User:
        claims = parse_access_token_claims(token, settings=self.settings)
        try:
            user_id = int(claims.subject)
        except ValueError as exc:
            raise UserNotFoundError("登录凭证中的用户不存在。") from exc

        user = self.repository.get_user_by_id(user_id)
        if user is None:
            raise UserNotFoundError("登录凭证中的用户不存在。")
        if claims.auth_version != int(user.auth_version or 0):
            raise UserNotFoundError("登录状态已失效，请重新登录。")
        return user

    def update_display_name(self, user: User, display_name: str) -> User:
        normalized_name = display_name.strip()
        if not normalized_name:
            raise InvalidDisplayNameError("昵称不能为空。")
        if len(normalized_name) > 100:
            raise InvalidDisplayNameError("昵称不能超过 100 个字符。")

        user.display_name = normalized_name
        try:
            self.repository.commit()
            self.repository.refresh(user)
        except Exception:
            self.repository.rollback()
            raise

        return user

    def change_password(self, user: User, current_password: str, new_password: str) -> None:
        if not verify_password(current_password, user.hashed_password):
            raise InvalidCredentialsError("当前密码不正确。")
        if verify_password(new_password, user.hashed_password):
            raise PasswordUnchangedError("新密码不能与当前密码相同。")
        self._validate_password(new_password)

        user.hashed_password = hash_password(new_password)
        user.auth_version = int(user.auth_version or 0) + 1
        try:
            self.repository.commit()
        except Exception:
            self.repository.rollback()
            raise

    def _copy_data_structures_course(self, user: User) -> Course:
        existing = self.repository.get_course_for_user(
            user,
            title=BUILTIN_DATA_STRUCTURES_COURSE["title"],
            source_type=BUILTIN_DATA_STRUCTURES_COURSE["source_type"],
        )
        if existing is not None:
            return existing

        course = build_builtin_data_structures_course_graph(user)
        course.visibility = "private"
        course.enrollments.append(
            CourseEnrollment(
                user=user,
                role="learner",
                learning_status="active",
                last_accessed_at=datetime.now(UTC),
                learning_context_json={},
                learning_context_confidence_json={},
            )
        )
        self.repository.add_course(course)
        self.repository.flush()
        finalize_builtin_course_graph(course)
        self.repository.flush()
        return course

    @staticmethod
    def _validate_account(account: str) -> None:
        if not re.fullmatch(r"[a-z0-9][a-z0-9_]{3,23}", account):
            raise ValueError("账号需为 4 至 24 位字母、数字或下划线，并以字母或数字开头。")

    @staticmethod
    def _validate_starter_mode(mode: str) -> None:
        if mode not in {"blank", "data_structures"}:
            raise ValueError("starter_mode 只能是 blank 或 data_structures。")

    @staticmethod
    def _validate_password(password: str) -> None:
        has_letter = any(char.isalpha() for char in password)
        has_digit = any(char.isdigit() for char in password)
        if len(password) < 8 or not has_letter or not has_digit:
            raise WeakPasswordError("密码至少 8 位，并同时包含字母和数字。")

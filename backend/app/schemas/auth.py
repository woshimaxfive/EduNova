from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from backend.app.models import User


StarterMode = Literal["blank", "ai_intro"]


class ApiUser(BaseModel):
    id: int
    email: str
    display_name: str
    role: Literal["student", "admin"]
    starter_mode: StarterMode


class RegisterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=255)
    display_name: str = Field(min_length=1, max_length=100)
    starter_mode: StarterMode = "ai_intro"

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        email = value.strip().lower()
        if "@" not in email:
            raise ValueError("请输入有效邮箱。")
        return email

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(cls, value: str) -> str:
        return value.strip()


class UpdateCurrentUserRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=100)

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(cls, value: str) -> str:
        display_name = value.strip()
        if not display_name:
            raise ValueError("昵称不能为空。")
        return display_name


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=255)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


def user_to_api(user: User) -> ApiUser:
    return ApiUser(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        starter_mode=user.starter_mode,
    )

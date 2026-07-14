from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from backend.app.models import User


StarterMode = Literal["blank", "data_structures"]


class ApiUser(BaseModel):
    id: int
    account: str
    display_name: str
    role: Literal["student", "admin"]
    starter_mode: StarterMode


class RegisterRequest(BaseModel):
    account: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=255)
    display_name: str = Field(min_length=1, max_length=100)
    starter_mode: StarterMode = "blank"

    @field_validator("account")
    @classmethod
    def normalize_account(cls, value: str) -> str:
        account = value.strip().lower()
        if not re.fullmatch(r"[a-z0-9][a-z0-9_]{3,23}", account):
            raise ValueError("账号需为 4 至 24 位字母、数字或下划线，并以字母或数字开头。")
        return account

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


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=255)
    new_password: str = Field(min_length=1, max_length=255)


class LoginRequest(BaseModel):
    account: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=255)

    @field_validator("account")
    @classmethod
    def normalize_account(cls, value: str) -> str:
        return value.strip().lower()


def user_to_api(user: User) -> ApiUser:
    return ApiUser(
        id=user.id,
        account=user.account,
        display_name=user.display_name,
        role=user.role,
        starter_mode=user.starter_mode,
    )

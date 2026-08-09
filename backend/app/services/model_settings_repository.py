from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from backend.app.models import ModelSetting


class SqlAlchemyModelSettingsRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_for_user(self, user_id: int) -> ModelSetting | None:
        return self.get_default_for_user(user_id) or self._first_for_user(user_id)

    def get_default_for_user(self, user_id: int) -> ModelSetting | None:
        return self.db.scalar(
            select(ModelSetting)
            .where(ModelSetting.user_id == user_id, ModelSetting.is_default.is_(True))
            .order_by(ModelSetting.updated_at.desc(), ModelSetting.id.desc())
        )

    def get_generation_default_for_user(self, user_id: int) -> ModelSetting | None:
        return self.db.scalar(
            select(ModelSetting)
            .where(ModelSetting.user_id == user_id, ModelSetting.is_generation_default.is_(True))
            .order_by(ModelSetting.updated_at.desc(), ModelSetting.id.desc())
        )

    def get_embedding_default_for_user(self, user_id: int) -> ModelSetting | None:
        return self.db.scalar(
            select(ModelSetting)
            .where(ModelSetting.user_id == user_id, ModelSetting.is_embedding_default.is_(True))
            .order_by(ModelSetting.updated_at.desc(), ModelSetting.id.desc())
        )

    def get_rerank_default_for_user(self, user_id: int) -> ModelSetting | None:
        return self.db.scalar(
            select(ModelSetting)
            .where(ModelSetting.user_id == user_id, ModelSetting.is_rerank_default.is_(True))
            .order_by(ModelSetting.updated_at.desc(), ModelSetting.id.desc())
        )

    def get_vision_default_for_user(self, user_id: int) -> ModelSetting | None:
        return self.db.scalar(
            select(ModelSetting)
            .where(ModelSetting.user_id == user_id, ModelSetting.is_vision_default.is_(True))
            .order_by(ModelSetting.updated_at.desc(), ModelSetting.id.desc())
        )

    def list_for_user(self, user_id: int) -> list[ModelSetting]:
        return list(
            self.db.scalars(
                select(ModelSetting)
                .where(ModelSetting.user_id == user_id)
                .order_by(
                    ModelSetting.is_default.desc(),
                    ModelSetting.is_generation_default.desc(),
                    ModelSetting.is_embedding_default.desc(),
                    ModelSetting.is_rerank_default.desc(),
                    ModelSetting.is_vision_default.desc(),
                    ModelSetting.updated_at.desc(),
                    ModelSetting.id.desc(),
                )
            )
        )

    def get_by_id_for_user(self, setting_id: int, user_id: int) -> ModelSetting | None:
        return self.db.scalar(
            select(ModelSetting).where(ModelSetting.id == setting_id, ModelSetting.user_id == user_id)
        )

    def save(self, setting: ModelSetting) -> None:
        self.db.add(setting)
        self.db.flush()

    def delete(self, setting: ModelSetting) -> None:
        self.db.delete(setting)
        self.db.flush()

    def unset_defaults_for_user(self, user_id: int, except_setting_id: int | None = None) -> None:
        statement = update(ModelSetting).where(ModelSetting.user_id == user_id)
        if except_setting_id is not None:
            statement = statement.where(ModelSetting.id != except_setting_id)
        self.db.execute(statement.values(is_default=False))

    def unset_generation_defaults_for_user(self, user_id: int, except_setting_id: int | None = None) -> None:
        statement = update(ModelSetting).where(ModelSetting.user_id == user_id)
        if except_setting_id is not None:
            statement = statement.where(ModelSetting.id != except_setting_id)
        self.db.execute(statement.values(is_generation_default=False))

    def unset_embedding_defaults_for_user(self, user_id: int, except_setting_id: int | None = None) -> None:
        statement = update(ModelSetting).where(ModelSetting.user_id == user_id)
        if except_setting_id is not None:
            statement = statement.where(ModelSetting.id != except_setting_id)
        self.db.execute(statement.values(is_embedding_default=False))

    def unset_rerank_defaults_for_user(self, user_id: int, except_setting_id: int | None = None) -> None:
        statement = update(ModelSetting).where(ModelSetting.user_id == user_id)
        if except_setting_id is not None:
            statement = statement.where(ModelSetting.id != except_setting_id)
        self.db.execute(statement.values(is_rerank_default=False))

    def unset_vision_defaults_for_user(self, user_id: int, except_setting_id: int | None = None) -> None:
        statement = update(ModelSetting).where(ModelSetting.user_id == user_id)
        if except_setting_id is not None:
            statement = statement.where(ModelSetting.id != except_setting_id)
        self.db.execute(statement.values(is_vision_default=False))

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()

    def _first_for_user(self, user_id: int) -> ModelSetting | None:
        return self.db.scalar(
            select(ModelSetting)
            .where(ModelSetting.user_id == user_id)
            .order_by(ModelSetting.updated_at.desc(), ModelSetting.id.desc())
        )

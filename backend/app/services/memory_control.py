"""Domain memory controls. User row locks serialize all writes and deletion barriers."""
from datetime import UTC, datetime

from sqlalchemy import delete, func, select, update

from backend.app.models import ConversationMemoryEntry, LearningMemoryFact, MemorySuppression, User, UserPrivacySetting
from backend.app.schemas.memory import MemoryActionResult, MemoryExport, MemoryItem, MemoryPage


class MemoryControlError(ValueError):
    def __init__(self, message: str, status_code: int = 409):
        super().__init__(message)
        self.status_code = status_code


def lock_memory_settings(db, user_id: int) -> UserPrivacySetting:
    if db.scalar(select(User.id).where(User.id == user_id).with_for_update()) is None:
        raise MemoryControlError("账号不存在。", 404)
    setting = db.scalar(select(UserPrivacySetting).where(UserPrivacySetting.user_id == user_id)
                        .execution_options(populate_existing=True))
    if setting is None:
        setting = UserPrivacySetting(user_id=user_id, conversation_memory_enabled=True, memory_revision=0)
        db.add(setting)
        db.flush()
    return setting


def memory_item(row, layer: str) -> MemoryItem:
    episode = layer == "episode"
    return MemoryItem(
        id=str(row.id), layer=layer, category="episode" if episode else row.category,
        content=row.summary if episode else row.content, topic=row.topic if episode else row.category,
        source="历史会话摘要（用户已纠正）" if episode and row.revision > 1 else (
            "历史会话摘要" if episode else "用户在设置页明确确认"),
        session_id=str(row.session_id) if episode else None,
        user_message_id=str(row.user_message_id) if episode else None,
        assistant_message_id=str(row.assistant_message_id) if episode else None,
        created_at=row.created_at, updated_at=row.updated_at, revision=row.revision,
        indexed=episode and row.embedding is not None,
    )


class MemoryControlService:
    def __init__(self, db):
        self.db = db

    @staticmethod
    def _model(layer):
        return ConversationMemoryEntry if layer == "episode" else LearningMemoryFact

    def list_items(self, user_id, layer, page=1, page_size=20):
        model = self._model(layer)
        total = self.db.scalar(select(func.count(model.id)).where(model.user_id == user_id)) or 0
        rows = self.db.scalars(select(model).where(model.user_id == user_id)
                               .order_by(model.updated_at.desc(), model.id.desc())
                               .offset((page - 1) * page_size).limit(page_size))
        return MemoryPage(items=[memory_item(row, layer) for row in rows], total=total, page=page, page_size=page_size)

    def export(self, user_id):
        # Hold the same per-account lock as writers for the full export snapshot.
        lock_memory_settings(self.db, user_id)
        items = []
        for layer in ("episode", "fact"):
            model = self._model(layer)
            items.extend(memory_item(row, layer) for row in self.db.scalars(
                select(model).where(model.user_id == user_id).order_by(model.id)))
        result = MemoryExport(exported_at=datetime.now(UTC), items=items)
        self.db.commit()
        return result

    def _owned(self, user_id, layer, item_id):
        model = self._model(layer)
        row = self.db.scalar(select(model).where(model.id == item_id, model.user_id == user_id)
                             .execution_options(populate_existing=True))
        if row is None:
            raise MemoryControlError("记忆不存在或已删除。", 404)
        return row

    def create_fact(self, user_id, payload):
        from backend.app.services.conversation_memory import ConversationMemoryService
        setting = lock_memory_settings(self.db, user_id)
        content = ConversationMemoryService.redact(payload.content)
        existing = self.db.scalar(select(LearningMemoryFact).where(
            LearningMemoryFact.user_id == user_id, LearningMemoryFact.category == payload.category,
            LearningMemoryFact.content == content))
        if existing is not None:
            result = memory_item(existing, "fact")
            self.db.commit()
            return result
        row = LearningMemoryFact(user_id=user_id, category=payload.category, content=content)
        self.db.add(row)
        setting.memory_revision += 1
        self.db.flush()
        result = memory_item(row, "fact")
        self.db.commit()
        return result

    def correct(self, user_id, layer, item_id, payload):
        from backend.app.services.conversation_memory import ConversationMemoryService
        setting = lock_memory_settings(self.db, user_id)
        row = self._owned(user_id, layer, item_id)
        if row.revision != payload.revision:
            raise MemoryControlError("记忆已被更新，请刷新后重新编辑。")
        if layer == "fact" and len(payload.content) > 500:
            raise MemoryControlError("长期信息不能超过 500 字。", 422)
        content = ConversationMemoryService.redact(payload.content)
        if layer == "episode":
            row.summary = content
            row.topic = content[:120]
            row.embedding = None
        else:
            row.content = content
        row.revision += 1
        row.updated_at = datetime.now(UTC)
        setting.memory_revision += 1
        self.db.flush()
        result = memory_item(row, layer)
        self.db.commit()
        return result

    def remove(self, user_id, layer, item_id, revision):
        setting = lock_memory_settings(self.db, user_id)
        row = self._owned(user_id, layer, item_id)
        if row.revision != revision:
            raise MemoryControlError("记忆已被更新，请刷新后重新删除。")
        if layer == "episode":
            self.db.add(MemorySuppression(user_id=user_id, assistant_message_id=row.assistant_message_id))
        self.db.delete(row)
        setting.memory_revision += 1
        self.db.commit()
        return MemoryActionResult(affected_count=1)

    def clear_indexes(self, user_id):
        setting = lock_memory_settings(self.db, user_id)
        result = self.db.execute(update(ConversationMemoryEntry).where(
            ConversationMemoryEntry.user_id == user_id, ConversationMemoryEntry.embedding.is_not(None)
        ).values(embedding=None).execution_options(synchronize_session="fetch"))
        setting.memory_revision += 1
        self.db.commit()
        return MemoryActionResult(affected_count=result.rowcount)

    def clear_all(self, user_id):
        setting = lock_memory_settings(self.db, user_id)
        # Database time after the lock prevents a worker started before clear from resurrecting content.
        setting.memory_cleared_before = self.db.scalar(select(func.clock_timestamp()))
        setting.memory_revision += 1
        count = 0
        for model in (ConversationMemoryEntry, LearningMemoryFact):
            count += self.db.execute(delete(model).where(model.user_id == user_id)).rowcount
        self.db.commit()
        return MemoryActionResult(affected_count=count)

from __future__ import annotations

import logging
import re
from typing import Any, Protocol

from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from backend.app.models import ChatMessage, ChatSession, ConversationMemoryEntry, User, UserPrivacySetting
from backend.app.services.embeddings import EmbeddingService


logger = logging.getLogger(__name__)


class PrivacySettingsResponse(BaseModel):
    conversation_memory_enabled: bool = True
    indexed_memory_count: int = 0


class UpdatePrivacySettingsRequest(BaseModel):
    conversation_memory_enabled: bool


class ClearConversationMemoryResponse(BaseModel):
    deleted_count: int
    raw_chat_history_preserved: bool = True


class ConversationMemoryQueue(Protocol):
    def enqueue(self, *, user_id: int, session_id: int, user_message_id: int, assistant_message_id: int) -> None: ...
    def enqueue_backfill(self, *, user_id: int) -> None: ...


class RqConversationMemoryQueue:
    def __init__(self, *, redis_url: str, queue_name: str) -> None:
        self.redis_url = redis_url
        self.queue_name = queue_name

    def enqueue(self, *, user_id: int, session_id: int, user_message_id: int, assistant_message_id: int) -> None:
        from redis import Redis
        from rq import Queue

        from backend.app.workers.conversation_memory import index_conversation_memory

        Queue(self.queue_name, connection=Redis.from_url(self.redis_url)).enqueue(
            index_conversation_memory,
            user_id,
            session_id,
            user_message_id,
            assistant_message_id,
            job_id=f"conversation-memory-{assistant_message_id}",
            job_timeout=300,
            result_ttl=3600,
            failure_ttl=86400,
        )

    def enqueue_backfill(self, *, user_id: int) -> None:
        from redis import Redis
        from rq import Queue

        from backend.app.workers.conversation_memory import backfill_conversation_memory

        Queue(self.queue_name, connection=Redis.from_url(self.redis_url)).enqueue(
            backfill_conversation_memory,
            user_id,
            job_id=f"conversation-memory-backfill-{user_id}",
            job_timeout=1800,
            result_ttl=3600,
            failure_ttl=86400,
        )


class ConversationMemoryService:
    def __init__(
        self,
        db: Session,
        embedding_service: EmbeddingService | None = None,
        queue: ConversationMemoryQueue | None = None,
    ) -> None:
        self.db = db
        self.embedding_service = embedding_service
        self.queue = queue

    def get_settings(self, user: User) -> PrivacySettingsResponse:
        setting = self.db.scalar(select(UserPrivacySetting).where(UserPrivacySetting.user_id == user.id))
        count = int(self.db.scalar(
            select(func.count(ConversationMemoryEntry.id)).where(ConversationMemoryEntry.user_id == user.id)
        ) or 0)
        return PrivacySettingsResponse(
            conversation_memory_enabled=True if setting is None else setting.conversation_memory_enabled,
            indexed_memory_count=count,
        )

    def update_settings(self, user: User, enabled: bool) -> PrivacySettingsResponse:
        setting = self.db.scalar(select(UserPrivacySetting).where(UserPrivacySetting.user_id == user.id))
        if setting is None:
            setting = UserPrivacySetting(user_id=user.id, conversation_memory_enabled=enabled)
        else:
            setting.conversation_memory_enabled = enabled
        self.db.add(setting)
        if not enabled:
            self.db.execute(delete(ConversationMemoryEntry).where(ConversationMemoryEntry.user_id == user.id))
        self.db.commit()
        if enabled and self.queue is not None:
            try:
                self.queue.enqueue_backfill(user_id=int(user.id))
            except Exception:
                pass
        return self.get_settings(user)

    def clear(self, user: User) -> ClearConversationMemoryResponse:
        result = self.db.execute(delete(ConversationMemoryEntry).where(ConversationMemoryEntry.user_id == user.id))
        self.db.commit()
        return ClearConversationMemoryResponse(deleted_count=max(0, int(result.rowcount or 0)))

    def index_pair(
        self,
        *,
        user: User,
        session: ChatSession,
        user_message: ChatMessage,
        assistant_message: ChatMessage,
    ) -> bool:
        if not self.get_settings(user).conversation_memory_enabled or self.embedding_service is None:
            return False
        summary = self._safe_summary(user_message.content, assistant_message.content)
        batch = self.embedding_service.embed_documents(user, [summary])
        if batch.status != "completed" or len(batch.vectors) != 1 or not batch.profile_hash:
            return False
        existing = self.db.scalar(
            select(ConversationMemoryEntry).where(
                ConversationMemoryEntry.assistant_message_id == assistant_message.id
            )
        )
        if existing is not None:
            if self._matches_profile(existing, batch):
                return False
            # pgvector is intentionally unbounded here so profiles can migrate
            # between dimensions. Explicitly mark the value dirty before flush;
            # otherwise SQLAlchemy may compare old/new arrays element by element
            # and fail when their lengths differ.
            existing.summary = summary
            existing.embedding = batch.vectors[0]
            flag_modified(existing, "embedding")
            existing.embedding_provider = batch.source
            existing.embedding_model = batch.model
            existing.embedding_dimension = batch.dimension
            existing.embedding_profile_hash = batch.profile_hash
        else:
            self.db.add(
                ConversationMemoryEntry(
                    user_id=user.id,
                    session_id=session.id,
                    user_message_id=user_message.id,
                    assistant_message_id=assistant_message.id,
                    summary=summary,
                    embedding=batch.vectors[0],
                    embedding_provider=batch.source,
                    embedding_model=batch.model,
                    embedding_dimension=batch.dimension,
                    embedding_profile_hash=batch.profile_hash,
                )
            )
        self.db.commit()
        return True

    @staticmethod
    def _matches_profile(entry: ConversationMemoryEntry, batch: Any) -> bool:
        return (
            entry.embedding_provider == batch.source
            and entry.embedding_model == batch.model
            and entry.embedding_dimension == batch.dimension
            and entry.embedding_profile_hash == batch.profile_hash
            and isinstance(entry.embedding, list)
            and len(entry.embedding) == batch.dimension
        )

    def schedule_pair(
        self,
        *,
        user: User,
        session: ChatSession,
        user_message: ChatMessage,
        assistant_message: ChatMessage,
    ) -> bool:
        if not self.get_settings(user).conversation_memory_enabled:
            return False
        if self.queue is None:
            return self.index_pair(
                user=user,
                session=session,
                user_message=user_message,
                assistant_message=assistant_message,
            )
        self.queue.enqueue(
            user_id=int(user.id),
            session_id=int(session.id),
            user_message_id=int(user_message.id),
            assistant_message_id=int(assistant_message.id),
        )
        return True

    def search(self, *, user: User, current_session_id: int, query: str, limit: int = 5) -> list[dict[str, Any]]:
        if not self.get_settings(user).conversation_memory_enabled or self.embedding_service is None:
            logger.info("conversation_memory_search_skipped reason=disabled_or_unavailable user_id=%s", user.id)
            return []
        batch = self.embedding_service.embed_query(user, query)
        if batch.status != "completed" or len(batch.vectors) != 1 or not batch.profile_hash:
            logger.warning(
                "conversation_memory_search_skipped reason=embedding_status user_id=%s status=%s",
                user.id,
                batch.status,
            )
            return []
        distance = ConversationMemoryEntry.embedding.cosine_distance(batch.vectors[0])
        rows = list(
            self.db.scalars(
                select(ConversationMemoryEntry)
                .where(
                    ConversationMemoryEntry.user_id == user.id,
                    ConversationMemoryEntry.session_id != current_session_id,
                    ConversationMemoryEntry.embedding_profile_hash == batch.profile_hash,
                    ConversationMemoryEntry.embedding_dimension == batch.dimension,
                )
                .order_by(distance.asc(), ConversationMemoryEntry.created_at.desc())
                .limit(max(1, min(limit, 5)))
            )
        )
        return [
            {
                "source_type": "history",
                "title": "历史对话",
                "snippet": row.summary[:500],
                "session_id": str(row.session_id),
                "user_message_id": str(row.user_message_id),
                "assistant_message_id": str(row.assistant_message_id),
                "evidence_role": "conversation_memory",
            }
            for row in rows
        ]

    @staticmethod
    def _safe_summary(question: str, answer: str) -> str:
        text = f"学生：{' '.join(question.split())[:500]}\n助手：{' '.join(answer.split())[:900]}"
        text = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "[邮箱已隐藏]", text)
        text = re.sub(r"(?<!\d)1[3-9]\d{9}(?!\d)", "[手机号已隐藏]", text)
        text = re.sub(r"(?i)(api[_ -]?key|token|secret)\s*[:=]\s*\S+", r"\1=[已隐藏]", text)
        return text[:1600]

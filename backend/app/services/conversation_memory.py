from __future__ import annotations

import logging
import re
from typing import Any, Protocol

from pydantic import BaseModel
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from backend.app.models import ChatMessage, ChatSession, ConversationMemoryEntry, User, UserPrivacySetting, MemorySuppression, LearningMemoryFact
from backend.app.core.config import get_settings
from backend.app.services.memory_control import lock_memory_settings, MemoryControlService
from backend.app.services.embeddings import EmbeddingService


logger = logging.getLogger(__name__)


class PrivacySettingsResponse(BaseModel):
    conversation_memory_enabled: bool = True
    indexed_memory_count: int = 0
    episode_count: int = 0
    confirmed_fact_count: int = 0
    memory_revision: int = 0


class UpdatePrivacySettingsRequest(BaseModel):
    conversation_memory_enabled: bool


class ClearConversationMemoryResponse(BaseModel):
    deleted_count: int
    raw_chat_history_preserved: bool = True


class ConversationMemoryQueue(Protocol):
    def enqueue(self, *, user_id: int, session_id: int, user_message_id: int, assistant_message_id: int, expected_revision: int) -> None: ...
    def enqueue_backfill(self, *, user_id: int, expected_revision: int) -> None: ...


class RqConversationMemoryQueue:
    def __init__(self, *, redis_url: str, queue_name: str) -> None:
        self.redis_url = redis_url
        self.queue_name = queue_name

    def enqueue(self, *, user_id: int, session_id: int, user_message_id: int, assistant_message_id: int, expected_revision: int) -> None:
        from redis import Redis
        from rq import Queue

        from backend.app.workers.conversation_memory import index_conversation_memory

        Queue(self.queue_name, connection=Redis.from_url(self.redis_url)).enqueue(
            index_conversation_memory,
            user_id,
            session_id,
            user_message_id,
            assistant_message_id,
            expected_revision,
            job_id=f"conversation-memory-{assistant_message_id}-{expected_revision}",
            job_timeout=300,
            result_ttl=3600,
            failure_ttl=86400,
        )

    def enqueue_backfill(self, *, user_id: int, expected_revision: int) -> None:
        from redis import Redis
        from rq import Queue

        from backend.app.workers.conversation_memory import backfill_conversation_memory

        Queue(self.queue_name, connection=Redis.from_url(self.redis_url)).enqueue(
            backfill_conversation_memory,
            user_id,
            expected_revision,
            job_id=f"conversation-memory-backfill-{user_id}-{expected_revision}",
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
        setting = self.db.scalar(select(UserPrivacySetting).where(UserPrivacySetting.user_id == user.id)
                                 .execution_options(populate_existing=True))
        count = int(self.db.scalar(
            select(func.count(ConversationMemoryEntry.id)).where(ConversationMemoryEntry.user_id == user.id,
                                                                 ConversationMemoryEntry.embedding.is_not(None))
        ) or 0)
        return PrivacySettingsResponse(
            conversation_memory_enabled=True if setting is None else setting.conversation_memory_enabled,
            indexed_memory_count=count,
            episode_count=int(self.db.scalar(select(func.count(ConversationMemoryEntry.id))
                              .where(ConversationMemoryEntry.user_id == user.id)) or 0),
            confirmed_fact_count=int(self.db.scalar(select(func.count(LearningMemoryFact.id))
                                     .where(LearningMemoryFact.user_id == user.id)) or 0),
            memory_revision=setting.memory_revision if setting else 0,
        )

    def update_settings(self, user: User, enabled: bool) -> PrivacySettingsResponse:
        setting = lock_memory_settings(self.db, int(user.id))
        if setting.conversation_memory_enabled != enabled:
            setting.conversation_memory_enabled = enabled
            setting.memory_revision += 1
        self.db.commit()
        return self.get_settings(user)

    def clear(self, user: User) -> ClearConversationMemoryResponse:
        result = MemoryControlService(self.db).clear_all(int(user.id))
        return ClearConversationMemoryResponse(deleted_count=result.affected_count)

    def rebuild_indexes(self, user: User) -> None:
        state = self.get_settings(user)
        if not state.conversation_memory_enabled:
            from backend.app.services.memory_control import MemoryControlError
            raise MemoryControlError("请先恢复记忆使用，再重建派生索引。")
        if self.queue is None:
            from backend.app.services.memory_control import MemoryControlError
            raise MemoryControlError("记忆索引队列暂不可用。", 503)
        self.queue.enqueue_backfill(user_id=int(user.id), expected_revision=state.memory_revision)

    def index_pair(
        self,
        *,
        user: User,
        session: ChatSession,
        user_message: ChatMessage,
        assistant_message: ChatMessage,
        expected_revision: int | None = None,
    ) -> bool:
        state = self.get_settings(user)
        revision = state.memory_revision if expected_revision is None else expected_revision
        if not state.conversation_memory_enabled or state.memory_revision != revision or self.embedding_service is None:
            return False
        if (session.user_id != user.id or user_message.session_id != session.id
                or assistant_message.session_id != session.id or user_message.role != "user"
                or assistant_message.role != "assistant"):
            return False
        existing = self.db.scalar(select(ConversationMemoryEntry).where(
            ConversationMemoryEntry.user_id == user.id, ConversationMemoryEntry.assistant_message_id == assistant_message.id))
        summary = existing.summary if existing else self._safe_summary(user_message.content, assistant_message.content)
        source_revision = existing.revision if existing else None
        batch = self.embedding_service.embed_documents(user, [summary])
        if batch.status != "completed" or len(batch.vectors) != 1 or not batch.profile_hash:
            return False
        setting = lock_memory_settings(self.db, int(user.id))
        suppressed = self.db.scalar(select(MemorySuppression.id).where(
            MemorySuppression.user_id == user.id, MemorySuppression.assistant_message_id == assistant_message.id))
        source = self.db.scalar(select(ChatMessage).where(ChatMessage.id == assistant_message.id,
                               ChatMessage.session_id == session.id).execution_options(populate_existing=True))
        if (not setting.conversation_memory_enabled or setting.memory_revision != revision or suppressed is not None
                or source is None or (setting.memory_cleared_before is not None
                                      and source.created_at <= setting.memory_cleared_before)):
            self.db.rollback()
            return False
        existing = self.db.scalar(
            select(ConversationMemoryEntry).where(
                ConversationMemoryEntry.assistant_message_id == assistant_message.id
            ).execution_options(populate_existing=True)
        )
        if existing is not None and existing.revision != source_revision:
            self.db.rollback()
            return False
        if existing is not None:
            if self._matches_profile(existing, batch):
                self.db.rollback()
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
                    topic=self.redact(" ".join(user_message.content.split()))[:120] or "历史对话",
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
            and entry.embedding is not None
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
        state = self.get_settings(user)
        if not state.conversation_memory_enabled:
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
            expected_revision=state.memory_revision,
        )
        return True

    def search(self, *, user: User, current_session_id: int, query: str, limit: int = 5) -> list[dict[str, Any]]:
        state = self.get_settings(user)
        if not state.conversation_memory_enabled or self.embedding_service is None:
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
        # A CASE guard avoids distance evaluation on a different vector dimension
        # even if PostgreSQL reorders the WHERE predicates.
        distance = case((ConversationMemoryEntry.embedding_dimension == batch.dimension,
                         ConversationMemoryEntry.embedding.cosine_distance(batch.vectors[0])), else_=None)
        rows = list(
            self.db.scalars(
                select(ConversationMemoryEntry)
                .where(
                    ConversationMemoryEntry.user_id == user.id,
                    ConversationMemoryEntry.session_id != current_session_id,
                    ConversationMemoryEntry.embedding_profile_hash == batch.profile_hash,
                    ConversationMemoryEntry.embedding_dimension == batch.dimension,
                    ConversationMemoryEntry.embedding.is_not(None),
                    distance <= 1 - get_settings().conversation_memory_min_similarity,
                )
                .order_by(distance.asc(), ConversationMemoryEntry.created_at.desc())
                .limit(max(1, min(limit, 5)) * 4)
            )
        )
        # Recheck pause/delete decisions after potentially slow embedding work.
        current = self.get_settings(user)
        if not current.conversation_memory_enabled or current.memory_revision != state.memory_revision:
            return []
        unique = []
        seen = set()
        for row in rows:
            key = " ".join(row.summary.casefold().split())
            if key not in seen:
                unique.append(row)
                seen.add(key)
            if len(unique) >= max(1, min(limit, 5)):
                break
        return [
            {
                "source_type": "history",
                "title": "历史对话",
                "snippet": row.summary[:500],
                "session_id": str(row.session_id),
                "user_message_id": str(row.user_message_id),
                "assistant_message_id": str(row.assistant_message_id),
                "evidence_role": "conversation_memory",
                "memory_id": str(row.id),
                "topic": row.topic,
                "created_at": row.created_at.isoformat(),
            }
            for row in unique
        ]

    def confirmed_context(self, user: User) -> str:
        if not self.get_settings(user).conversation_memory_enabled:
            return ""
        rows = self.db.scalars(select(LearningMemoryFact).where(LearningMemoryFact.user_id == user.id)
                               .order_by(LearningMemoryFact.updated_at.desc(), LearningMemoryFact.id.desc()).limit(8))
        return "；".join(f"{row.category}：{row.content[:160]}" for row in rows)[:1200]

    @staticmethod
    def _safe_summary(question: str, answer: str) -> str:
        text = f"学生：{' '.join(question.split())[:500]}\n助手：{' '.join(answer.split())[:900]}"
        return ConversationMemoryService.redact(text)[:1600]

    @staticmethod
    def redact(text: str) -> str:
        text = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "[邮箱已隐藏]", text)
        text = re.sub(r"(?<!\d)1[3-9]\d{9}(?!\d)", "[手机号已隐藏]", text)
        text = re.sub(r"(?i)(api[_ -]?key|token|secret)\s*[:=]\s*\S+", r"\1=[已隐藏]", text)
        return text

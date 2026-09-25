from __future__ import annotations

from backend.app.core.config import get_settings
from backend.app.db.session import SessionLocal
from backend.app.models import ChatMessage, ChatSession, User, ConversationMemoryEntry
from backend.app.providers.openai_compatible import OpenAICompatibleChatProvider
from backend.app.services.conversation_memory import ConversationMemoryService
from backend.app.services.embeddings import EmbeddingService
from backend.app.services.model_settings import ModelSettingsService, SqlAlchemyModelSettingsRepository
from sqlalchemy import select


def index_conversation_memory(
    user_id: int,
    session_id: int,
    user_message_id: int,
    assistant_message_id: int,
    expected_revision: int = 0,
) -> None:
    with SessionLocal() as db:
        user = db.get(User, user_id)
        session = db.get(ChatSession, session_id)
        user_message = db.get(ChatMessage, user_message_id)
        assistant_message = db.get(ChatMessage, assistant_message_id)
        if user is None or session is None or user_message is None or assistant_message is None:
            return
        model_service = ModelSettingsService(
            repository=SqlAlchemyModelSettingsRepository(db),
            settings=get_settings(),
            provider=OpenAICompatibleChatProvider(),
        )
        ConversationMemoryService(db, EmbeddingService(model_service)).index_pair(
            user=user,
            session=session,
            user_message=user_message,
            assistant_message=assistant_message,
            expected_revision=expected_revision,
        )


def backfill_conversation_memory(user_id: int, expected_revision: int = 0) -> None:
    """Explicitly rebuild retained summaries; never reconstruct deleted memories from raw chat."""
    with SessionLocal() as db:
        user = db.get(User, user_id)
        if user is None:
            return
        model_service = ModelSettingsService(
            repository=SqlAlchemyModelSettingsRepository(db),
            settings=get_settings(),
            provider=OpenAICompatibleChatProvider(),
        )
        service = ConversationMemoryService(db, EmbeddingService(model_service))
        revision = expected_revision
        ids = list(db.execute(select(ConversationMemoryEntry.session_id, ConversationMemoryEntry.user_message_id,
                                     ConversationMemoryEntry.assistant_message_id)
                              .where(ConversationMemoryEntry.user_id == user_id)).all())
        for session_id, user_message_id, assistant_message_id in ids:
            if service.get_settings(user).memory_revision != revision:
                return
            session = db.get(ChatSession, session_id)
            question = db.get(ChatMessage, user_message_id)
            answer = db.get(ChatMessage, assistant_message_id)
            if session is not None and question is not None and answer is not None:
                service.index_pair(user=user, session=session, user_message=question,
                                   assistant_message=answer, expected_revision=revision)

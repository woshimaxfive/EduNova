from __future__ import annotations

from backend.app.core.config import get_settings
from backend.app.db.session import SessionLocal
from backend.app.models import ChatMessage, ChatSession, User
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
        )


def backfill_conversation_memory(user_id: int) -> None:
    """Idempotently index completed user/assistant pairs without copying raw messages."""
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
        sessions = list(db.scalars(select(ChatSession).where(ChatSession.user_id == user_id)))
        for session in sessions:
            messages = list(db.scalars(
                select(ChatMessage)
                .where(ChatMessage.session_id == session.id)
                .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
            ))
            previous_user: ChatMessage | None = None
            for message in messages:
                if message.role == "user":
                    previous_user = message
                elif message.role == "assistant" and previous_user is not None:
                    service.index_pair(
                        user=user,
                        session=session,
                        user_message=previous_user,
                        assistant_message=message,
                    )
                    previous_user = None

"""User-confirmed learning preferences and content-free deletion markers."""
from sqlalchemy import BigInteger, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base
from backend.app.models.mixins import IdMixin, TimestampMixin, CreatedAtMixin


class LearningMemoryFact(IdMixin, TimestampMixin, Base):
    __tablename__ = "learning_memory_facts"
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")


class MemorySuppression(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "memory_suppressions"
    __table_args__ = (UniqueConstraint("user_id", "assistant_message_id", name="uq_memory_suppression_source"),)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    assistant_message_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("chat_messages.id", ondelete="CASCADE"))

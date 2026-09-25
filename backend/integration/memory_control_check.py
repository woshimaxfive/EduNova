"""Real PostgreSQL memory isolation, ranking, correction and concurrent deletion checks."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from types import SimpleNamespace
from uuid import uuid4
from importlib import import_module
from alembic.migration import MigrationContext
from alembic.operations import Operations

from sqlalchemy import delete, select, func, text

from backend.app.db.session import SessionLocal, engine
from backend.app.models import User, ChatSession, ChatMessage, ConversationMemoryEntry, LearningMemoryFact
from backend.app.schemas.memory import ConfirmedMemoryRequest, MemoryCorrectionRequest
from backend.app.services.conversation_memory import ConversationMemoryService
from backend.app.services.memory_control import MemoryControlService, MemoryControlError
from backend.app.services.embeddings import EmbeddingBatch


def batch(vector=None):
    return EmbeddingBatch(vectors=[vector or [1.0, 0.0, 0.0]], source="synthetic", model="memory-test",
                          dimension=3, status="completed", profile_hash="memory-test-v1")


def main():
    migration = import_module("backend.migrations.versions.20260925_0039_controlled_memory")
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            schema = "memory_migration_" + uuid4().hex
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            connection.execute(text(f'SET LOCAL search_path TO "{schema}", public'))
            connection.execute(text("SET LOCAL lock_timeout = '5s'"))
            connection.execute(text("CREATE TABLE users (id bigint PRIMARY KEY)"))
            connection.execute(text("CREATE TABLE chat_messages (id bigint PRIMARY KEY)"))
            connection.execute(text("CREATE TABLE user_privacy_settings (id bigint PRIMARY KEY)"))
            connection.execute(text("CREATE TABLE conversation_memory_entries (id bigint PRIMARY KEY, summary text, embedding vector NOT NULL)"))
            connection.execute(text("INSERT INTO conversation_memory_entries VALUES (1, '保留旧摘要', '[1,0,0]')"))
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
                assert connection.scalar(text("SELECT summary FROM conversation_memory_entries")) == "保留旧摘要"
                migration.downgrade()
                migration.upgrade()
                connection.execute(text("INSERT INTO user_privacy_settings (id, memory_revision) VALUES (1, 1)"))
                try:
                    migration.downgrade()
                    raise AssertionError("privacy barrier downgrade allowed")
                except RuntimeError as exc:
                    assert "privacy decisions" in str(exc)
        finally:
            transaction.rollback()
    ids = []
    with SessionLocal() as db:
        try:
            users = [User(account=f"memory_{uuid4().hex[:12]}", hashed_password="synthetic-only",
                          display_name="memory fixture", role="student", starter_mode="blank") for _ in range(2)]
            db.add_all(users)
            db.commit()
            ids = [u.id for u in users]
            owner, other = users
            session = ChatSession(user_id=owner.id, scope="home", title="历史学习", mode="chat")
            db.add(session)
            db.commit()

            def pair(label):
                question = ChatMessage(user_id=owner.id, session_id=session.id, role="user", content=f"我在学习{label}")
                answer = ChatMessage(user_id=owner.id, session_id=session.id, role="assistant", content=f"关于{label}的解释")
                db.add_all([question, answer])
                db.commit()
                return question, answer

            embedding = SimpleNamespace(embed_documents=lambda *_: batch(), embed_query=lambda *_: batch())
            service = ConversationMemoryService(db, embedding)
            control = MemoryControlService(db)
            question, answer = pair("队列")
            args = dict(user=owner, session=session, user_message=question, assistant_message=answer)
            assert service.index_pair(**args)
            entry = db.scalar(select(ConversationMemoryEntry).where(ConversationMemoryEntry.user_id == owner.id))
            assert entry is not None
            assert service.search(user=owner, current_session_id=session.id + 100, query="队列")
            assert service.search(user=owner, current_session_id=session.id, query="队列") == []
            assert service.search(user=other, current_session_id=session.id + 100, query="队列") == []
            # A different profile/dimension cannot break distance evaluation.
            other_question, other_answer = pair("其他维度")
            other_entry = ConversationMemoryEntry(user_id=owner.id, session_id=session.id,
                user_message_id=other_question.id, assistant_message_id=other_answer.id, summary="其他维度",
                embedding=[1, 0], embedding_provider="synthetic", embedding_model="other", embedding_dimension=2,
                embedding_profile_hash="other-profile")
            db.add(other_entry)
            db.commit()
            assert len(service.search(user=owner, current_session_id=999, query="队列")) == 1
            db.delete(other_entry)
            db.commit()
            low = ConversationMemoryService(db, SimpleNamespace(embed_query=lambda *_: batch([0, 1, 0])))
            assert low.search(user=owner, current_session_id=session.id + 100, query="无关") == []

            fact = control.create_fact(owner.id, ConfirmedMemoryRequest(category="preference", content="先给例子", confirmed=True))
            assert control.create_fact(owner.id, ConfirmedMemoryRequest(category="preference", content="先给例子", confirmed=True)).id == fact.id
            assert "先给例子" in service.confirmed_context(owner)
            try:
                control.correct(other.id, "fact", int(fact.id), MemoryCorrectionRequest(content="越权", revision=1, confirmed=True))
                raise AssertionError("cross-user update accepted")
            except MemoryControlError as exc:
                assert exc.status_code == 404
                db.rollback()
            assert control.list_items(other.id, "fact").total == 0

            corrected = control.correct(owner.id, "episode", entry.id,
                                        MemoryCorrectionRequest(content="已纠正：学习的是双端队列", revision=1, confirmed=True))
            assert corrected.revision == 2 and not corrected.indexed
            assert service.index_pair(**args)
            db.refresh(entry)
            assert entry.summary == corrected.content
            try:
                control.remove(owner.id, "episode", entry.id, 1)
                raise AssertionError("stale delete accepted")
            except MemoryControlError as exc:
                assert exc.status_code == 409
                db.rollback()
            service.update_settings(owner, False)
            assert service.confirmed_context(owner) == ""
            assert service.search(user=owner, current_session_id=999, query="队列") == []
            assert not service.index_pair(**args)
            assert control.list_items(owner.id, "episode").total == 1
            service.update_settings(owner, True)
            assert control.clear_indexes(owner.id).affected_count == 1
            assert service.search(user=owner, current_session_id=999, query="队列") == []
            assert service.index_pair(**args)
            exported = control.export(owner.id).model_dump(mode="json")
            assert len(exported["items"]) == 2 and not exported["raw_chat_history_included"]
            assert "embedding" not in str(exported) and "hashed_password" not in str(exported)

            # Block vector calculation outside the lock; mutate privacy while it is in flight.
            for mutation in ("pause", "delete", "clear"):
                question, answer = pair(mutation)
                assert service.index_pair(user=owner, session=session, user_message=question, assistant_message=answer)
                candidate = db.scalar(select(ConversationMemoryEntry).where(ConversationMemoryEntry.assistant_message_id == answer.id))
                started, release = Event(), Event()
                user_id, session_id, question_id, answer_id = owner.id, session.id, question.id, answer.id
                def worker():
                    with SessionLocal() as worker_db:
                        def embed(*_):
                            started.set()
                            assert release.wait(20)
                            return batch()
                        worker_service = ConversationMemoryService(worker_db, SimpleNamespace(embed_documents=embed))
                        return worker_service.index_pair(user=worker_db.get(User, user_id), session=worker_db.get(ChatSession, session_id),
                            user_message=worker_db.get(ChatMessage, question_id), assistant_message=worker_db.get(ChatMessage, answer_id))
                with ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(worker)
                    assert started.wait(20)
                    if mutation == "pause":
                        service.update_settings(owner, False)
                    elif mutation == "delete":
                        control.remove(owner.id, "episode", candidate.id, candidate.revision)
                    else:
                        control.clear_all(owner.id)
                    release.set()
                    assert future.result(timeout=20) is False
                if mutation == "pause":
                    service.update_settings(owner, True)
                else:
                    assert not service.index_pair(user=owner, session=session, user_message=question, assistant_message=answer)
            assert control.list_items(owner.id, "episode").total == 0
            assert control.list_items(owner.id, "fact").total == 0
            assert db.scalar(select(func.count(ChatMessage.id)).where(ChatMessage.user_id == owner.id)) == 10
            # A genuinely new pair after clear can be remembered.
            question, answer = pair("新主题")
            assert service.index_pair(user=owner, session=session, user_message=question, assistant_message=answer)
            assert control.list_items(owner.id, "episode").total == 1
            assert db.scalar(select(func.count(LearningMemoryFact.id)).where(LearningMemoryFact.user_id == other.id)) == 0
        finally:
            db.rollback()
            if ids:
                db.execute(delete(User).where(User.id.in_(ids)))
                db.commit()
    print("Memory PostgreSQL ownership, threshold, correction, pause, deletion races, export and clear barriers passed")


if __name__ == "__main__":
    main()

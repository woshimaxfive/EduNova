"""Real PostgreSQL selection races with synthetic data and a blocked fake model.

Run in the backend container with PYTHONPATH=/app. No provider calls.
"""

import json
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from types import SimpleNamespace
from uuid import uuid4

from sqlalchemy import delete, func, select

from backend.app.core.config import get_settings
from backend.app.db.session import SessionLocal
from backend.app.models import (
    User,
    ChatSession,
    ChatMessage,
    ConversationMemoryEntry,
    UserPrivacySetting,
    MemorySuppression,
)
from backend.app.schemas.memory import MemoryCorrectionRequest
from backend.app.services.conversation_memory import ConversationMemoryService
from backend.app.services.embeddings import EmbeddingBatch
from backend.app.services.memory_control import MemoryControlService


def main():
    config = get_settings()
    previous = config.conversation_memory_semantic_selection_enabled
    config.conversation_memory_semantic_selection_enabled = True
    ids = []
    result = {"checks": [], "provider_calls": 0}
    embedding = SimpleNamespace(
        embed_query=lambda *_: EmbeddingBatch(
            vectors=[[1, 0, 0]],
            source="synthetic",
            model="selection-test",
            dimension=3,
            profile_hash="selection-test",
            status="completed",
        )
    )
    try:
        with SessionLocal() as db:
            user = User(
                account="msrace_" + uuid4().hex[:12],
                hashed_password="synthetic-only",
                display_name="脱敏并发验证",
                role="student",
                starter_mode="blank",
            )
            other = User(
                account="msrace_" + uuid4().hex[:12],
                hashed_password="synthetic-only",
                display_name="隔离验证",
                role="student",
                starter_mode="blank",
            )
            db.add_all([user, other])
            db.commit()
            ids = [user.id, other.id]
            history = ChatSession(
                user_id=user.id, scope="home", mode="chat", title="脱敏历史"
            )
            fresh = ChatSession(
                user_id=user.id, scope="home", mode="chat", title="脱敏当前"
            )
            db.add_all([history, fresh])
            db.commit()
            session_id, user_id = fresh.id, user.id

            def seed():
                um = ChatMessage(
                    user_id=user.id,
                    session_id=history.id,
                    role="user",
                    content="练习甲容量13",
                )
                am = ChatMessage(
                    user_id=user.id,
                    session_id=history.id,
                    role="assistant",
                    content="最多12",
                )
                db.add_all([um, am])
                db.commit()
                entry = ConversationMemoryEntry(
                    user_id=user.id,
                    session_id=history.id,
                    user_message_id=um.id,
                    assistant_message_id=am.id,
                    summary="练习甲容量13，最多12",
                    topic="循环队列",
                    embedding=[0.6, 0.8, 0],
                    embedding_provider="synthetic",
                    embedding_model="selection-test",
                    embedding_dimension=3,
                    embedding_profile_hash="selection-test",
                )
                db.add(entry)
                db.commit()
                return entry.id

            entry_id = seed()
            memory = ConversationMemoryService(db, embedding)
            assert (
                memory.search(user=user, current_session_id=session_id, query="甲")
                == []
            )
            result["checks"].append("baseline_threshold_excludes_low_similarity")
            calls = []

            def select_first(_user, messages, _profile):
                calls.append(messages)
                candidates = json.loads(messages[1]["content"])["candidates"]
                return json.dumps(
                    {"state": "matched", "selected_ids": [candidates[0]["id"]]}
                )

            model = SimpleNamespace(chat_completion_for_task=select_first)
            memory = ConversationMemoryService(db, embedding, selection_model=model)
            assert [
                r["memory_id"]
                for r in memory.search(
                    user=user, current_session_id=session_id, query="甲"
                )
            ] == [str(entry_id)]
            assert (
                memory.search(user=other, current_session_id=session_id, query="甲")
                == []
            )
            assert (
                memory.search(user=user, current_session_id=history.id, query="甲")
                == []
            )
            assert len(calls) == 1
            result["checks"].extend(
                [
                    "expanded_candidate_selected",
                    "ownership_isolated",
                    "current_session_excluded",
                ]
            )
            for action in ("pause", "delete", "correct", "clear"):
                if action != "pause":
                    entry_id = seed()
                entered, release = Event(), Event()

                def block(_user, messages, _profile):
                    entered.set()
                    assert release.wait(15), "controller did not release model"
                    candidates = json.loads(messages[1]["content"])["candidates"]
                    return json.dumps(
                        {"state": "matched", "selected_ids": [candidates[0]["id"]]}
                    )

                def retrieval():
                    with SessionLocal() as worker_db:
                        worker_user = worker_db.get(User, user_id)
                        service = ConversationMemoryService(
                            worker_db,
                            embedding,
                            selection_model=SimpleNamespace(
                                chat_completion_for_task=block
                            ),
                        )
                        return service.search(
                            user=worker_user, current_session_id=session_id, query="甲"
                        )

                with ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(retrieval)
                    try:
                        assert entered.wait(15), "selection never entered"
                        control = MemoryControlService(db)
                        if action == "pause":
                            memory.update_settings(user, False)
                        elif action == "delete":
                            entry = db.get(ConversationMemoryEntry, entry_id)
                            control.remove(user.id, "episode", entry.id, entry.revision)
                        elif action == "correct":
                            entry = db.get(ConversationMemoryEntry, entry_id)
                            control.correct(
                                user.id,
                                "episode",
                                entry.id,
                                MemoryCorrectionRequest(
                                    content="练习甲容量19，最多18",
                                    revision=entry.revision,
                                    confirmed=True,
                                ),
                            )
                        else:
                            control.clear_all(user.id)
                    finally:
                        release.set()
                    assert future.result(timeout=15) == [], action
                result["checks"].append(action + "_during_selection_discards_result")
                if action == "pause":
                    memory.update_settings(user, True)
    finally:
        config.conversation_memory_semantic_selection_enabled = previous
        with SessionLocal() as cleanup:
            cleanup.execute(
                delete(User).where(User.id.in_(ids), User.account.like("msrace_%"))
            )
            cleanup.commit()
        with SessionLocal() as verify:
            result["residuals"] = {
                cls.__name__: verify.scalar(
                    select(func.count())
                    .select_from(cls)
                    .where((cls.id if cls is User else cls.user_id).in_(ids))
                )
                for cls in (
                    User,
                    ChatSession,
                    ChatMessage,
                    ConversationMemoryEntry,
                    UserPrivacySetting,
                    MemorySuppression,
                )
            }
        print(json.dumps(result, ensure_ascii=False))
        assert not any(result["residuals"].values())


if __name__ == "__main__":
    main()

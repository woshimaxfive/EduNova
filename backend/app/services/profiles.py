from __future__ import annotations

import re
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Protocol

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.models import ChatMessage, ChatSession, ProfileEvent, StudentProfile, User
from backend.app.schemas.profiles import (
    ProfileChatResponse,
    ProfileEventResponse,
    StudentProfileResponse,
    empty_profile_json,
    event_to_api,
    normalize_profile_json,
    profile_to_api,
)
from backend.app.services.model_settings import ModelSettingsService


PROFILE_SIGNAL_WORDS = ("不懂", "不会", "困惑", "卡住", "薄弱", "最担心", "为什么", "怎么复习", "难")


class ProfileRepository(Protocol):
    def get_profile(self, user_id: int) -> StudentProfile | None:
        ...

    def add_profile(self, profile: StudentProfile) -> None:
        ...

    def add_event(self, event: ProfileEvent) -> None:
        ...

    def list_events(self, user_id: int, limit: int) -> list[ProfileEvent]:
        ...

    def count_events_for_profile(self, profile_id: int | None) -> int:
        ...

    def flush(self) -> None:
        ...

    def commit(self) -> None:
        ...

    def rollback(self) -> None:
        ...


class SqlAlchemyProfileRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_profile(self, user_id: int) -> StudentProfile | None:
        return self.db.scalar(select(StudentProfile).where(StudentProfile.user_id == user_id))

    def add_profile(self, profile: StudentProfile) -> None:
        self.db.add(profile)
        self.db.flush()

    def add_event(self, event: ProfileEvent) -> None:
        self.db.add(event)

    def list_events(self, user_id: int, limit: int) -> list[ProfileEvent]:
        return list(
            self.db.scalars(
                select(ProfileEvent)
                .where(ProfileEvent.user_id == user_id)
                .order_by(ProfileEvent.created_at.desc(), ProfileEvent.id.desc())
                .limit(limit)
            )
        )

    def count_events_for_profile(self, profile_id: int | None) -> int:
        if profile_id is None:
            return 0
        return int(
            self.db.scalar(
                select(func.count()).select_from(ProfileEvent).where(ProfileEvent.profile_id == profile_id)
            )
            or 0
        )

    def flush(self) -> None:
        self.db.flush()

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()


class ProfileService:
    def __init__(
        self,
        repository: ProfileRepository,
        now: datetime | None = None,
        *,
        model_service: ModelSettingsService | None = None,
        trace_recorder: Any | None = None,
    ) -> None:
        self.repository = repository
        self.now = now
        self.model_service = model_service
        self.trace_recorder = trace_recorder

    def get_my_profile(self, user: User) -> StudentProfileResponse:
        profile = self.repository.get_profile(user.id)
        events = self.repository.list_events(user.id, 100)
        return profile_to_api(
            profile,
            version=self.repository.count_events_for_profile(profile.id if profile is not None else None),
            next_question=self._next_question(profile),
            evidence_summary=self._evidence_summary(events),
        )

    def update_by_chat(self, user: User, message: str) -> ProfileChatResponse:
        from backend.app.agents.profile import ProfileGraphRunner

        return ProfileGraphRunner(self).update_by_chat(user, message)

    def ingest_learning_signal(
        self,
        *,
        user: User,
        source_type: str,
        source_ref_type: str,
        source_ref_id: int,
        suggested_updates: dict[str, Any],
        course_id: int | None = None,
        parent_trace_id: str | None = None,
    ) -> ProfileEvent | None:
        from backend.app.agents.profile import ProfileGraphRunner

        return ProfileGraphRunner(self).ingest_learning_signal(
            user=user,
            source_type=source_type,
            source_ref_type=source_ref_type,
            source_ref_id=source_ref_id,
            suggested_updates=suggested_updates,
            course_id=course_id,
            parent_trace_id=parent_trace_id,
        )

    def ingest_course_question_signal(
        self,
        *,
        user: User,
        session: ChatSession,
        user_message: ChatMessage,
        message_text: str,
        citation_json: list[dict[str, Any]],
        trace_id: str | None,
    ) -> ProfileEvent | None:
        if session.scope != "course" or not self._has_profile_signal(message_text):
            return None
        citations = self._safe_citations(citation_json)
        title = next(
            (
                str(item.get("section_title") or item.get("source_title") or "").strip()
                for item in citations
                if item.get("section_title") or item.get("source_title")
            ),
            "",
        )
        if not title:
            return None
        return self.ingest_learning_signal(
            user=user,
            source_type="course_question",
            source_ref_type="chat_message",
            source_ref_id=user_message.id,
            suggested_updates={"weak_points": [title]},
            course_id=session.course_id,
            parent_trace_id=trace_id,
        )

    def list_events(self, user: User, limit: int = 20) -> list[ProfileEventResponse]:
        return [event_to_api(event) for event in self.repository.list_events(user.id, limit=limit)]

    def record_course_question_event(
        self,
        *,
        user: User,
        session: ChatSession,
        user_message: ChatMessage,
        assistant_message: ChatMessage,
        message_text: str,
        citation_json: list[dict[str, Any]],
        trace_id: str | None,
    ) -> ProfileEvent | None:
        if session.scope != "course" or not self._has_profile_signal(message_text):
            return None

        profile = self.repository.get_profile(user.id)
        event = ProfileEvent(
            user_id=user.id,
            profile_id=profile.id if profile is not None else None,
            dimension="weak_points",
            change_summary="课程问答提示可能存在薄弱点",
            evidence_json={
                "source_type": "course_question",
                "course_id": session.course_id,
                "session_id": session.id,
                "user_message_id": user_message.id,
                "assistant_message_id": assistant_message.id,
                "trace_id": trace_id,
                "citations": self._safe_citations(citation_json),
            },
            agent_trace_id=trace_id,
            source_type="course_question",
            source_ref_type="chat_message",
            source_ref_id=user_message.id,
            status="candidate",
            confidence_score=Decimal("0.78"),
            proposal_json={"weak_points": [self._safe_citations(citation_json)[0].get("section_title")]} if self._safe_citations(citation_json) and self._safe_citations(citation_json)[0].get("section_title") else {},
        )
        self.repository.add_event(event)
        return event

    def _extract_profile_updates(self, message_text: str) -> dict[str, Any]:
        updates: dict[str, Any] = {}
        major_background = self._find_first(
            message_text,
            [
                r"我是([^，。；,;]*专业[^，。；,;]*学生)",
                r"([^，。；,;]*专业[^，。；,;]*学生)",
            ],
        )
        if major_background:
            updates["major_background"] = major_background

        knowledge_foundation = self._find_first(
            message_text,
            [
                r"([^，。；,;]*刚入门)",
                r"([^，。；,;]*基础较稳)",
                r"([^，。；,;]*基础一般)",
            ],
        )
        if knowledge_foundation and "数学基础一般" not in knowledge_foundation:
            updates["knowledge_foundation"] = knowledge_foundation

        learning_goal = self._find_first(
            message_text,
            [
                r"(?:想|希望|目标是)([^，。；,;]*掌握[^，。；,;]*)",
                r"(?:想|希望|目标是)([^，。；,;]*复习[^，。；,;]*)",
            ],
        )
        if learning_goal:
            updates["learning_goal"] = learning_goal

        if "案例和图解" in message_text:
            updates["learning_preference"] = "案例和图解"
            updates["cognitive_style"] = "案例驱动"
        elif "图解" in message_text:
            updates["learning_preference"] = "图解"
        elif "代码" in message_text:
            updates["learning_preference"] = "代码"

        learning_pace = self._find_first(message_text, [r"(每天\s*\d+\s*分钟)"])
        if learning_pace:
            updates["learning_pace"] = re.sub(r"\s+", " ", learning_pace)

        weak_points = self._extract_weak_points(message_text)
        if weak_points:
            updates["weak_points"] = weak_points

        if "提升" in message_text and "能力" in message_text:
            updates["motivation_interest"] = self._clip_sentence(message_text)

        if not updates and len(message_text) <= 80:
            updates["learning_goal"] = message_text.rstrip("。")

        return updates

    @staticmethod
    def _find_first(message_text: str, patterns: list[str]) -> str:
        for pattern in patterns:
            match = re.search(pattern, message_text)
            if match:
                return match.group(1).strip()
        return ""

    @staticmethod
    def _extract_weak_points(message_text: str) -> list[str]:
        weak_points: list[str] = []
        if "数学基础一般" in message_text:
            weak_points.append("数学基础一般")
        worry = re.search(r"(?:最担心|担心)([^，。；,;]*)", message_text)
        if worry:
            weak_point = worry.group(1).strip()
            if weak_point:
                weak_points.append(weak_point)
        if "链式法则" in message_text and "链式法则" not in weak_points:
            weak_points.append("链式法则")
        return weak_points

    @staticmethod
    def _merge_profile_json(current: dict[str, Any] | None, updates: dict[str, Any]) -> dict[str, Any]:
        merged = normalize_profile_json(current)
        for key, value in updates.items():
            if key == "weak_points":
                current_points = list(merged["weak_points"])
                for item in value:
                    if item not in current_points:
                        current_points.append(item)
                merged[key] = current_points
            else:
                merged[key] = value
        return merged

    @staticmethod
    def _changed_labels(updates: dict[str, Any]) -> list[str]:
        labels = {
            "major_background": "专业背景",
            "knowledge_foundation": "知识基础",
            "learning_goal": "学习目标",
            "cognitive_style": "认知风格",
            "learning_preference": "学习偏好",
            "weak_points": "薄弱点",
            "learning_pace": "学习节奏",
            "motivation_interest": "学习动机",
        }
        return [labels[key] for key in updates if key in labels]

    @staticmethod
    def _change_summary(changed_labels: list[str]) -> str:
        if not changed_labels:
            return "更新学习画像"
        return f"更新学习画像：{'、'.join(changed_labels)}"

    @staticmethod
    def _next_confidence(current: Decimal, changed_labels: list[str]) -> Decimal:
        base = Decimal(current or 0)
        if base <= 0:
            base = Decimal("60")
        increment = Decimal(len(changed_labels) * 4)
        return min(base + increment, Decimal("94"))

    @staticmethod
    def _has_profile_signal(message_text: str) -> bool:
        return any(word in message_text for word in PROFILE_SIGNAL_WORDS)

    @staticmethod
    def _safe_citations(citation_json: list[dict[str, Any]]) -> list[dict[str, Any]]:
        safe_items = []
        for citation in citation_json[:5]:
            safe_items.append(
                {
                    "chunk_id": citation.get("chunk_id"),
                    "knowledge_point_id": citation.get("knowledge_point_id"),
                    "source_title": citation.get("source_title"),
                    "section_title": citation.get("section_title"),
                }
            )
        return safe_items

    @staticmethod
    def _clip_sentence(message_text: str) -> str:
        return message_text.strip().rstrip("。")[:80]

    def _next_question(self, profile: StudentProfile | None) -> str:
        profile_json = normalize_profile_json(profile.profile_json if profile is not None else None)
        if not profile_json["learning_goal"]:
            return "这门课你最想先解决什么问题？"
        if not profile_json["weak_points"]:
            return "这门课你最担心哪一章？"
        if not profile_json["learning_preference"]:
            return "你更喜欢哪种学习方式？"
        return "最近一次学习里，哪里最卡住？"

    def _current_time(self) -> datetime:
        current = self.now or datetime.now(UTC)
        return current if current.tzinfo is not None else current.replace(tzinfo=UTC)

    @staticmethod
    def _empty_profile() -> dict[str, Any]:
        return empty_profile_json()

    @staticmethod
    def _evidence_summary(events: list[ProfileEvent]) -> dict[str, int | str | None]:
        return {
            "candidate_count": sum(1 for event in events if getattr(event, "status", None) == "candidate"),
            "applied_count": sum(1 for event in events if getattr(event, "status", None) == "applied"),
            "last_trace_id": next((event.agent_trace_id for event in events if getattr(event, "agent_trace_id", None)), None),
        }

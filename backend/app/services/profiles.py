from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Protocol

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.models import ChatMessage, ChatSession, CourseEnrollment, ProfileEvent, StudentProfile, User
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


PROFILE_QUESTION_ORDER = (
    "learning_preference",
    "learning_pace",
    "major_background",
    "cognitive_style",
    "motivation_interest",
    "learning_goal",
    "knowledge_foundation",
    "weak_points",
)

PROFILE_QUESTIONS = {
    "major_background": "你现在在学什么，或者有过哪些相关经历？",
    "knowledge_foundation": "关于现在想学的内容，你已经会些什么？",
    "learning_goal": "接下来你最想学会、完成或解决什么？",
    "cognitive_style": "遇到新知识时，你通常怎样更容易弄懂？",
    "learning_preference": "你更喜欢通过什么形式学习和练习？",
    "weak_points": "目前哪些内容最容易让你卡住或出错？",
    "learning_pace": "你通常能投入多少时间，喜欢怎样安排学习？",
    "motivation_interest": "你为什么想学这些内容，对什么方向感兴趣？",
}


class ProfileRepository(Protocol):
    def get_profile(self, user_id: int) -> StudentProfile | None:
        ...

    def add_profile(self, profile: StudentProfile) -> None:
        ...

    def add_event(self, event: ProfileEvent) -> None:
        ...

    def get_course_enrollment(self, user_id: int, course_id: int) -> CourseEnrollment | None:
        ...

    def list_events(self, user_id: int, limit: int) -> list[ProfileEvent]:
        ...

    def count_events_for_profile(self, profile_id: int | None) -> int:
        ...

    def count_applied_events_for_profile(self, profile_id: int | None) -> int:
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

    def get_course_enrollment(self, user_id: int, course_id: int) -> CourseEnrollment | None:
        return self.db.scalar(select(CourseEnrollment).where(
            CourseEnrollment.user_id == user_id,
            CourseEnrollment.course_id == course_id,
        ))

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

    def count_applied_events_for_profile(self, profile_id: int | None) -> int:
        if profile_id is None:
            return 0
        return int(
            self.db.scalar(
                select(func.count()).select_from(ProfileEvent).where(
                    ProfileEvent.profile_id == profile_id,
                    ProfileEvent.status == "applied",
                )
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
        next_question_dimension, next_question = self._next_question_target(profile)
        return profile_to_api(
            profile,
            version=self.repository.count_events_for_profile(profile.id if profile is not None else None),
            next_question=next_question,
            next_question_dimension=next_question_dimension,
            evidence_summary=self._evidence_summary(events),
            applied_version=self._count_applied_events(profile.id if profile is not None else None, events),
            dimension_evidence_summary=self._dimension_evidence_summary(profile, events),
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
        suggested_confidence: dict[str, float] | None = None,
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
            suggested_confidence=suggested_confidence or {},
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
        suggested_updates: dict[str, Any] | None = None,
        suggested_confidence: dict[str, float] | None = None,
    ) -> ProfileEvent | None:
        if session.scope != "course" or not suggested_updates:
            return None
        citations = self._safe_citations(citation_json)
        if not citations:
            return None
        return self.ingest_learning_signal(
            user=user,
            source_type="course_question",
            source_ref_type="chat_message",
            source_ref_id=user_message.id,
            suggested_updates=suggested_updates,
            suggested_confidence=suggested_confidence or {},
            course_id=session.course_id,
            parent_trace_id=trace_id,
        )

    def list_events(self, user: User, limit: int = 20) -> list[ProfileEventResponse]:
        return [event_to_api(event) for event in self.repository.list_events(user.id, limit=limit)]

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
            "major_background": "学习背景",
            "knowledge_foundation": "已有基础",
            "learning_goal": "学习目标",
            "cognitive_style": "理解习惯",
            "learning_preference": "学习方式",
            "weak_points": "学习难点",
            "learning_pace": "学习节奏",
            "motivation_interest": "学习动力",
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

    def _next_question_target(
        self,
        profile: StudentProfile | None,
        preferred_dimensions: list[str] | None = None,
    ) -> tuple[str, str]:
        profile_json = normalize_profile_json(profile.profile_json if profile is not None else None)
        confidence = dict(getattr(profile, "dimension_confidence_json", None) or {}) if profile is not None else {}
        preferred = [key for key in (preferred_dimensions or []) if key in PROFILE_QUESTIONS]
        for key in preferred:
            if not profile_json[key]:
                return key, PROFILE_QUESTIONS[key]
        missing = [key for key in PROFILE_QUESTION_ORDER if not profile_json[key]]
        if missing:
            key = missing[0]
            return key, PROFILE_QUESTIONS[key]
        lowest = min(PROFILE_QUESTION_ORDER, key=lambda key: float(confidence.get(key, 0)))
        return lowest, PROFILE_QUESTIONS[lowest]

    def _next_question(self, profile: StudentProfile | None, preferred_dimensions: list[str] | None = None) -> str:
        return self._next_question_target(profile, preferred_dimensions)[1]

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

    def _count_applied_events(self, profile_id: int | None, events: list[ProfileEvent] | None = None) -> int:
        counter = getattr(self.repository, "count_applied_events_for_profile", None)
        if callable(counter):
            return int(counter(profile_id))
        if profile_id is None:
            return 0
        source_events = events or []
        return sum(1 for event in source_events if getattr(event, "status", None) == "applied")

    @classmethod
    def _dimension_evidence_summary(
        cls,
        profile: StudentProfile | None,
        events: list[ProfileEvent],
    ) -> dict[str, dict[str, Any]]:
        if profile is None:
            return {}
        profile_json = normalize_profile_json(profile.profile_json)
        confidence = dict(getattr(profile, "dimension_confidence_json", None) or {})
        summary: dict[str, dict[str, Any]] = {}
        for dimension in PROFILE_QUESTION_ORDER:
            value = profile_json.get(dimension)
            if not value:
                continue
            normalized = cls._normalized_profile_value(value)
            supporting = [
                event
                for event in events
                if getattr(event, "status", None) == "applied"
                and cls._normalized_profile_value((getattr(event, "proposal_json", None) or {}).get(dimension)) == normalized
            ]
            source_refs = {
                (
                    str(getattr(event, "source_type", None) or "legacy"),
                    str(getattr(event, "source_ref_type", None) or ""),
                    str(getattr(event, "source_ref_id", None) or getattr(event, "id", "legacy")),
                )
                for event in supporting
            }
            score = float(confidence.get(dimension, 0))
            summary[dimension] = {
                "confidence": round(score, 2),
                "level": "trusted" if score >= 70 else "advisory" if score >= 50 else "low",
                "source_count": len(source_refs),
                "applied_event_count": len(supporting),
                "latest_source_type": str(getattr(supporting[0], "source_type", None) or "legacy") if supporting else None,
            }
        return summary

    @staticmethod
    def _normalized_profile_value(value: Any) -> str:
        if isinstance(value, list):
            return "|".join(sorted(str(item).strip().lower() for item in value if str(item).strip()))
        return " ".join(str(value or "").split()).lower()

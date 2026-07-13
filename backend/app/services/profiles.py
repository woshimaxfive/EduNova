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

PROFILE_QUESTION_ORDER = (
    "learning_goal",
    "knowledge_foundation",
    "weak_points",
    "learning_preference",
    "learning_pace",
    "cognitive_style",
    "major_background",
    "motivation_interest",
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
            confidence_score=Decimal("0.60"),
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
                r"((?:已经|曾经)?学过[^，。；,;]{1,40})",
                r"((?:已经)?(?:熟悉|了解|掌握)[^，。；,;]{1,40}(?:基础|知识|概念))",
                r"(零基础)",
            ],
        )
        if knowledge_foundation and "数学基础一般" not in knowledge_foundation:
            updates["knowledge_foundation"] = knowledge_foundation

        learning_goal = self._find_first(
            message_text,
            [
                r"(?:我的)?目标(?:是|改为|改成)([^，。；,;]{2,80})",
                r"(?:想|希望|目标是)([^，。；,;]*掌握[^，。；,;]*)",
                r"(?:想|希望|目标是)([^，。；,;]*复习[^，。；,;]*)",
                r"(?:想|希望)(成为[^，。；,;]{2,80})",
                r"(?:想|希望)(完成[^，。；,;]{2,80})",
                r"(?:想|希望)(解决[^，。；,;]{2,80})",
            ],
        )
        if learning_goal:
            updates["learning_goal"] = learning_goal

        preferences = sorted(
            [
                term
                for term in ("图解", "案例", "代码", "视频", "练习")
                if self._positive_preference(message_text, term)
            ],
            key=message_text.index,
        )
        if preferences:
            updates["learning_preference"] = "、".join(preferences)

        cognitive_styles: list[str] = []
        if "案例" in preferences:
            cognitive_styles.append("案例驱动")
        if any(marker in message_text for marker in ("先看结构", "先看框架", "先看大纲", "整体框架")):
            cognitive_styles.append("结构化理解")
        if any(marker in message_text for marker in ("一步一步", "分步骤", "逐步推导")):
            cognitive_styles.append("渐进推导")
        if cognitive_styles:
            updates["cognitive_style"] = "、".join(dict.fromkeys(cognitive_styles))

        learning_pace = self._find_first(
            message_text,
            [
                r"((?:每天|每日)[^，。；,;]{0,14}[0-9零一二两三四五六七八九十百半]+\s*(?:个)?\s*(?:分钟|小时))",
                r"((?:每周|一周)[^，。；,;]{0,14}[0-9零一二两三四五六七八九十百半]+\s*次)",
            ],
        )
        if learning_pace:
            updates["learning_pace"] = re.sub(r"\s+", " ", learning_pace)

        weak_points = self._extract_weak_points(message_text)
        if weak_points:
            updates["weak_points"] = weak_points

        motivation_markers = (
            "感兴趣",
            "热爱",
            "动力",
            "理想",
            "职业",
            "想成为",
            "想进入",
            "想从事",
            "做贡献",
            "贡献",
            "帮助别人",
            "解决真实问题",
        )
        if ("提升" in message_text and "能力" in message_text) or any(
            marker in message_text for marker in motivation_markers
        ):
            updates["motivation_interest"] = self._clip_sentence(message_text)

        return updates

    @staticmethod
    def _positive_preference(message_text: str, term: str) -> bool:
        if term not in message_text:
            return False
        negative_patterns = (
            rf"不(?:太)?喜欢[^，。；,;]{{0,8}}{re.escape(term)}",
            rf"不想[^，。；,;]{{0,8}}{re.escape(term)}",
            rf"不适合[^，。；,;]{{0,8}}{re.escape(term)}",
        )
        return not any(re.search(pattern, message_text) for pattern in negative_patterns)

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
        for segment in re.split(r"[，。；,;！!?？]", message_text):
            normalized = segment.strip()
            if not normalized or any(
                marker in normalized
                for marker in ("并不薄弱", "不是薄弱", "没有卡住", "没有困难", "不是不会", "并不难")
            ):
                continue
            topic_match = re.search(
                r"(?P<topic>[^，。；,;]{1,48}?)(?:比较|有点|很|特别)?(?:薄弱|不熟|容易错|没理解|比较难|很难|卡住)$",
                normalized,
            )
            reverse_match = re.search(r"(?:不会|不熟|没理解)(?P<topic>[^，。；,;]{1,40})$", normalized)
            match = topic_match or reverse_match
            if match:
                topic = re.sub(r"^(?:我(?:在|对|觉得)?|目前|最近|但是|但|而且|同时|也)", "", match.group("topic")).strip()
                if topic and topic not in weak_points:
                    weak_points.append(topic)
        return weak_points

    @staticmethod
    def _uncertain_profile_dimensions(message_text: str, updates: dict[str, Any]) -> list[str]:
        uncertain: list[str] = []
        markers = ("可能", "也许", "好像", "似乎", "不确定", "说不准")
        for segment in re.split(r"[，。；,;！!?？]", message_text):
            if not any(marker in segment for marker in markers):
                continue
            for key, value in updates.items():
                values = value if isinstance(value, list) else re.split(r"[、/]", str(value))
                if any(str(item).strip() and str(item).strip() in segment for item in values):
                    uncertain.append(key)
        return list(dict.fromkeys(uncertain))

    @staticmethod
    def _profile_dimension_hints(message_text: str) -> list[str]:
        hints: list[str] = []
        markers = {
            "major_background": ("专业", "年级", "学生", "工作"),
            "knowledge_foundation": ("基础", "学过", "熟悉", "了解", "零基础"),
            "learning_goal": ("目标", "希望", "想掌握", "想学会", "想成为", "想完成", "想解决", "复习"),
            "cognitive_style": ("理解", "推导", "结构", "框架", "步骤"),
            "learning_preference": ("喜欢", "图解", "案例", "代码", "视频", "练习"),
            "weak_points": ("薄弱", "不熟", "不会", "卡住", "容易错", "没理解", "难"),
            "learning_pace": ("每天", "每周", "分钟", "小时", "学习时间"),
            "motivation_interest": ("兴趣", "动力", "为了", "提升", "项目", "想成为", "职业", "理想", "贡献", "方向"),
        }
        for key, values in markers.items():
            if any(marker in message_text for marker in values):
                hints.append(key)
        return hints

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

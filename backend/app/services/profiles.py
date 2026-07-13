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
    "major_background": "你目前的专业方向或学习经历是什么？",
    "knowledge_foundation": "关于当前课程，你已经学过哪些基础内容？",
    "learning_goal": "这门课你最想先解决什么问题？",
    "cognitive_style": "遇到新概念时，你通常怎样理解得最快？",
    "learning_preference": "什么样的内容呈现和练习方式更适合你？",
    "weak_points": "最近哪一个知识点最容易卡住或出错？",
    "learning_pace": "你通常每次或每周能安排多少学习时间？",
    "motivation_interest": "是什么目标或兴趣让你想继续学这门课？",
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
        next_question_dimension, next_question = self._next_question_target(profile)
        return profile_to_api(
            profile,
            version=self.repository.count_events_for_profile(profile.id if profile is not None else None),
            next_question=next_question,
            next_question_dimension=next_question_dimension,
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

        if "提升" in message_text and "能力" in message_text:
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
            "learning_goal": ("目标", "希望", "想掌握", "想学会", "复习"),
            "cognitive_style": ("理解", "推导", "结构", "框架", "步骤"),
            "learning_preference": ("喜欢", "图解", "案例", "代码", "视频", "练习"),
            "weak_points": ("薄弱", "不熟", "不会", "卡住", "容易错", "没理解", "难"),
            "learning_pace": ("每天", "每周", "分钟", "小时", "学习时间"),
            "motivation_interest": ("兴趣", "动力", "为了", "提升", "项目"),
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

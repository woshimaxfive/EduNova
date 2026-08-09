from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from backend.app.models import (
    AgentRunLog,
    ChatMessage,
    ChatMessageAttachment,
    ChatSession,
    Course,
    GeneratedResource,
    KnowledgePoint,
    Material,
    User,
)
from backend.app.schemas.tutor import TutorResourceJob
from backend.app.services.course_answers import ConversationContext, HomeAnswerReview


class InvalidSessionScopeError(ValueError):
    pass


class SessionNotFoundError(LookupError):
    pass


class EmptyMessageError(ValueError):
    pass


class InvalidMaterialContextError(ValueError):
    pass


class InvalidResourceContextError(ValueError):
    pass


class TutorSessionRepository(Protocol):
    def list_sessions(self, user_id: int, scope: str, course_id: int | None = None) -> list[ChatSession]: ...

    def get_session_for_user(self, session_id: int, user_id: int) -> ChatSession | None: ...

    def list_home_history(
        self, user_id: int, page: int, page_size: int, query: str
    ) -> tuple[list[ChatSession], int]: ...

    def find_history_match(self, session_id: int, query: str) -> str | None: ...

    def user_can_access_course(self, user_id: int, course_id: int) -> bool: ...

    def get_course_for_user(self, user_id: int, course_id: int) -> Course | None: ...

    def get_resource_for_user(self, user_id: int, resource_id: int) -> GeneratedResource | None: ...

    def get_knowledge_point(self, course_id: int, knowledge_point_id: int) -> KnowledgePoint | None: ...

    def find_knowledge_point_for_topic(self, course_id: int, topic: str) -> KnowledgePoint | None: ...

    def list_messages(self, session_id: int) -> list[ChatMessage]: ...

    def get_assistant_message(self, user_id: int, session_id: int, message_id: int) -> ChatMessage | None: ...

    def add_session(self, session: ChatSession) -> None: ...

    def add_message(self, message: ChatMessage) -> None: ...

    def pending_attachments(
        self, user_id: int, session_id: int, attachment_ids: list[int]
    ) -> list[ChatMessageAttachment]: ...

    def bind_attachments(self, attachments: list[ChatMessageAttachment], message_id: int) -> None: ...

    def attachment_map(self, message_ids: list[int]) -> dict[int, list[ChatMessageAttachment]]: ...

    def resource_job_map(self, user_id: int, message_ids: list[int]) -> dict[int, list[TutorResourceJob]]: ...

    def register_resource_job(self, user_id: int, session_id: int, message_id: int, job_id: int) -> None: ...

    def link_resource_job(self, user_id: int, session_id: int, message_id: int, job_id: int) -> None: ...

    def bound_attachments(
        self, user_id: int, session_id: int, message_ids: list[int]
    ) -> list[ChatMessageAttachment]: ...

    def add_agent_log(self, log: AgentRunLog) -> None: ...

    def list_home_materials_for_user(self, user_id: int, material_ids: list[int]) -> list[Material]: ...

    def touch_session(self, session: ChatSession) -> None: ...

    def flush(self) -> None: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...


class CourseCitationSearcher(Protocol):
    def search(self, user: User, course_id: int, query: str, top_k: int) -> Any: ...


class MaterialCitationSearcher(Protocol):
    def search(self, user: User, material_ids: list[int], query: str, top_k: int = 5) -> Any: ...


class CourseAnswerGenerator(Protocol):
    def generate_home(
        self,
        user: User,
        question: str,
        citations: list[dict[str, Any]] | None = None,
        use_web_search: bool = False,
        deep_thinking: bool = False,
        warnings: list[str] | None = None,
        conversation_context: ConversationContext | None = None,
        plan_summary: str | None = None,
        learner_context: dict[str, Any] | None = None,
    ) -> Any: ...

    def generate(
        self,
        user: User,
        question: str,
        citations: list[dict[str, Any]],
        conversation_context: ConversationContext | None = None,
        learner_context: dict[str, Any] | None = None,
        reasoning_mode: str = "auto",
    ) -> Any: ...

    def stream(
        self,
        user: User,
        question: str,
        citations: list[dict[str, Any]],
        conversation_context: ConversationContext | None = None,
        learner_context: dict[str, Any] | None = None,
        reasoning_mode: str = "auto",
    ) -> Any: ...

    def stream_home(
        self,
        user: User,
        question: str,
        citations: list[dict[str, Any]] | None = None,
        use_web_search: bool = False,
        deep_thinking: bool = False,
        warnings: list[str] | None = None,
        conversation_context: ConversationContext | None = None,
        plan_summary: str | None = None,
        learner_context: dict[str, Any] | None = None,
    ) -> Any: ...

    def plan_home(self, user: User, question: str, citations: list[dict[str, Any]]) -> str: ...

    def review_home(
        self,
        user: User,
        question: str,
        answer: str,
        citations: list[dict[str, Any]],
        warnings: list[str] | None = None,
    ) -> HomeAnswerReview | None: ...

    def repair_home(
        self,
        user: User,
        question: str,
        draft: str,
        citations: list[dict[str, Any]],
        risk_flags: list[str],
    ) -> str | None: ...


class ProfileEventRecorder(Protocol):
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
    ) -> Any: ...


class WebSearchProvider(Protocol):
    def search(self, query: str, max_results: int = 5) -> Any: ...


class NativeWebSearchProvider(Protocol):
    def native_web_search(
        self,
        user: User,
        query: str,
        *,
        reasoning_mode: str = "auto",
        force: bool = False,
    ) -> Any: ...


class SemanticDecisionProvider(Protocol):
    def decide(self, **kwargs: Any) -> Any: ...


class ConversationMemoryProvider(Protocol):
    def search(
        self, *, user: User, current_session_id: int, query: str, limit: int = 5
    ) -> list[dict[str, Any]]: ...

    def index_pair(
        self,
        *,
        user: User,
        session: ChatSession,
        user_message: ChatMessage,
        assistant_message: ChatMessage,
    ) -> bool: ...


@dataclass(frozen=True)
class GeneratedAnswer:
    content: str
    trace_id: str | None

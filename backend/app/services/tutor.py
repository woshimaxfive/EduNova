from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Iterator, Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import ChatMessage, ChatSession, Course, CourseEnrollment, User
from backend.app.schemas.tutor import TutorSessionDetail, TutorSessionSummary, session_detail_to_api, session_to_summary
from backend.app.services.course_answers import CourseAnswerGenerationError, HOME_MODEL_NOT_CONFIGURED_MESSAGE


COURSE_ASSISTANT_REPLY_WITH_CITATIONS = "我先从课程资料里找到了相关依据。下面保留真实引用片段，后续接入大模型后会基于这些来源生成完整回答。"
COURSE_ASSISTANT_REPLY_WITHOUT_CITATIONS = "我先检查了课程资料，但还没有足够依据支撑这个问题。"
COURSE_ASSISTANT_REPLY_MODEL_NOT_CONFIGURED = "已找到资料依据，但当前未配置可用模型。"


class InvalidSessionScopeError(ValueError):
    pass


class SessionNotFoundError(LookupError):
    pass


class EmptyMessageError(ValueError):
    pass


class TutorSessionRepository(Protocol):
    def list_sessions(self, user_id: int, scope: str, course_id: int | None = None) -> list[ChatSession]:
        ...

    def get_session_for_user(self, session_id: int, user_id: int) -> ChatSession | None:
        ...

    def user_can_access_course(self, user_id: int, course_id: int) -> bool:
        ...

    def list_messages(self, session_id: int) -> list[ChatMessage]:
        ...

    def add_session(self, session: ChatSession) -> None:
        ...

    def add_message(self, message: ChatMessage) -> None:
        ...

    def touch_session(self, session: ChatSession) -> None:
        ...

    def flush(self) -> None:
        ...

    def commit(self) -> None:
        ...

    def rollback(self) -> None:
        ...


class CourseCitationSearcher(Protocol):
    def search(self, user: User, course_id: int, query: str, top_k: int) -> Any:
        ...


class CourseAnswerGenerator(Protocol):
    def generate_home(self, user: User, question: str) -> Any:
        ...

    def generate(self, user: User, question: str, citations: list[dict[str, Any]]) -> Any:
        ...

    def stream(self, user: User, question: str, citations: list[dict[str, Any]]) -> Any:
        ...


@dataclass(frozen=True)
class GeneratedAnswer:
    content: str
    trace_id: str | None


class SqlAlchemyTutorSessionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_sessions(self, user_id: int, scope: str, course_id: int | None = None) -> list[ChatSession]:
        statement = select(ChatSession).where(
            ChatSession.user_id == user_id,
            ChatSession.scope == scope,
            ChatSession.archived_from_home.is_(False),
        )
        if course_id is not None:
            statement = statement.where(ChatSession.course_id == course_id)

        return list(self.db.scalars(statement.order_by(ChatSession.updated_at.desc(), ChatSession.id.desc())))

    def get_session_for_user(self, session_id: int, user_id: int) -> ChatSession | None:
        return self.db.scalar(
            select(ChatSession).where(
                ChatSession.id == session_id,
                ChatSession.user_id == user_id,
            )
        )

    def user_can_access_course(self, user_id: int, course_id: int) -> bool:
        owned_course = self.db.scalar(
            select(Course.id).where(
                Course.id == course_id,
                Course.owner_id == user_id,
            )
        )
        if owned_course is not None:
            return True

        enrollment = self.db.scalar(
            select(CourseEnrollment.id).where(
                CourseEnrollment.user_id == user_id,
                CourseEnrollment.course_id == course_id,
            )
        )
        return enrollment is not None

    def list_messages(self, session_id: int) -> list[ChatMessage]:
        return list(
            self.db.scalars(
                select(ChatMessage)
                .where(ChatMessage.session_id == session_id)
                .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
            )
        )

    def add_session(self, session: ChatSession) -> None:
        self.db.add(session)

    def add_message(self, message: ChatMessage) -> None:
        self.db.add(message)

    def touch_session(self, session: ChatSession) -> None:
        session.updated_at = datetime.now(UTC)
        self.db.add(session)

    def flush(self) -> None:
        self.db.flush()

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()


class TutorSessionService:
    def __init__(
        self,
        repository: TutorSessionRepository,
        course_citation_searcher: CourseCitationSearcher | None = None,
        course_answer_generator: CourseAnswerGenerator | None = None,
    ) -> None:
        self.repository = repository
        self.course_citation_searcher = course_citation_searcher
        self.course_answer_generator = course_answer_generator

    def create_session(
        self,
        user: User,
        scope: str,
        course_id: int | None,
        mode: str,
        title: str,
    ) -> ChatSession:
        normalized_scope = self._normalize_scope(scope)
        normalized_course_id = self._normalize_course_id(user.id, normalized_scope, course_id)
        normalized_mode = self._normalize_mode(mode)
        normalized_title = title.strip() or "新的学习对话"

        session = ChatSession(
            user_id=user.id,
            course_id=normalized_course_id,
            scope=normalized_scope,
            title=normalized_title[:255],
            mode=normalized_mode,
            archived_from_home=False,
        )

        try:
            self.repository.add_session(session)
            self.repository.flush()
            self.repository.commit()
        except Exception:
            self.repository.rollback()
            raise

        return session

    def list_sessions(self, user: User, scope: str, course_id: int | None = None) -> list[TutorSessionSummary]:
        normalized_scope = self._normalize_scope(scope)
        normalized_course_id = None
        if normalized_scope == "course":
            normalized_course_id = self._normalize_course_id(user.id, normalized_scope, course_id)

        return [
            session_to_summary(session)
            for session in self.repository.list_sessions(
                user_id=user.id,
                scope=normalized_scope,
                course_id=normalized_course_id,
            )
        ]

    def get_session(self, user: User, session_id: int) -> TutorSessionDetail:
        session = self._get_session_for_user(user.id, session_id)
        return session_detail_to_api(session, self.repository.list_messages(session.id))

    def append_message(self, user: User, session_id: int, content: str) -> TutorSessionDetail:
        message_text = content.strip()
        if not message_text:
            raise EmptyMessageError("消息不能为空。")

        session = self._get_session_for_user(user.id, session_id)
        citation_json = self._search_course_citations(user=user, session=session, message_text=message_text)
        generated_answer = self._generate_answer(
            user=user,
            session=session,
            message_text=message_text,
            citation_json=citation_json,
        )
        assistant_reply = generated_answer.content or self._build_assistant_reply(session=session, citation_json=citation_json)
        return self._persist_message_pair(
            user=user,
            session=session,
            message_text=message_text,
            assistant_reply=assistant_reply,
            citation_json=citation_json,
            trace_id=generated_answer.trace_id,
        )

    def stream_message(self, user: User, session_id: int, content: str) -> Iterator[dict[str, Any]]:
        message_text = content.strip()
        if not message_text:
            raise EmptyMessageError("消息不能为空。")

        session = self._get_session_for_user(user.id, session_id)
        if session.scope != "course":
            raise InvalidSessionScopeError("只有课程会话支持流式回答。")

        citation_json = self._search_course_citations(user=user, session=session, message_text=message_text)
        return self._stream_course_response(
            user=user,
            session=session,
            message_text=message_text,
            citation_json=citation_json,
        )

    def _stream_course_response(
        self,
        user: User,
        session: ChatSession,
        message_text: str,
        citation_json: list[dict[str, Any]],
    ) -> Iterator[dict[str, Any]]:
        try:
            if not citation_json:
                assistant_reply = COURSE_ASSISTANT_REPLY_WITHOUT_CITATIONS
                yield self._stream_event(
                    "metadata",
                    session_id=session.id,
                    trace_id=None,
                    citation_count=0,
                    used_model=False,
                )
                yield {"event": "token", "data": {"content": assistant_reply}}
                detail = self._persist_message_pair(
                    user=user,
                    session=session,
                    message_text=message_text,
                    assistant_reply=assistant_reply,
                    citation_json=[],
                    trace_id=None,
                )
                yield {"event": "done", "data": detail.model_dump()}
                return

            if self.course_answer_generator is None:
                assistant_reply = COURSE_ASSISTANT_REPLY_MODEL_NOT_CONFIGURED
                yield self._stream_event(
                    "metadata",
                    session_id=session.id,
                    trace_id=None,
                    citation_count=len(citation_json),
                    used_model=False,
                )
                yield {"event": "token", "data": {"content": assistant_reply}}
                detail = self._persist_message_pair(
                    user=user,
                    session=session,
                    message_text=message_text,
                    assistant_reply=assistant_reply,
                    citation_json=citation_json,
                    trace_id=None,
                )
                yield {"event": "done", "data": detail.model_dump()}
                return

            stream_result = self.course_answer_generator.stream(user=user, question=message_text, citations=citation_json)
            trace_id = getattr(stream_result, "trace_id", None)
            used_model = bool(getattr(stream_result, "used_model", True))
            yield self._stream_event(
                "metadata",
                session_id=session.id,
                trace_id=trace_id,
                citation_count=len(citation_json),
                used_model=used_model,
            )

            answer_parts: list[str] = []
            for token in getattr(stream_result, "tokens"):
                if not isinstance(token, str) or not token:
                    continue
                answer_parts.append(token)
                yield {"event": "token", "data": {"content": token}}

            assistant_reply = "".join(answer_parts).strip()
            if not assistant_reply:
                raise CourseAnswerGenerationError("模型暂不可用，请检查设置或稍后重试。")

            detail = self._persist_message_pair(
                user=user,
                session=session,
                message_text=message_text,
                assistant_reply=assistant_reply,
                citation_json=citation_json,
                trace_id=trace_id,
            )
            yield {"event": "done", "data": detail.model_dump()}
        except CourseAnswerGenerationError:
            yield {
                "event": "error",
                "data": {
                    "code": "MODEL_PROVIDER_ERROR",
                    "message": "模型暂不可用，请检查设置或稍后重试。",
                },
            }

    def _generate_answer(
        self,
        user: User,
        session: ChatSession,
        message_text: str,
        citation_json: list[dict[str, Any]],
    ) -> GeneratedAnswer:
        if session.scope == "home":
            if self.course_answer_generator is None:
                return GeneratedAnswer(content=HOME_MODEL_NOT_CONFIGURED_MESSAGE, trace_id=None)
            answer = self.course_answer_generator.generate_home(user=user, question=message_text)
            return GeneratedAnswer(
                content=str(getattr(answer, "content", "") or ""),
                trace_id=getattr(answer, "trace_id", None),
            )

        if session.scope != "course" or not citation_json:
            return GeneratedAnswer(content="", trace_id=None)
        if self.course_answer_generator is None:
            return GeneratedAnswer(content=COURSE_ASSISTANT_REPLY_MODEL_NOT_CONFIGURED, trace_id=None)

        answer = self.course_answer_generator.generate(user=user, question=message_text, citations=citation_json)
        return GeneratedAnswer(
            content=str(getattr(answer, "content", "") or ""),
            trace_id=getattr(answer, "trace_id", None),
        )

    def _persist_message_pair(
        self,
        user: User,
        session: ChatSession,
        message_text: str,
        assistant_reply: str,
        citation_json: list[dict[str, Any]],
        trace_id: str | None,
    ) -> TutorSessionDetail:
        user_message = ChatMessage(
            session_id=session.id,
            user_id=user.id,
            role="user",
            content=message_text,
            citation_json=[],
            trace_id=None,
        )
        assistant_message = ChatMessage(
            session_id=session.id,
            user_id=user.id,
            role="assistant",
            content=assistant_reply,
            citation_json=citation_json,
            trace_id=trace_id,
        )

        try:
            self.repository.add_message(user_message)
            self.repository.add_message(assistant_message)
            self.repository.touch_session(session)
            self.repository.flush()
            self.repository.commit()
        except Exception:
            self.repository.rollback()
            raise

        return session_detail_to_api(session, self.repository.list_messages(session.id))

    @staticmethod
    def _stream_event(
        event: str,
        session_id: int,
        trace_id: str | None,
        citation_count: int,
        used_model: bool,
    ) -> dict[str, Any]:
        return {
            "event": event,
            "data": {
                "session_id": str(session_id),
                "trace_id": trace_id,
                "citation_count": citation_count,
                "used_model": used_model,
            },
        }

    def _search_course_citations(self, user: User, session: ChatSession, message_text: str) -> list[dict[str, Any]]:
        if session.scope != "course" or session.course_id is None or self.course_citation_searcher is None:
            return []

        result = self.course_citation_searcher.search(
            user=user,
            course_id=session.course_id,
            query=message_text,
            top_k=5,
        )
        return [self._citation_to_dict(item) for item in result.results]

    @staticmethod
    def _citation_to_dict(item: Any) -> dict[str, Any]:
        if hasattr(item, "model_dump"):
            return item.model_dump()
        if isinstance(item, dict):
            return item
        citation = {
            key: getattr(item, key, None)
            for key in (
                "chunk_id",
                "course_id",
                "material_id",
                "knowledge_point_id",
                "content",
                "source_title",
                "page_number",
                "section_title",
                "score",
            )
        }
        for key in ("keyword_score", "vector_score", "retrieval_source", "embedding_status"):
            value = getattr(item, key, None)
            if value is not None:
                citation[key] = value
        return citation

    @staticmethod
    def _build_assistant_reply(session: ChatSession, citation_json: list[dict[str, Any]]) -> str:
        if session.scope != "course":
            return HOME_MODEL_NOT_CONFIGURED_MESSAGE
        if citation_json:
            return COURSE_ASSISTANT_REPLY_MODEL_NOT_CONFIGURED
        return COURSE_ASSISTANT_REPLY_WITHOUT_CITATIONS

    def _get_session_for_user(self, user_id: int, session_id: int) -> ChatSession:
        session = self.repository.get_session_for_user(session_id=session_id, user_id=user_id)
        if session is None:
            raise SessionNotFoundError("会话不存在或无权访问。")
        return session

    def _normalize_course_id(self, user_id: int, scope: str, course_id: int | None) -> int | None:
        if scope == "home":
            if course_id is not None:
                raise InvalidSessionScopeError("主页会话不能绑定课程。")
            return None

        if course_id is None:
            raise InvalidSessionScopeError("课程会话必须提供 course_id。")
        if not self.repository.user_can_access_course(user_id, course_id):
            raise SessionNotFoundError("课程不存在或无权访问。")
        return course_id

    @staticmethod
    def _normalize_scope(scope: str) -> str:
        if scope not in {"home", "course"}:
            raise InvalidSessionScopeError("scope 只能是 home 或 course。")
        return scope

    @staticmethod
    def _normalize_mode(mode: str) -> str:
        if mode not in {"chat", "socratic", "direct"}:
            raise InvalidSessionScopeError("mode 只能是 chat、socratic 或 direct。")
        return mode

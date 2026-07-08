from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from time import perf_counter
from typing import Any, Iterator, Protocol

from langgraph.graph import END, START, StateGraph
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.api.errors import make_trace_id
from backend.app.agents.runtime import PendingAgentTrace, agent_log_from_pending_trace
from backend.app.agents.schemas import AgentState
from backend.app.models import AgentRunLog, ChatMessage, ChatSession, Course, CourseEnrollment, Material, User
from backend.app.schemas.tutor import TutorSessionDetail, TutorSessionSummary, session_detail_to_api, session_to_summary
from backend.app.services.course_answers import ConversationContext, CourseAnswerGenerationError, HOME_MODEL_NOT_CONFIGURED_MESSAGE


COURSE_ASSISTANT_REPLY_WITH_CITATIONS = "我先从课程资料里找到了相关依据。下面保留真实引用片段，后续接入大模型后会基于这些来源生成完整回答。"
COURSE_ASSISTANT_REPLY_WITHOUT_CITATIONS = "我先检查了课程资料，但还没有足够依据支撑这个问题。"
COURSE_ASSISTANT_REPLY_MODEL_NOT_CONFIGURED = "已找到资料依据，但当前未配置可用模型。"
COURSE_TUTOR_GRAPH_STEPS = ["profile", "retriever", "tutor", "weakness", "review", "next_action"]
HOME_TUTOR_GRAPH_STEPS = ["home_profile", "material_context", "web_search", "answer", "review"]
CONTEXT_RECENT_MESSAGE_LIMIT = 12
CONTEXT_RETRIEVAL_USER_MESSAGE_LIMIT = 2
CONTEXT_MESSAGE_CHAR_LIMIT = 1200
CONTEXT_TOTAL_CHAR_LIMIT = 6000
CONTEXT_SUMMARY_CHAR_LIMIT = 1500


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

    def add_agent_log(self, log: AgentRunLog) -> None:
        ...

    def list_home_materials_for_user(self, user_id: int, material_ids: list[int]) -> list[Material]:
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
    def generate_home(
        self,
        user: User,
        question: str,
        citations: list[dict[str, Any]] | None = None,
        use_web_search: bool = False,
        deep_thinking: bool = False,
        warnings: list[str] | None = None,
        conversation_context: ConversationContext | None = None,
    ) -> Any:
        ...

    def generate(
        self,
        user: User,
        question: str,
        citations: list[dict[str, Any]],
        conversation_context: ConversationContext | None = None,
    ) -> Any:
        ...

    def stream(
        self,
        user: User,
        question: str,
        citations: list[dict[str, Any]],
        conversation_context: ConversationContext | None = None,
    ) -> Any:
        ...


class ProfileEventRecorder(Protocol):
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
    ) -> Any:
        ...


class WebSearchProvider(Protocol):
    def search(self, query: str, max_results: int = 5) -> Any:
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
                ChatSession.archived_from_home.is_(False),
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

    def add_agent_log(self, log: AgentRunLog) -> None:
        self.db.add(log)

    def list_home_materials_for_user(self, user_id: int, material_ids: list[int]) -> list[Material]:
        if not material_ids:
            return []
        unique_ids = list(dict.fromkeys(material_ids))[:10]
        return list(
            self.db.scalars(
                select(Material).where(
                    Material.user_id == user_id,
                    Material.id.in_(unique_ids),
                    Material.parse_status == "completed",
                )
            )
        )

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
        profile_event_recorder: ProfileEventRecorder | None = None,
        web_search_service: WebSearchProvider | None = None,
    ) -> None:
        self.repository = repository
        self.course_citation_searcher = course_citation_searcher
        self.course_answer_generator = course_answer_generator
        self.profile_event_recorder = profile_event_recorder
        self.web_search_service = web_search_service

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

    def rename_session(self, user: User, session_id: int, title: str) -> TutorSessionSummary:
        normalized_title = title.strip()
        if not normalized_title:
            raise EmptyMessageError("会话名称不能为空。")

        session = self._get_session_for_user(user.id, session_id)
        session.title = normalized_title[:255]

        try:
            self.repository.touch_session(session)
            self.repository.flush()
            self.repository.commit()
        except Exception:
            self.repository.rollback()
            raise

        return session_to_summary(session)

    def delete_session(self, user: User, session_id: int) -> TutorSessionSummary:
        session = self._get_session_for_user(user.id, session_id)
        session.archived_from_home = True

        try:
            self.repository.touch_session(session)
            self.repository.flush()
            self.repository.commit()
        except Exception:
            self.repository.rollback()
            raise

        return session_to_summary(session)

    def append_message(
        self,
        user: User,
        session_id: int,
        content: str,
        use_web_search: bool = False,
        deep_thinking: bool = False,
        selected_material_ids: list[int] | None = None,
    ) -> TutorSessionDetail:
        message_text = content.strip()
        if not message_text:
            raise EmptyMessageError("消息不能为空。")

        session = self._get_session_for_user(user.id, session_id)
        if session.scope == "course":
            return CourseTutorGraphRunner(self).append(
                user=user,
                session=session,
                message_text=message_text,
            )

        conversation_context = self._build_conversation_context(session)
        retrieval_query = self._build_contextual_query(message_text, conversation_context)
        context_metadata = self._context_metadata(
            conversation_context,
            retrieval_query,
            message_text,
            retrieval_active=session.scope == "course" or use_web_search,
        )
        warnings: list[str] = []
        citation_json = self._collect_citations(
            user=user,
            session=session,
            message_text=message_text,
            retrieval_query=retrieval_query,
            use_web_search=use_web_search,
            selected_material_ids=selected_material_ids or [],
            warnings=warnings,
        )
        generated_answer = self._generate_answer(
            user=user,
            session=session,
            message_text=message_text,
            citation_json=citation_json,
            use_web_search=use_web_search,
            deep_thinking=deep_thinking,
            warnings=warnings,
            conversation_context=conversation_context if conversation_context.has_context else None,
        )
        assistant_reply = generated_answer.content or self._build_assistant_reply(session=session, citation_json=citation_json)
        return self._persist_message_pair(
            user=user,
            session=session,
            message_text=message_text,
            assistant_reply=assistant_reply,
            citation_json=citation_json,
            trace_id=generated_answer.trace_id,
            home_tool_metadata={
                "use_web_search": use_web_search,
                "deep_thinking": deep_thinking,
                "warning_count": len(warnings),
                "warnings": warnings,
            },
            context_metadata=context_metadata,
        )

    def stream_message(self, user: User, session_id: int, content: str) -> Iterator[dict[str, Any]]:
        message_text = content.strip()
        if not message_text:
            raise EmptyMessageError("消息不能为空。")

        session = self._get_session_for_user(user.id, session_id)
        if session.scope != "course":
            raise InvalidSessionScopeError("只有课程会话支持流式回答。")

        return CourseTutorGraphRunner(self).stream(
            user=user,
            session=session,
            message_text=message_text,
        )

    def _stream_course_response(
        self,
        user: User,
        session: ChatSession,
        message_text: str,
        citation_json: list[dict[str, Any]],
        conversation_context: ConversationContext | None = None,
        context_metadata: dict[str, Any] | None = None,
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
                    context_metadata=context_metadata,
                )
                yield {"event": "token", "data": {"content": assistant_reply}}
                detail = self._persist_message_pair(
                    user=user,
                    session=session,
                    message_text=message_text,
                    assistant_reply=assistant_reply,
                    citation_json=[],
                    trace_id=None,
                    home_tool_metadata=None,
                    context_metadata=context_metadata,
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
                    context_metadata=context_metadata,
                )
                yield {"event": "token", "data": {"content": assistant_reply}}
                detail = self._persist_message_pair(
                    user=user,
                    session=session,
                    message_text=message_text,
                    assistant_reply=assistant_reply,
                    citation_json=citation_json,
                    trace_id=None,
                    home_tool_metadata=None,
                    context_metadata=context_metadata,
                )
                yield {"event": "done", "data": detail.model_dump()}
                return

            stream_result = self.course_answer_generator.stream(
                user=user,
                question=message_text,
                citations=citation_json,
                conversation_context=conversation_context,
            )
            trace_id = getattr(stream_result, "trace_id", None)
            used_model = bool(getattr(stream_result, "used_model", True))
            yield self._stream_event(
                "metadata",
                session_id=session.id,
                trace_id=trace_id,
                citation_count=len(citation_json),
                used_model=used_model,
                context_metadata=context_metadata,
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
                home_tool_metadata=None,
                context_metadata=context_metadata,
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
        use_web_search: bool = False,
        deep_thinking: bool = False,
        warnings: list[str] | None = None,
        conversation_context: ConversationContext | None = None,
    ) -> GeneratedAnswer:
        if session.scope == "home":
            if self.course_answer_generator is None:
                return GeneratedAnswer(content=HOME_MODEL_NOT_CONFIGURED_MESSAGE, trace_id=None)
            answer = self.course_answer_generator.generate_home(
                user=user,
                question=message_text,
                citations=citation_json,
                use_web_search=use_web_search,
                deep_thinking=deep_thinking,
                warnings=warnings or [],
                conversation_context=conversation_context,
            )
            return GeneratedAnswer(
                content=str(getattr(answer, "content", "") or ""),
                trace_id=getattr(answer, "trace_id", None),
            )

        if session.scope != "course" or not citation_json:
            return GeneratedAnswer(content="", trace_id=None)
        if self.course_answer_generator is None:
            return GeneratedAnswer(content=COURSE_ASSISTANT_REPLY_MODEL_NOT_CONFIGURED, trace_id=None)

        answer = self.course_answer_generator.generate(
            user=user,
            question=message_text,
            citations=citation_json,
            conversation_context=conversation_context,
        )
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
        home_tool_metadata: dict[str, Any] | None = None,
        context_metadata: dict[str, Any] | None = None,
        course_trace_records: list[PendingAgentTrace] | None = None,
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
            if self.profile_event_recorder is not None and session.scope == "course":
                self.profile_event_recorder.record_course_question_event(
                    user=user,
                    session=session,
                    user_message=user_message,
                    assistant_message=assistant_message,
                    message_text=message_text,
                    citation_json=citation_json,
                    trace_id=trace_id,
                )
            if course_trace_records is not None and session.scope == "course" and trace_id is not None:
                self._persist_course_tutor_graph_trace(
                    user=user,
                    session=session,
                    assistant_message=assistant_message,
                    trace_id=trace_id,
                    trace_records=course_trace_records,
                )
            else:
                self._persist_course_tutor_trace(
                    user=user,
                    session=session,
                    assistant_message=assistant_message,
                    citation_json=citation_json,
                    trace_id=trace_id,
                    context_metadata=context_metadata,
                )
            self._persist_home_tutor_trace(
                user=user,
                session=session,
                assistant_message=assistant_message,
                citation_json=citation_json,
                trace_id=trace_id,
                tool_metadata=home_tool_metadata,
                context_metadata=context_metadata,
            )
            self.repository.commit()
        except Exception:
            self.repository.rollback()
            raise

        return session_detail_to_api(session, self.repository.list_messages(session.id))

    def _persist_course_tutor_graph_trace(
        self,
        user: User,
        session: ChatSession,
        assistant_message: ChatMessage,
        trace_id: str,
        trace_records: list[PendingAgentTrace],
    ) -> None:
        artifact_id = str(assistant_message.id) if assistant_message.id is not None else None
        for pending in trace_records:
            self.repository.add_agent_log(
                agent_log_from_pending_trace(
                    pending=pending,
                    trace_id=trace_id,
                    user_id=user.id,
                    course_id=session.course_id,
                    workflow="course_tutor",
                    artifact_type="chat_message",
                    artifact_id=artifact_id,
                )
            )

    def _persist_home_tutor_trace(
        self,
        user: User,
        session: ChatSession,
        assistant_message: ChatMessage,
        citation_json: list[dict[str, Any]],
        trace_id: str | None,
        tool_metadata: dict[str, Any] | None,
        context_metadata: dict[str, Any] | None,
    ) -> None:
        if session.scope != "home" or trace_id is None:
            return

        material_count = sum(1 for item in citation_json if item.get("source_type") == "material")
        web_result_count = sum(1 for item in citation_json if item.get("source_type") == "web")
        base_metadata: dict[str, Any] = {
            "workflow": "home_tutor",
            "artifact_type": "chat_message",
            "artifact_id": str(assistant_message.id) if assistant_message.id is not None else None,
            "citation_count": len(citation_json),
            "material_count": material_count,
            "web_result_count": web_result_count,
            "use_web_search": bool((tool_metadata or {}).get("use_web_search")),
            "deep_thinking": bool((tool_metadata or {}).get("deep_thinking")),
            "warning_count": int((tool_metadata or {}).get("warning_count") or 0),
        }
        base_metadata.update(self._safe_trace_context_metadata(context_metadata))
        warning_text = "；".join(str(item) for item in (tool_metadata or {}).get("warnings", [])[:2]) if tool_metadata else ""
        step_summaries = [
            ("home_profile", "读取主页学习上下文", "已加载主页会话与学生学习空间摘要。"),
            ("material_context", "读取选中资料短摘要", f"命中 {material_count} 份已解析资料。"),
            ("web_search", "执行联网搜索", f"返回 {web_result_count} 条联网来源。" if web_result_count else warning_text or "未返回联网来源。"),
            ("answer", "生成主页学习回答", "已生成面向学生的学习建议。"),
            ("review", "审核来源、隐私和工具状态", "ReviewAgent 审核通过。"),
        ]

        for index, (agent_name, input_summary, output_summary) in enumerate(step_summaries, start=1):
            metadata = dict(base_metadata)
            if agent_name == "review":
                metadata.update(
                    {
                        "review_status": "passed",
                        "confidence": 0.8 if citation_json else 0.66,
                        "risk_flags": [],
                        "safety_summary": "已隐藏原始思维链、系统提示词、完整模型输入和资料全文。",
                    }
                )
            self.repository.add_agent_log(
                AgentRunLog(
                    trace_id=trace_id,
                    user_id=user.id,
                    course_id=None,
                    agent_name=agent_name,
                    step_index=index,
                    status="completed",
                    input_summary=input_summary,
                    output_summary=output_summary,
                    duration_ms=0,
                    metadata_json=metadata,
                )
            )

    def _persist_course_tutor_trace(
        self,
        user: User,
        session: ChatSession,
        assistant_message: ChatMessage,
        citation_json: list[dict[str, Any]],
        trace_id: str | None,
        context_metadata: dict[str, Any] | None,
    ) -> None:
        if session.scope != "course" or trace_id is None:
            return

        citation_count = len(citation_json)
        artifact_id = str(assistant_message.id) if assistant_message.id is not None else None
        base_metadata: dict[str, Any] = {
            "workflow": "course_tutor",
            "artifact_type": "chat_message",
            "artifact_id": artifact_id,
            "citation_count": citation_count,
        }
        base_metadata.update(self._safe_trace_context_metadata(context_metadata))
        step_summaries = [
            ("profile", "读取学习画像与课程上下文", "已加载用户画像摘要。"),
            ("retriever", "检索当前课程知识切片", f"命中 {citation_count} 条课程引用。"),
            ("tutor", "生成课程导师回答", "已生成带引用的课程回答。"),
            ("weakness", "识别弱点候选", "已同步课程问答弱点候选。"),
            ("review", "审核回答依据与安全边界", "ReviewAgent 审核通过。"),
            ("next_action", "生成下一步学习动作", "建议查看来源、生成资源或进入练习。"),
        ]

        for index, (agent_name, input_summary, output_summary) in enumerate(step_summaries, start=1):
            metadata = dict(base_metadata)
            if agent_name == "review":
                metadata.update(
                    {
                        "review_status": "passed",
                        "confidence": 0.82,
                        "risk_flags": [],
                        "safety_summary": "已完成课程回答依据、隐私和下一步动作审核。",
                    }
                )
            self.repository.add_agent_log(
                AgentRunLog(
                    trace_id=trace_id,
                    user_id=user.id,
                    course_id=session.course_id,
                    agent_name=agent_name,
                    step_index=index,
                    status="completed",
                    input_summary=input_summary,
                    output_summary=output_summary,
                    duration_ms=0,
                    metadata_json=metadata,
                )
            )

    @staticmethod
    def _stream_event(
        event: str,
        session_id: int,
        trace_id: str | None,
        citation_count: int,
        used_model: bool,
        context_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        data: dict[str, Any] = {
            "session_id": str(session_id),
            "trace_id": trace_id,
            "workflow": "course_tutor",
            "artifact_type": "chat_message",
            "citation_count": citation_count,
            "used_model": used_model,
            "steps": COURSE_TUTOR_GRAPH_STEPS,
        }
        safe_context_metadata = TutorSessionService._safe_trace_context_metadata(context_metadata)
        if (
            safe_context_metadata.get("context_message_count")
            or safe_context_metadata.get("context_summary_used")
            or safe_context_metadata.get("retrieval_query_mode") == "contextual"
        ):
            data.update(safe_context_metadata)
        return {
            "event": event,
            "data": data,
        }

    def _collect_citations(
        self,
        user: User,
        session: ChatSession,
        message_text: str,
        retrieval_query: str,
        use_web_search: bool,
        selected_material_ids: list[int],
        warnings: list[str],
    ) -> list[dict[str, Any]]:
        if session.scope == "course":
            return self._search_course_citations(
                user=user,
                session=session,
                message_text=message_text,
                retrieval_query=retrieval_query,
            )

        citations: list[dict[str, Any]] = []
        citations.extend(self._home_material_citations(user=user, selected_material_ids=selected_material_ids))
        if use_web_search:
            citations.extend(self._web_search_citations(message_text=retrieval_query, warnings=warnings))
        return citations

    def _home_material_citations(self, user: User, selected_material_ids: list[int]) -> list[dict[str, Any]]:
        if not selected_material_ids:
            return []
        materials = self.repository.list_home_materials_for_user(user.id, selected_material_ids)
        by_id = {material.id: material for material in materials}
        citations: list[dict[str, Any]] = []
        for material_id in list(dict.fromkeys(selected_material_ids))[:10]:
            material = by_id.get(material_id)
            if material is None or not material.extracted_text:
                continue
            citations.append(
                {
                    "source_type": "material",
                    "material_id": str(material.id),
                    "title": material.filename,
                    "snippet": self._safe_snippet(material.extracted_text, limit=240),
                }
            )
        return citations

    def _web_search_citations(self, message_text: str, warnings: list[str]) -> list[dict[str, Any]]:
        if self.web_search_service is None:
            warnings.append("联网搜索未配置。")
            return []
        result = self.web_search_service.search(message_text, max_results=5)
        warning = getattr(result, "warning", None)
        if warning:
            warnings.append(str(warning))
        raw_citations = getattr(result, "citations", [])
        if not isinstance(raw_citations, list):
            return []
        citations: list[dict[str, Any]] = []
        for item in raw_citations[:5]:
            if not isinstance(item, dict):
                continue
            title = self._safe_snippet(str(item.get("title") or "联网来源"), 120)
            snippet = self._safe_snippet(str(item.get("snippet") or item.get("content") or ""), 240)
            url = self._safe_snippet(str(item.get("url") or ""), 300)
            citations.append(
                {
                    "source_type": "web",
                    "title": title,
                    "url": url,
                    "snippet": snippet,
                }
            )
        return citations

    def _search_course_citations(
        self,
        user: User,
        session: ChatSession,
        message_text: str,
        retrieval_query: str | None = None,
    ) -> list[dict[str, Any]]:
        if session.scope != "course" or session.course_id is None or self.course_citation_searcher is None:
            return []

        result = self.course_citation_searcher.search(
            user=user,
            course_id=session.course_id,
            query=retrieval_query or message_text,
            top_k=5,
        )
        return [self._citation_to_dict(item) for item in result.results]

    def _build_conversation_context(self, session: ChatSession) -> ConversationContext:
        history = [
            message
            for message in self.repository.list_messages(session.id)
            if message.role in {"user", "assistant"} and str(message.content or "").strip()
        ]
        if not history:
            return ConversationContext()

        older_messages = history[:-CONTEXT_RECENT_MESSAGE_LIMIT]
        recent_messages = history[-CONTEXT_RECENT_MESSAGE_LIMIT:]
        summary = self._summarize_older_messages(older_messages)
        remaining_budget = max(CONTEXT_TOTAL_CHAR_LIMIT - len(summary), 0)
        selected_messages: list[dict[str, str]] = []
        for message in reversed(recent_messages):
            if remaining_budget <= 0:
                break
            limit = min(CONTEXT_MESSAGE_CHAR_LIMIT, remaining_budget)
            content = self._safe_context_text(str(message.content or ""), limit=limit)
            if not content:
                continue
            selected_messages.append({"role": message.role, "content": content})
            remaining_budget -= len(content)

        selected_messages.reverse()
        return ConversationContext(
            summary=summary,
            messages=selected_messages,
            message_count=len(selected_messages),
            summary_used=bool(summary),
        )

    def _summarize_older_messages(self, messages: list[ChatMessage]) -> str:
        if not messages:
            return ""

        user_lines: list[str] = []
        assistant_lines: list[str] = []
        for message in messages:
            content = self._safe_context_text(str(message.content or ""), limit=220)
            if not content:
                continue
            if message.role == "user":
                user_lines.append(content)
            elif message.role == "assistant":
                assistant_lines.append(content)

        summary_parts: list[str] = []
        if user_lines:
            summary_parts.append(f"学生此前关注：{'；'.join(user_lines[-4:])}")
        if assistant_lines:
            summary_parts.append(f"已给建议：{'；'.join(assistant_lines[-3:])}")
        return self._safe_context_text("；".join(summary_parts), limit=CONTEXT_SUMMARY_CHAR_LIMIT)

    def _build_contextual_query(self, message_text: str, conversation_context: ConversationContext) -> str:
        previous_user_questions = [
            item["content"]
            for item in conversation_context.messages
            if item.get("role") == "user" and item.get("content")
        ][-CONTEXT_RETRIEVAL_USER_MESSAGE_LIMIT:]
        if not previous_user_questions:
            return message_text
        query = "\n".join([*previous_user_questions, message_text])
        return self._safe_query_text(query, limit=CONTEXT_MESSAGE_CHAR_LIMIT)

    @staticmethod
    def _context_metadata(
        conversation_context: ConversationContext,
        retrieval_query: str,
        message_text: str,
        retrieval_active: bool,
    ) -> dict[str, Any]:
        return {
            "context_message_count": conversation_context.message_count,
            "context_summary_used": conversation_context.summary_used,
            "retrieval_query_mode": "contextual" if retrieval_active and retrieval_query != message_text else "direct",
        }

    @staticmethod
    def _safe_trace_context_metadata(context_metadata: dict[str, Any] | None) -> dict[str, Any]:
        if not context_metadata:
            return {}
        return {
            "context_message_count": max(0, int(context_metadata.get("context_message_count") or 0)),
            "context_summary_used": bool(context_metadata.get("context_summary_used")),
            "retrieval_query_mode": "contextual"
            if context_metadata.get("retrieval_query_mode") == "contextual"
            else "direct",
        }

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
    def _safe_snippet(text: str, limit: int = 240) -> str:
        cleaned = " ".join(text.split())
        for marker in ("SECRET", "API Key", "系统提示词", "模型输入", "完整资料原文", "JWT"):
            if marker in cleaned:
                cleaned = cleaned.split(marker, 1)[0].strip()
        if len(cleaned) <= limit:
            return cleaned
        return f"{cleaned[:limit].rstrip()}..."

    @staticmethod
    def _safe_context_text(text: str, limit: int) -> str:
        cleaned = " ".join(text.split())
        for marker in ("SECRET", "API Key", "系统提示词", "模型输入", "完整资料原文", "JWT"):
            cleaned = cleaned.replace(marker, "")
        cleaned = " ".join(cleaned.split())
        if len(cleaned) <= limit:
            return cleaned
        if limit <= 3:
            return cleaned[:limit]
        return f"{cleaned[: limit - 3].rstrip()}..."

    @staticmethod
    def _safe_query_text(text: str, limit: int) -> str:
        lines: list[str] = []
        for raw_line in text.splitlines():
            cleaned = " ".join(raw_line.split())
            for marker in ("SECRET", "API Key", "系统提示词", "模型输入", "完整资料原文", "JWT"):
                cleaned = cleaned.replace(marker, "")
            cleaned = " ".join(cleaned.split())
            if cleaned:
                lines.append(cleaned)
        query = "\n".join(lines)
        if len(query) <= limit:
            return query
        if limit <= 3:
            return query[:limit]
        return f"{query[: limit - 3].rstrip()}..."

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


class CourseTutorGraphRunner:
    workflow = "course_tutor"
    artifact_type = "chat_message"

    def __init__(self, service: TutorSessionService) -> None:
        self.service = service
        self.graph = self._build_graph()

    def append(self, *, user: User, session: ChatSession, message_text: str) -> TutorSessionDetail:
        state = self._initial_state(user=user, session=session, message_text=message_text)
        result = self.graph.invoke(state)
        return self.service._persist_message_pair(
            user=user,
            session=session,
            message_text=message_text,
            assistant_reply=str(result.get("assistant_reply") or ""),
            citation_json=list(result.get("citation_json", [])),
            trace_id=str(result.get("trace_id") or ""),
            home_tool_metadata=None,
            context_metadata=result.get("context_metadata"),
            course_trace_records=list(result.get("pending_traces", [])),
        )

    def stream(self, *, user: User, session: ChatSession, message_text: str) -> Iterator[dict[str, Any]]:
        state = self._initial_state(user=user, session=session, message_text=message_text)
        try:
            state.update(self._profile_node(state))
            state.update(self._retriever_node(state))
            citation_json = list(state.get("citation_json", []))
            stream_state = self._prepare_stream_tutor_node(state)
            state.update(stream_state)
            trace_id = str(state.get("trace_id") or "")
            used_model = bool(state.get("used_model"))
            yield self.service._stream_event(
                "metadata",
                session_id=session.id,
                trace_id=trace_id,
                citation_count=len(citation_json),
                used_model=used_model,
                context_metadata=state.get("context_metadata"),
            )

            answer_parts: list[str] = []
            for token in state.get("tokens", []):
                if not isinstance(token, str) or not token:
                    continue
                answer_parts.append(token)
                yield {"event": "token", "data": {"content": token}}

            assistant_reply = "".join(answer_parts).strip()
            if not assistant_reply:
                raise CourseAnswerGenerationError("模型暂不可用，请检查设置或稍后重试。")
            state["assistant_reply"] = assistant_reply
            state.update(self._weakness_node(state))
            state.update(self._review_node(state))
            state.update(self._next_action_node(state))
            detail = self.service._persist_message_pair(
                user=user,
                session=session,
                message_text=message_text,
                assistant_reply=assistant_reply,
                citation_json=citation_json,
                trace_id=trace_id,
                home_tool_metadata=None,
                context_metadata=state.get("context_metadata"),
                course_trace_records=list(state.get("pending_traces", [])),
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

    def _build_graph(self):
        graph = StateGraph(AgentState)
        graph.add_node("profile", self._profile_node)
        graph.add_node("retriever", self._retriever_node)
        graph.add_node("tutor", self._tutor_node)
        graph.add_node("weakness", self._weakness_node)
        graph.add_node("review", self._review_node)
        graph.add_node("next_action", self._next_action_node)
        graph.add_edge(START, "profile")
        graph.add_edge("profile", "retriever")
        graph.add_edge("retriever", "tutor")
        graph.add_edge("tutor", "weakness")
        graph.add_edge("weakness", "review")
        graph.add_edge("review", "next_action")
        graph.add_edge("next_action", END)
        return graph.compile()

    def _initial_state(self, *, user: User, session: ChatSession, message_text: str) -> AgentState:
        conversation_context = self.service._build_conversation_context(session)
        retrieval_query = self.service._build_contextual_query(message_text, conversation_context)
        context_metadata = self.service._context_metadata(
            conversation_context,
            retrieval_query,
            message_text,
            retrieval_active=True,
        )
        return {
            "trace_id": make_trace_id(),
            "workflow": self.workflow,
            "artifact_type": self.artifact_type,
            "user_id": user.id,
            "course_id": session.course_id,
            "user": user,
            "session": session,
            "message_text": message_text,
            "conversation_context": conversation_context if conversation_context.has_context else None,
            "retrieval_query": retrieval_query,
            "context_metadata": context_metadata,
            "pending_traces": [],
            "warnings": [],
            "errors": [],
        }

    def _profile_node(self, state: AgentState) -> dict[str, Any]:
        return self._run_node(
            state,
            agent_name="profile",
            step_index=1,
            input_summary="读取学习画像与课程上下文",
            work=lambda: ({}, "已加载用户画像摘要。", "completed", {}),
        )

    def _retriever_node(self, state: AgentState) -> dict[str, Any]:
        def work() -> tuple[dict[str, Any], str, str, dict[str, Any]]:
            citations = self.service._search_course_citations(
                user=state["user"],
                session=state["session"],
                message_text=str(state["message_text"]),
                retrieval_query=str(state["retrieval_query"]),
            )
            return (
                {"citation_json": citations, "citations": citations},
                f"命中 {len(citations)} 条课程引用。",
                "completed",
                {"citation_count": len(citations), "source_count": len(citations)},
            )

        return self._run_node(
            state,
            agent_name="retriever",
            step_index=2,
            input_summary="检索当前课程知识切片",
            work=work,
        )

    def _tutor_node(self, state: AgentState) -> dict[str, Any]:
        def work() -> tuple[dict[str, Any], str, str, dict[str, Any]]:
            citations = list(state.get("citation_json", []))
            if not citations:
                return (
                    {
                        "assistant_reply": COURSE_ASSISTANT_REPLY_WITHOUT_CITATIONS,
                        "used_model": False,
                    },
                    "课程资料依据不足，已生成低依据提示。",
                    "warning",
                    {"citation_count": 0, "risk_flags": ["low_evidence"]},
                )
            if self.service.course_answer_generator is None:
                return (
                    {
                        "assistant_reply": COURSE_ASSISTANT_REPLY_MODEL_NOT_CONFIGURED,
                        "used_model": False,
                    },
                    "当前未配置课程回答模型，已返回清晰提示。",
                    "warning",
                    {"citation_count": len(citations), "risk_flags": ["model_not_configured"]},
                )
            answer = self.service.course_answer_generator.generate(
                user=state["user"],
                question=str(state["message_text"]),
                citations=citations,
                conversation_context=state.get("conversation_context"),
            )
            trace_id = getattr(answer, "trace_id", None) or state["trace_id"]
            return (
                {
                    "assistant_reply": str(getattr(answer, "content", "") or ""),
                    "trace_id": trace_id,
                    "used_model": getattr(answer, "trace_id", None) is not None,
                },
                "已生成带引用的课程回答。",
                "completed",
                {"citation_count": len(citations)},
            )

        return self._run_node(
            state,
            agent_name="tutor",
            step_index=3,
            input_summary="生成课程导师回答",
            work=work,
        )

    def _prepare_stream_tutor_node(self, state: AgentState) -> dict[str, Any]:
        def work() -> tuple[dict[str, Any], str, str, dict[str, Any]]:
            citations = list(state.get("citation_json", []))
            if not citations:
                return (
                    {
                        "tokens": [COURSE_ASSISTANT_REPLY_WITHOUT_CITATIONS],
                        "used_model": False,
                    },
                    "课程资料依据不足，已生成低依据提示。",
                    "warning",
                    {"citation_count": 0, "risk_flags": ["low_evidence"]},
                )
            if self.service.course_answer_generator is None:
                return (
                    {
                        "tokens": [COURSE_ASSISTANT_REPLY_MODEL_NOT_CONFIGURED],
                        "used_model": False,
                    },
                    "当前未配置课程回答模型，已返回清晰提示。",
                    "warning",
                    {"citation_count": len(citations), "risk_flags": ["model_not_configured"]},
                )
            stream_result = self.service.course_answer_generator.stream(
                user=state["user"],
                question=str(state["message_text"]),
                citations=citations,
                conversation_context=state.get("conversation_context"),
            )
            trace_id = getattr(stream_result, "trace_id", None) or state["trace_id"]
            return (
                {
                    "tokens": getattr(stream_result, "tokens"),
                    "trace_id": trace_id,
                    "used_model": bool(getattr(stream_result, "used_model", True)) and getattr(stream_result, "trace_id", None) is not None,
                },
                "已启动课程导师流式回答。",
                "completed",
                {"citation_count": len(citations)},
            )

        return self._run_node(
            state,
            agent_name="tutor",
            step_index=3,
            input_summary="生成课程导师回答",
            work=work,
        )

    def _weakness_node(self, state: AgentState) -> dict[str, Any]:
        citation_count = len(state.get("citation_json", []))
        output = "已同步课程问答弱点候选。" if citation_count else "依据不足，未生成新的弱点候选。"
        return self._run_node(
            state,
            agent_name="weakness",
            step_index=4,
            input_summary="识别弱点候选",
            work=lambda: ({}, output, "completed", {"citation_count": citation_count}),
        )

    def _review_node(self, state: AgentState) -> dict[str, Any]:
        citations = list(state.get("citation_json", []))
        used_model = bool(state.get("used_model"))
        risk_flags: list[str] = []
        if not citations:
            risk_flags.append("low_evidence")
        if citations and not used_model:
            risk_flags.append("model_not_configured")
        review_status = "warning" if risk_flags else "passed"
        metadata = {
            "review_status": review_status,
            "confidence": 0.82 if review_status == "passed" else 0.55,
            "risk_flags": risk_flags,
            "safety_summary": "已完成课程回答依据、隐私和下一步动作审核。",
            "citation_count": len(citations),
        }
        return self._run_node(
            state,
            agent_name="review",
            step_index=5,
            input_summary="审核回答依据与安全边界",
            work=lambda: ({"review_result": metadata}, f"ReviewAgent 审核结果：{review_status}", review_status, metadata),
        )

    def _next_action_node(self, state: AgentState) -> dict[str, Any]:
        citations = list(state.get("citation_json", []))
        output = "建议查看来源、生成资源或进入练习。" if citations else "建议补充课程资料或换一个与课程资料更贴近的问题。"
        return self._run_node(
            state,
            agent_name="next_action",
            step_index=6,
            input_summary="生成下一步学习动作",
            work=lambda: ({}, output, "completed", {"citation_count": len(citations)}),
        )

    def _run_node(
        self,
        state: AgentState,
        *,
        agent_name: str,
        step_index: int,
        input_summary: str,
        work,
    ) -> dict[str, Any]:
        started = perf_counter()
        try:
            updates, output_summary, status, metadata = work()
        except Exception as exc:
            duration_ms = max(1, int((perf_counter() - started) * 1000))
            failed = PendingAgentTrace(
                agent_name=agent_name,
                step_index=step_index,
                status="failed",
                input_summary=input_summary,
                output_summary="节点执行失败，已记录安全错误摘要。",
                duration_ms=duration_ms,
                metadata={
                    **self._base_metadata(state),
                    "error_code": exc.__class__.__name__,
                },
            )
            self._persist_failed_trace_records(state, failed)
            raise
        duration_ms = max(1, int((perf_counter() - started) * 1000))
        pending = PendingAgentTrace(
            agent_name=agent_name,
            step_index=step_index,
            status=status,
            input_summary=input_summary,
            output_summary=output_summary,
            duration_ms=duration_ms,
            metadata={**self._base_metadata(state), **metadata},
        )
        return {
            **updates,
            "pending_traces": [*list(state.get("pending_traces", [])), pending],
        }

    def _persist_failed_trace_records(self, state: AgentState, failed: PendingAgentTrace) -> None:
        user = state.get("user")
        session = state.get("session")
        trace_id = str(state.get("trace_id") or "")
        if not isinstance(user, User) or not isinstance(session, ChatSession) or not trace_id:
            return
        trace_records = [*list(state.get("pending_traces", [])), failed]
        try:
            for pending in trace_records:
                self.service.repository.add_agent_log(
                    agent_log_from_pending_trace(
                        pending=pending,
                        trace_id=trace_id,
                        user_id=user.id,
                        course_id=session.course_id,
                        workflow=self.workflow,
                        artifact_type=self.artifact_type,
                    )
                )
            self.service.repository.commit()
        except Exception:
            self.service.repository.rollback()

    def _base_metadata(self, state: AgentState) -> dict[str, Any]:
        return {
            "citation_count": len(state.get("citation_json", [])),
            **self.service._safe_trace_context_metadata(state.get("context_metadata")),
        }

from __future__ import annotations

import logging
from typing import Any


from backend.app.models import (
    ChatSession,
    User,
)
from backend.app.schemas.tutor import (
    TutorSessionDetail,
    TutorSessionHistoryItem,
    TutorSessionHistoryPage,
    TutorSessionSummary,
    session_to_summary,
)
from backend.app.providers.openai_compatible import ModelProviderError
from backend.app.services.tutor_contracts import (
    ConversationMemoryProvider,
    CourseAnswerGenerator,
    CourseCitationSearcher,
    EmptyMessageError,
    InvalidMaterialContextError as InvalidMaterialContextError,
    InvalidResourceContextError as InvalidResourceContextError,
    InvalidSessionScopeError,
    MaterialCitationSearcher,
    NativeWebSearchProvider,
    ProfileEventRecorder,
    SemanticDecisionProvider,
    SessionNotFoundError,
    TutorSessionRepository,
    WebSearchProvider,
)
from backend.app.services.tutor_context import TutorContextMixin
from backend.app.services.tutor_course_graph import (
    CourseTutorGraphRunner as CourseTutorGraphRunner,
)
from backend.app.services.tutor_home_graph import (
    HomeTutorGraphRunner as HomeTutorGraphRunner,
)
from backend.app.services.tutor_repository import (
    SqlAlchemyTutorSessionRepository as SqlAlchemyTutorSessionRepository,
)
from backend.app.services.tutor_resource_flow import TutorResourceFlowMixin
from backend.app.services.tutor_response_flow import TutorResponseFlowMixin
from backend.app.services.tutor_runtime import (
    COURSE_TUTOR_GRAPH_STEPS,
)
from backend.app.services.tutor_trace import TutorTraceMixin


logger = logging.getLogger(__name__)


class TutorSessionService(TutorResourceFlowMixin, TutorResponseFlowMixin, TutorTraceMixin, TutorContextMixin):
    def __init__(
        self,
        repository: TutorSessionRepository,
        course_citation_searcher: CourseCitationSearcher | None = None,
        course_answer_generator: CourseAnswerGenerator | None = None,
        profile_event_recorder: ProfileEventRecorder | None = None,
        web_search_service: WebSearchProvider | None = None,
        material_citation_searcher: MaterialCitationSearcher | None = None,
        semantic_decision_service: SemanticDecisionProvider | None = None,
        native_web_search_provider: NativeWebSearchProvider | None = None,
        conversation_memory_service: ConversationMemoryProvider | None = None,
        vision_understanding_service: Any | None = None,
    ) -> None:
        self.repository = repository
        self.course_citation_searcher = course_citation_searcher
        self.course_answer_generator = course_answer_generator
        self.profile_event_recorder = profile_event_recorder
        self.web_search_service = web_search_service
        self.material_citation_searcher = material_citation_searcher
        self.semantic_decision_service = semantic_decision_service
        self.native_web_search_provider = native_web_search_provider
        self.conversation_memory_service = conversation_memory_service
        self.vision_understanding_service = vision_understanding_service

    def create_session(
        self,
        user: User,
        scope: str,
        course_id: int | None,
        mode: str,
        title: str,
        selected_material_ids: list[int] | None = None,
    ) -> ChatSession:
        normalized_scope = self._normalize_scope(scope)
        normalized_course_id = self._normalize_course_id(user.id, normalized_scope, course_id)
        normalized_mode = self._normalize_mode(mode)
        normalized_title = title.strip() or "新的学习对话"
        material_ids = self._validate_material_context(user, normalized_scope, selected_material_ids or [])

        session = ChatSession(
            user_id=user.id,
            course_id=normalized_course_id,
            scope=normalized_scope,
            title=normalized_title[:255],
            mode=normalized_mode,
            archived_from_home=False,
            selected_material_ids=material_ids,
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

    def list_home_history(self, user: User, page: int, page_size: int, query: str = "") -> TutorSessionHistoryPage:
        normalized_query = " ".join(query.split())[:100]
        sessions, total = self.repository.list_home_history(user.id, page, page_size, normalized_query)
        items: list[TutorSessionHistoryItem] = []
        for session in sessions:
            summary = session_to_summary(session).model_dump()
            matched = self.repository.find_history_match(session.id, normalized_query) if normalized_query else None
            items.append(TutorSessionHistoryItem(**summary, match_snippet=self._history_snippet(matched, normalized_query)))
        return TutorSessionHistoryPage(
            items=items,
            page=page,
            page_size=page_size,
            total=total,
            has_more=page * page_size < total,
        )

    def get_session(self, user: User, session_id: int) -> TutorSessionDetail:
        session = self._get_session_for_user(user.id, session_id)
        return self._session_detail(session)

    def update_session(
        self,
        user: User,
        session_id: int,
        *,
        title: str | None = None,
        selected_material_ids: list[int] | None = None,
    ) -> TutorSessionSummary:
        session = self._get_session_for_user(user.id, session_id)
        if title is not None:
            normalized_title = title.strip()
            if not normalized_title:
                raise EmptyMessageError("会话名称不能为空。")
            session.title = normalized_title[:255]
        if selected_material_ids is not None:
            session.selected_material_ids = self._validate_material_context(user, session.scope, selected_material_ids)

        try:
            self.repository.touch_session(session)
            self.repository.flush()
            self.repository.commit()
        except Exception:
            self.repository.rollback()
            raise

        return session_to_summary(session)

    def rename_session(self, user: User, session_id: int, title: str) -> TutorSessionSummary:
        return self.update_session(user, session_id, title=title)

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

    @staticmethod
    def _safe_model_error(exc: Exception) -> dict[str, Any]:
        current: BaseException | None = exc
        provider_error: ModelProviderError | None = None
        while current is not None:
            if isinstance(current, ModelProviderError):
                provider_error = current
                break
            current = current.__cause__ or current.__context__
        code = provider_error.code if provider_error is not None else getattr(exc, "code", "MODEL_PROVIDER_ERROR")
        messages = {
            "not_configured": "当前未配置可用模型，请先检查模型设置。",
            "authentication_failed": "模型配置认证失败，请检查模型设置。",
            "context_too_long": "本次会话内容过长，请缩短问题或新建会话。",
            "rate_limited": "模型服务请求较多，请稍后重试。",
            "model_busy": "当前模型请求较多，请稍后重试。",
            "circuit_open": "模型服务正在恢复，请稍后重试。",
            "timeout": "模型响应超时，请稍后重试。",
            "stream_interrupted": "模型输出中断，本次回答未保存，可重新发送。",
            "invalid_request": "模型服务无法处理本次请求。",
            "invalid_response": "模型返回格式异常，请稍后重试。",
            "network_error": "暂时无法连接模型服务，请稍后重试。",
            "provider_unavailable": "模型暂不可用，请检查设置或稍后重试。",
        }
        data: dict[str, Any] = {
            "code": str(code),
            "message": messages.get(str(code), messages["provider_unavailable"]),
            "retryable": bool(provider_error.retryable) if provider_error is not None else str(code) not in {"not_configured", "authentication_failed", "invalid_request", "context_too_long"},
        }
        retry_after = provider_error.retry_after_seconds if provider_error is not None else None
        if retry_after is not None:
            data["retry_after_seconds"] = max(0.0, min(float(retry_after), 3.0))
        return data

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
            or safe_context_metadata.get("resource_context_used")
        ):
            data.update(safe_context_metadata)
        return {
            "event": event,
            "data": data,
        }

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

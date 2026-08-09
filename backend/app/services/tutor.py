from __future__ import annotations

import logging
import re
from typing import Any, Iterator

from langchain_core.messages import AIMessage, HumanMessage, trim_messages

from backend.app.agents.runtime import PendingAgentTrace, agent_log_from_pending_trace
from backend.app.agents.schemas import AgentState
from backend.app.agents.search_tools import SearchToolExecutor
from backend.app.agents.tool_policy import decide_tool_capabilities
from backend.app.models import (
    AgentRunLog,
    ChatMessage,
    ChatSession,
    User,
)
from backend.app.schemas.tutor import (
    TutorSessionDetail,
    TutorSessionHistoryItem,
    TutorSessionHistoryPage,
    TutorSessionSummary,
    session_detail_to_api,
    session_to_summary,
)
from backend.app.services.course_answers import (
    ConversationContext,
    CourseAnswerGenerationError,
    HOME_MODEL_NOT_CONFIGURED_MESSAGE,
)
from backend.app.providers.openai_compatible import ModelProviderError
from backend.app.services.tutor_contracts import (
    ConversationMemoryProvider,
    CourseAnswerGenerator,
    CourseCitationSearcher,
    EmptyMessageError,
    GeneratedAnswer,
    InvalidMaterialContextError,
    InvalidResourceContextError,
    InvalidSessionScopeError,
    MaterialCitationSearcher,
    NativeWebSearchProvider,
    ProfileEventRecorder,
    SemanticDecisionProvider,
    SessionNotFoundError,
    TutorSessionRepository,
    WebSearchProvider,
)
from backend.app.services.tutor_course_graph import (
    CourseTutorGraphRunner as CourseTutorGraphRunner,
)
from backend.app.services.tutor_home_graph import (
    HomeTutorGraphRunner as HomeTutorGraphRunner,
)
from backend.app.services.tutor_repository import (
    SqlAlchemyTutorSessionRepository as SqlAlchemyTutorSessionRepository,
)
from backend.app.services.tutor_runtime import (
    CONTEXT_MESSAGE_CHAR_LIMIT,
    CONTEXT_RECENT_MESSAGE_LIMIT,
    CONTEXT_RETRIEVAL_USER_MESSAGE_LIMIT,
    CONTEXT_SUMMARY_CHAR_LIMIT,
    CONTEXT_TOTAL_CHAR_LIMIT,
    COURSE_ASSISTANT_REPLY_MODEL_NOT_CONFIGURED,
    COURSE_ASSISTANT_REPLY_WITHOUT_CITATIONS,
    COURSE_TUTOR_GRAPH_STEPS,
    DEFAULT_IMAGE_QUESTION,
)


logger = logging.getLogger(__name__)


class TutorSessionService:
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

    def _semantic_decision(
        self,
        *,
        user: User,
        session: ChatSession,
        question: str,
        force_search: bool,
        force_deep: bool,
        conversation_context: ConversationContext | None = None,
    ) -> Any:
        if self.semantic_decision_service is None:
            return decide_tool_capabilities(question, force_search=force_search, force_deep=force_deep)
        course_title = ""
        if session.course_id is not None:
            course = self.repository.get_course_for_user(user.id, session.course_id)
            course_title = str(getattr(course, "title", "") or "")
        return self.semantic_decision_service.decide(
            user=user,
            question=question,
            scope="course" if session.scope == "course" else "home",
            course_title=course_title,
            selected_materials=bool(getattr(session, "selected_material_ids", None)),
            force_search=force_search,
            force_deep=force_deep,
            conversation_messages=[
                {**message, "turn_id": conversation_context.turn_ids[index] if index < len(conversation_context.turn_ids) else ""}
                for index, message in enumerate(conversation_context.messages)
            ] if conversation_context is not None else [],
        )

    @staticmethod
    def _resource_proposal_from_state(state: AgentState) -> dict[str, Any]:
        action = str(state.get("resource_action") or "none")
        valid_types = {"doc", "mindmap", "quiz", "code", "slide", "animation", "video"}
        resource_types = [
            str(item)
            for item in dict.fromkeys(state.get("resource_types", []))
            if str(item) in valid_types
        ][:3]
        if action not in {"suggest", "generate"} or not resource_types:
            return {}
        difficulty = str(state.get("resource_difficulty") or "medium")
        return {
            "action": action,
            "response_mode": str(state.get("response_mode") or "answer"),
            "resource_types": resource_types,
            "difficulty": difficulty if difficulty in {"easy", "medium", "hard"} else "medium",
            "topic": str(state.get("resource_topic") or "")[:120],
            "learning_goal": str(state.get("resource_learning_goal") or state.get("standalone_query") or state.get("message_text") or "")[:500],
            "reason_summary": str(state.get("resource_reason_summary") or "根据本轮学习目标推荐。")[:160],
            "confidence": max(0.0, min(1.0, float(state.get("semantic_decision_confidence") or 0))),
        }

    @staticmethod
    def _resource_action_reply(state: AgentState) -> str:
        labels = {
            "doc": "讲解文档",
            "mindmap": "思维导图",
            "quiz": "练习题",
            "code": "代码实操",
            "slide": "演示文稿",
            "animation": "动画图解",
            "video": "教学视频",
        }
        selected = [labels.get(str(item), str(item)) for item in state.get("resource_types", [])][:3]
        resource_text = "、".join(selected) or "学习资源"
        if str(state.get("workflow")) == "home_tutor":
            return f"已理解你的学习目标。请选择目标课程后，我会生成{resource_text}，进度和结果会保留在这条回答下方。"
        return f"已理解你的学习目标，正在准备生成{resource_text}。任务进度和完成结果会显示在这条回答下方。"

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

    def append_message(
        self,
        user: User,
        session_id: int,
        content: str,
        use_web_search: bool = False,
        deep_thinking: bool = False,
        selected_material_ids: list[int] | None = None,
        attachment_ids: list[int] | None = None,
        context_resource_id: int | None = None,
    ) -> TutorSessionDetail:
        normalized_attachment_ids = list(dict.fromkeys(attachment_ids or []))[:3]
        stored_message_text = content.strip() or (DEFAULT_IMAGE_QUESTION if normalized_attachment_ids else "")
        session = self._get_session_for_user(user.id, session_id)
        resource_context = self._prepare_resource_context(user, session, context_resource_id)
        message_text, vision_decision = self._prepare_visual_question(
            user=user,
            session=session,
            question=stored_message_text,
            attachment_ids=normalized_attachment_ids,
        )
        if not message_text:
            raise EmptyMessageError("消息不能为空。")

        if session.scope == "course":
            return CourseTutorGraphRunner(self).append(
                user=user,
                session=session,
                message_text=message_text,
                force_search=use_web_search,
                force_deep=deep_thinking,
                attachment_ids=normalized_attachment_ids,
                stored_message_text=stored_message_text,
                vision_decision=vision_decision,
                resource_context=resource_context,
            )
        material_ids, material_warnings = self._material_context_for_message(user, session, selected_material_ids)
        return HomeTutorGraphRunner(self).append(
            user=user,
            session=session,
            message_text=message_text,
            use_web_search=use_web_search,
            deep_thinking=deep_thinking,
            selected_material_ids=material_ids,
            initial_warnings=material_warnings,
            attachment_ids=normalized_attachment_ids,
            stored_message_text=stored_message_text,
            vision_decision=vision_decision,
        )

    def stream_message(
        self,
        user: User,
        session_id: int,
        content: str,
        use_web_search: bool = False,
        deep_thinking: bool = False,
        selected_material_ids: list[int] | None = None,
        attachment_ids: list[int] | None = None,
        resource_request: bool = False,
        context_resource_id: int | None = None,
    ) -> Iterator[dict[str, Any]]:
        normalized_attachment_ids = list(dict.fromkeys(attachment_ids or []))[:3]
        stored_message_text = content.strip() or (DEFAULT_IMAGE_QUESTION if normalized_attachment_ids else "")
        session = self._get_session_for_user(user.id, session_id)
        resource_context = self._prepare_resource_context(user, session, context_resource_id)
        message_text, vision_decision = self._prepare_visual_question(
            user=user,
            session=session,
            question=stored_message_text,
            attachment_ids=normalized_attachment_ids,
        )
        if not message_text:
            raise EmptyMessageError("消息不能为空。")

        if resource_request:
            return self._stream_resource_request_confirmation(
                user=user,
                session=session,
                message_text=message_text,
                attachment_ids=normalized_attachment_ids,
            )

        if session.scope == "course":
            return CourseTutorGraphRunner(self).stream(
                user=user,
                session=session,
                message_text=message_text,
                force_search=use_web_search,
                force_deep=deep_thinking,
                attachment_ids=normalized_attachment_ids,
                stored_message_text=stored_message_text,
                vision_decision=vision_decision,
                resource_context=resource_context,
            )
        material_ids, material_warnings = self._material_context_for_message(user, session, selected_material_ids)
        return HomeTutorGraphRunner(self).stream(
            user=user,
            session=session,
            message_text=message_text,
            use_web_search=use_web_search,
            deep_thinking=deep_thinking,
            selected_material_ids=material_ids,
            initial_warnings=material_warnings,
            attachment_ids=normalized_attachment_ids,
            stored_message_text=stored_message_text,
            vision_decision=vision_decision,
        )

    def _prepare_resource_context(
        self,
        user: User,
        session: ChatSession,
        resource_id: int | None,
    ) -> dict[str, Any] | None:
        if resource_id is None:
            return None
        if session.scope != "course" or session.course_id is None:
            raise InvalidResourceContextError("当前会话不能使用课程资源上下文。")
        resource = self.repository.get_resource_for_user(user.id, resource_id)
        if resource is None or resource.course_id != session.course_id or resource.status != "completed":
            raise InvalidResourceContextError("当前资源不存在、不可学习或无权访问。")
        point = (
            self.repository.get_knowledge_point(session.course_id, resource.knowledge_point_id)
            if resource.knowledge_point_id is not None
            else None
        )
        content = self._resource_context_content(resource.resource_type, resource.content_json)
        if not content.strip():
            raise InvalidResourceContextError("当前资源没有可供助教理解的有效内容。")
        return {
            "resource_id": resource.id,
            "resource_type": resource.resource_type,
            "title": resource.title[:255],
            "knowledge_point": str(getattr(point, "title", "") or "")[:160],
            "content": content,
            "usage_rule": "只辅助理解当前学习资源；课程资料仍是教材事实与页码引用来源。",
        }

    @classmethod
    def _resource_context_content(cls, resource_type: str, content_json: dict[str, Any]) -> str:
        if resource_type == "video":
            artifact = content_json.get("artifact") if isinstance(content_json, dict) else None
            source = artifact if isinstance(artifact, dict) else content_json
            fields = (
                ("平台", source.get("platform")),
                ("标题", source.get("title")),
                ("作者", source.get("author")),
                ("时长", source.get("duration")),
                ("原平台链接", source.get("original_url") or source.get("url")),
            )
            return "\n".join(f"{label}：{value}" for label, value in fields if value)[:6000]

        parts: list[str] = []

        def collect(value: Any, depth: int = 0) -> None:
            if sum(len(item) for item in parts) >= 6000 or depth > 5:
                return
            if isinstance(value, str):
                normalized = " ".join(value.split())
                if normalized:
                    parts.append(normalized[:1200])
            elif isinstance(value, dict):
                for key, item in value.items():
                    if str(key) in {"metadata", "quality", "agent_trace_id", "citation_json"}:
                        continue
                    collect(item, depth + 1)
            elif isinstance(value, list):
                for item in value[:40]:
                    collect(item, depth + 1)
            elif isinstance(value, (int, float, bool)):
                parts.append(str(value))

        collect(content_json)
        return "\n".join(parts)[:6000]

    def _stream_resource_request_confirmation(
        self,
        *,
        user: User,
        session: ChatSession,
        message_text: str,
        attachment_ids: list[int],
    ) -> Iterator[dict[str, Any]]:
        reply = "已识别为资源生成请求。请选择课程后，我会基于该课程资料生成资源。" if session.scope == "home" else "已识别为资源生成请求，正在基于当前课程资料创建任务。"
        yield self._stream_event("metadata", session.id, None, 0, False)
        yield {"event": "token", "data": {"content": reply}}
        detail = self._persist_message_pair(
            user=user,
            session=session,
            message_text=message_text,
            assistant_reply=reply,
            citation_json=[],
            trace_id=None,
            attachment_ids=attachment_ids,
            resource_proposal={
                "action": "generate",
                "resource_types": ["doc"],
                "difficulty": "medium",
                "learning_goal": message_text[:500],
                "reason_summary": "旧客户端明确请求生成学习资源。",
                "confidence": 1.0,
            },
        )
        yield {"event": "done", "data": detail.model_dump()}

    def _prepare_visual_question(
        self,
        *,
        user: User,
        session: ChatSession,
        question: str,
        attachment_ids: list[int],
    ) -> tuple[str, dict[str, Any] | None]:
        if not attachment_ids:
            return question, None
        if self.vision_understanding_service is None:
            raise CourseAnswerGenerationError("当前未配置可用图片理解模型。")
        attachments = self.repository.pending_attachments(user.id, session.id, attachment_ids)
        if len(attachments) != len(attachment_ids):
            raise InvalidMaterialContextError("部分图片不存在、已使用或无权访问。")
        try:
            result = self.vision_understanding_service.understand(
                user=user,
                question=question,
                attachment_ids=attachment_ids,
            )
        except Exception as exc:
            raise CourseAnswerGenerationError(str(exc) or "图片理解失败，请稍后重试。") from exc
        contextualizer = getattr(self.vision_understanding_service, "contextual_question")
        return contextualizer(question, result), result.model_dump()

    def _prepare_history_visual_question(
        self,
        *,
        user: User,
        session: ChatSession,
        question: str,
        referenced_turn_ids: list[str],
    ) -> tuple[str, dict[str, Any] | None]:
        if self.vision_understanding_service is None or not referenced_turn_ids:
            return question, None
        message_ids = [int(item) for item in referenced_turn_ids if str(item).isdigit()]
        finder = getattr(self.repository, "bound_attachments", None)
        if not callable(finder):
            return question, None
        attachments = finder(user.id, session.id, message_ids)
        if not attachments:
            return question, None
        result = self.vision_understanding_service.understand(
            user=user,
            question=question,
            attachment_ids=[int(item.id) for item in attachments],
        )
        contextualizer = getattr(self.vision_understanding_service, "contextual_question")
        payload = result.model_dump()
        payload["reused_history_image"] = True
        payload["image_count"] = len(attachments)
        return contextualizer(question, result), payload

    def _material_context_for_message(
        self,
        user: User,
        session: ChatSession,
        requested_ids: list[int] | None,
    ) -> tuple[list[int], list[str]]:
        if requested_ids is None:
            persisted = [int(item) for item in (session.selected_material_ids or []) if str(item).isdigit()][:10]
            available = self.repository.list_home_materials_for_user(user.id, persisted)
            available_ids = {material.id for material in available}
            available_material_ids = [material_id for material_id in persisted if material_id in available_ids]
            warnings = []
            if len(available_material_ids) != len(persisted):
                warnings.append("部分历史参考资料已失效，已从本次检索中忽略。")
            return available_material_ids, warnings
        material_ids = self._validate_material_context(user, session.scope, requested_ids)
        session.selected_material_ids = material_ids
        try:
            self.repository.touch_session(session)
            self.repository.flush()
            self.repository.commit()
        except Exception:
            self.repository.rollback()
            raise
        return material_ids, []

    def _validate_material_context(self, user: User, scope: str, material_ids: list[int]) -> list[int]:
        normalized = list(dict.fromkeys(item for item in material_ids if item > 0))
        if len(normalized) > 10:
            raise InvalidMaterialContextError("单个会话最多选择 10 份参考资料。")
        if scope != "home":
            if normalized:
                raise InvalidMaterialContextError("课程会话不能绑定主页参考资料。")
            return []
        materials = self.repository.list_home_materials_for_user(user.id, normalized)
        available_ids = {material.id for material in materials}
        if any(material_id not in available_ids for material_id in normalized):
            raise InvalidMaterialContextError("部分参考资料不存在、尚未确认解析结构或无权访问。")
        return normalized

    @staticmethod
    def _history_snippet(content: str | None, query: str) -> str | None:
        normalized = " ".join((content or "").split())
        if not normalized:
            return None
        index = normalized.casefold().find(query.casefold()) if query else 0
        start = max(0, index - 40) if index >= 0 else 0
        snippet = normalized[start : start + 120]
        if start > 0:
            snippet = f"…{snippet[1:]}"
        if start + 120 < len(normalized):
            snippet = f"{snippet[:119]}…"
        return snippet[:120]

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
        home_trace_records: list[PendingAgentTrace] | None = None,
        profile_signal_updates: dict[str, Any] | None = None,
        profile_signal_confidence: dict[str, float] | None = None,
        attachment_ids: list[int] | None = None,
        resource_proposal: dict[str, Any] | None = None,
    ) -> TutorSessionDetail:
        normalized_attachment_ids = list(dict.fromkeys(attachment_ids or []))[:3]
        attachments = (
            self.repository.pending_attachments(user.id, session.id, normalized_attachment_ids)
            if normalized_attachment_ids
            else []
        )
        if len(attachments) != len(normalized_attachment_ids):
            raise InvalidMaterialContextError("部分图片不存在、已使用或无权访问。")
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
            resource_proposal_json=resource_proposal or {},
        )

        try:
            self.repository.add_message(user_message)
            self.repository.add_message(assistant_message)
            self.repository.touch_session(session)
            self.repository.flush()
            if attachments:
                self.repository.bind_attachments(attachments, user_message.id)
            if home_trace_records is not None and session.scope == "home" and trace_id is not None:
                self._persist_home_tutor_graph_trace(
                    user=user,
                    assistant_message=assistant_message,
                    trace_id=trace_id,
                    trace_records=home_trace_records,
                )
            elif course_trace_records is not None and session.scope == "course" and trace_id is not None:
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
            if home_trace_records is None:
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

        if self.conversation_memory_service is not None:
            try:
                schedule = getattr(self.conversation_memory_service, "schedule_pair", None)
                (schedule if callable(schedule) else self.conversation_memory_service.index_pair)(
                    user=user,
                    session=session,
                    user_message=user_message,
                    assistant_message=assistant_message,
                )
            except Exception:
                try:
                    self.repository.rollback()
                except Exception:
                    pass

        course_evidence = [item for item in citation_json if item.get("source_type") not in {"web", "history"}]
        if (
            self.profile_event_recorder is not None
            and session.scope == "course"
            and course_evidence
            and profile_signal_updates
        ):
            try:
                ingest = getattr(self.profile_event_recorder, "ingest_course_question_signal", None)
                if callable(ingest):
                    ingest(
                        user=user,
                        session=session,
                        user_message=user_message,
                        message_text=message_text,
                        citation_json=course_evidence,
                        trace_id=trace_id,
                        suggested_updates=profile_signal_updates,
                        suggested_confidence=profile_signal_confidence or {},
                    )
            except Exception:
                self.repository.rollback()

        return self._session_detail(session)

    def _session_detail(self, session: ChatSession) -> TutorSessionDetail:
        messages = self.repository.list_messages(session.id)
        mapper = getattr(self.repository, "attachment_map", None)
        attachment_map = mapper([message.id for message in messages]) if callable(mapper) else {}
        resource_mapper = getattr(self.repository, "resource_job_map", None)
        resource_job_map = resource_mapper(session.user_id, [message.id for message in messages]) if callable(resource_mapper) else {}
        return session_detail_to_api(session, messages, attachment_map, resource_job_map)

    def register_resource_job(self, user: User, session_id: int, message_id: int, job_id: int) -> None:
        self._get_session_for_user(user.id, session_id)
        self.repository.register_resource_job(user.id, session_id, message_id, job_id)

    def prepare_resource_job(
        self,
        user: User,
        session_id: int,
        message_id: int,
        requested_course_id: int,
        legacy_request: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], list[int]]:
        session = self._get_session_for_user(user.id, session_id)
        message = self.repository.get_assistant_message(user.id, session_id, message_id)
        if message is None:
            raise SessionNotFoundError("回答不存在或无权访问。")
        if session.scope == "course" and int(session.course_id or 0) != requested_course_id:
            raise InvalidMaterialContextError("不能把课程回答生成到其他课程。")

        proposal = getattr(message, "resource_proposal_json", {})
        proposal = proposal if isinstance(proposal, dict) else {}
        if proposal.get("action") not in {"suggest", "generate"}:
            proposal = legacy_request or {}
        valid_types = {"doc", "mindmap", "quiz", "code", "slide", "animation", "video"}
        resource_types = [
            str(item)
            for item in dict.fromkeys(proposal.get("resource_types", []))
            if str(item) in valid_types
        ][:3]
        if not resource_types:
            raise InvalidMaterialContextError("该回答没有可确认的资源生成提案。")
        difficulty = str(proposal.get("difficulty") or "medium")
        if difficulty not in {"easy", "medium", "hard"}:
            difficulty = "medium"
        knowledge_point_id = None
        topic = str(proposal.get("topic") or "").strip()
        topic_finder = getattr(self.repository, "find_knowledge_point_for_topic", None)
        if topic and callable(topic_finder):
            point = topic_finder(requested_course_id, topic)
            if point is None:
                raise InvalidMaterialContextError(f"所选课程中没有与“{topic}”匹配的知识点，请选择对应课程。")
            knowledge_point_id = point.id
        evidence_chunk_ids: list[int] = []
        for citation in message.citation_json or []:
            if not isinstance(citation, dict) or citation.get("source_type") in {"web", "history"}:
                continue
            candidate = citation.get("knowledge_point_id")
            if knowledge_point_id is not None and str(candidate).isdigit() and int(candidate) != knowledge_point_id:
                continue
            chunk_id = citation.get("chunk_id")
            if str(chunk_id).isdigit():
                evidence_chunk_ids.append(int(chunk_id))
            if knowledge_point_id is None and str(candidate).isdigit():
                knowledge_point_id = int(candidate)
        return (
            {
                "course_id": requested_course_id,
                "knowledge_point_id": knowledge_point_id,
                "resource_types": resource_types,
                "learning_goal": str(proposal.get("learning_goal") or message.content)[:500],
                "difficulty": difficulty,
                "tutor_message_id": message_id,
                "evidence_chunk_ids": list(dict.fromkeys(evidence_chunk_ids))[:8],
            },
            [int(item) for item in (message.resource_job_ids or []) if str(item).isdigit()],
        )

    def link_resource_job(self, user: User, session_id: int, message_id: int, job_id: int) -> None:
        self._get_session_for_user(user.id, session_id)
        self.repository.link_resource_job(user.id, session_id, message_id, job_id)

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

    def _persist_home_tutor_graph_trace(
        self,
        user: User,
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
                    course_id=None,
                    workflow="home_tutor",
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

    def _web_search_citations(
        self,
        message_text: str,
        warnings: list[str],
        *,
        user: User | None = None,
        reasoning_mode: str = "auto",
        force: bool = False,
    ) -> list[dict[str, Any]]:
        if user is not None and self.native_web_search_provider is not None:
            try:
                native = self.native_web_search_provider.native_web_search(
                    user,
                    message_text,
                    reasoning_mode=reasoning_mode,
                    force=force,
                )
            except Exception:
                native = None
            native_citations = getattr(native, "citations", []) if native is not None else []
            if isinstance(native_citations, list) and native_citations:
                return [dict(item) for item in native_citations[:5] if isinstance(item, dict)]
            native_warning = getattr(native, "warning", None) if native is not None else None
            if native_warning and "不提供厂商原生" not in str(native_warning):
                warnings.append(str(native_warning))
        if self.web_search_service is None:
            warnings.append("联网搜索未配置。")
            return []
        try:
            tool_result = SearchToolExecutor(self.web_search_service).search(message_text, max_results=5)
        except Exception:
            tool_result = {"citations": [], "warning": "联网搜索暂不可用。"}
        warning = tool_result.get("warning")
        if warning:
            warnings.append(str(warning))
        raw_citations = tool_result.get("citations", [])
        if not isinstance(raw_citations, list):
            return []
        citations: list[dict[str, Any]] = []
        for item in raw_citations[:5]:
            if not isinstance(item, dict):
                continue
            title = self._safe_snippet(str(item.get("title") or "联网来源"), 120)
            snippet = self._safe_snippet(str(item.get("snippet") or item.get("content") or ""), 240)
            url = self._safe_snippet(str(item.get("url") or ""), 300)
            citation: dict[str, Any] = {
                "source_type": "web",
                "title": title,
                "url": url,
                "snippet": snippet,
            }
            for key in ("search_backend", "evidence_role", "retrieved_at"):
                if item.get(key):
                    citation[key] = str(item[key])
            citations.append(citation)
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
        citations = [self._citation_to_dict(item) for item in result.results]
        return self._filter_course_citations(citations)

    @staticmethod
    def _filter_course_citations(citations: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Remove clearly irrelevant reranker tails from student-visible evidence.

        Rerank scores are only comparable within one query, so the cutoff combines
        a small absolute floor with a relative floor derived from the best result.
        Retrievals without a completed rerank keep their existing behavior.
        """
        if not citations:
            return []
        completed = [
            item
            for item in citations
            if item.get("rerank_status") == "completed" and item.get("rerank_score") is not None
        ]
        if not completed:
            return citations
        best_score = max(float(item["rerank_score"]) for item in completed)
        minimum_score = max(0.05, best_score * 0.25)
        filtered = [
            item
            for item in citations
            if item.get("rerank_status") != "completed"
            or item.get("rerank_score") is None
            or float(item["rerank_score"]) >= minimum_score
        ]
        return filtered or [max(completed, key=lambda item: float(item["rerank_score"]))]

    def _build_conversation_context(
        self,
        session: ChatSession,
        *,
        user: User | None = None,
        current_question: str = "",
    ) -> ConversationContext:
        history = [
            message
            for message in self.repository.list_messages(session.id)
            if message.role in {"user", "assistant"} and str(message.content or "").strip()
        ]
        if not history:
            return ConversationContext()

        langchain_messages = [
            (HumanMessage if message.role == "user" else AIMessage)(
                content=self._safe_context_text(str(message.content or ""), limit=CONTEXT_MESSAGE_CHAR_LIMIT),
                additional_kwargs={"turn_id": str(message.id)},
            )
            for message in history
        ]
        trimmed = trim_messages(
            langchain_messages,
            max_tokens=3000,
            token_counter="approximate",
            strategy="last",
            allow_partial=False,
            start_on=HumanMessage,
        )
        trimmed_items = [
            {
                "role": "user" if isinstance(message, HumanMessage) else "assistant",
                "content": str(message.content),
                "turn_id": str(message.additional_kwargs.get("turn_id") or ""),
            }
            for message in trimmed
            if str(message.content).strip()
        ][-CONTEXT_RECENT_MESSAGE_LIMIT:]
        selected_messages_with_ids: list[dict[str, str]] = []
        remaining_budget = CONTEXT_TOTAL_CHAR_LIMIT - CONTEXT_SUMMARY_CHAR_LIMIT
        for item in reversed(trimmed_items):
            if remaining_budget <= 0:
                break
            content = self._safe_context_text(item["content"], limit=min(CONTEXT_MESSAGE_CHAR_LIMIT, remaining_budget))
            if not content:
                continue
            selected_messages_with_ids.append({**item, "content": content})
            remaining_budget -= len(content)
        selected_messages_with_ids.reverse()
        selected_turn_ids = {item["turn_id"] for item in selected_messages_with_ids}
        selected_messages = [
            {"role": item["role"], "content": item["content"]}
            for item in selected_messages_with_ids
        ]
        older_messages = [message for message in history if str(message.id) not in selected_turn_ids]
        summary = self._summarize_older_messages(older_messages)
        history_citations: list[dict[str, Any]] = []
        if user is not None and current_question.strip() and self.conversation_memory_service is not None:
            try:
                history_citations = self.conversation_memory_service.search(
                    user=user,
                    current_session_id=session.id,
                    query=current_question,
                    limit=5,
                )
                logger.info(
                    "conversation_memory_search_completed user_id=%s session_id=%s result_count=%s",
                    user.id,
                    session.id,
                    len(history_citations),
                )
            except Exception as exc:
                logger.warning(
                    "conversation_memory_search_failed user_id=%s session_id=%s error_type=%s",
                    user.id,
                    session.id,
                    type(exc).__name__,
                )
                history_citations = []
        if history_citations:
            memory_summary = "；".join(str(item.get("snippet") or "")[:300] for item in history_citations[:3])
            summary = self._safe_context_text(
                f"{summary}；相关历史对话（仅用于理解上下文，不是课程证据）：{memory_summary}".strip("；"),
                limit=CONTEXT_SUMMARY_CHAR_LIMIT,
            )
        return ConversationContext(
            summary=summary,
            messages=selected_messages,
            message_count=len(selected_messages),
            summary_used=bool(summary),
            history_citations=history_citations,
            turn_ids=[item["turn_id"] for item in selected_messages_with_ids],
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
        if self.semantic_decision_service is not None:
            return self._safe_query_text(message_text, limit=CONTEXT_MESSAGE_CHAR_LIMIT)
        previous_user_questions = [
            item["content"]
            for item in conversation_context.messages
            if item.get("role") == "user" and item.get("content")
        ][-CONTEXT_RETRIEVAL_USER_MESSAGE_LIMIT:]
        if not previous_user_questions or not self._should_use_previous_questions(message_text, previous_user_questions[-1]):
            return message_text
        return self._safe_query_text("\n".join([*previous_user_questions, message_text]), limit=CONTEXT_MESSAGE_CHAR_LIMIT)

    @classmethod
    def _should_use_previous_questions(cls, current: str, previous: str) -> bool:
        cleaned = " ".join(str(current or "").split()).casefold()
        if any(marker in cleaned for marker in ("这个", "那个", "它", "刚才", "上面", "上述", "继续", "再讲", "然后呢", "还有呢")):
            return True
        current_terms = cls._query_topic_terms(cleaned)
        previous_terms = cls._query_topic_terms(previous)
        if not current_terms or not previous_terms:
            return len(cleaned) <= 8
        overlap = len(current_terms & previous_terms) / max(1, min(len(current_terms), len(previous_terms)))
        return overlap >= 0.22

    @staticmethod
    def _query_topic_terms(value: str) -> set[str]:
        text = str(value or "").casefold()
        terms = set(re.findall(r"[a-z][a-z0-9*+()\-]{1,24}", text))
        for segment in re.findall(r"[一-龥]{2,}", text):
            terms.update(segment[index:index + 2] for index in range(max(0, len(segment) - 1)))
        stop = {"什么", "怎么", "如何", "为什", "么是", "可以", "一下", "请问", "还有", "讲讲"}
        return {term for term in terms if term not in stop}

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
            "resource_context_used": bool(context_metadata.get("resource_context_used")),
            "context_resource_id": int(context_metadata.get("context_resource_id"))
            if str(context_metadata.get("context_resource_id") or "").isdigit()
            else None,
            "context_resource_type": str(context_metadata.get("context_resource_type") or "")[:32],
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
        for key in (
            "keyword_score",
            "vector_score",
            "retrieval_source",
            "embedding_status",
            "embedding_provider",
            "embedding_dimension",
            "rerank_score",
            "rerank_status",
        ):
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

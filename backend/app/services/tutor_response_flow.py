from __future__ import annotations

import logging
from typing import Any, Iterator


from backend.app.agents.runtime import PendingAgentTrace
from backend.app.models import (
    ChatMessage,
    ChatSession,
    User,
)
from backend.app.schemas.tutor import (
    TutorSessionDetail,
    session_detail_to_api,
)
from backend.app.services.course_answers import (
    ConversationContext,
    CourseAnswerGenerationError,
    HOME_MODEL_NOT_CONFIGURED_MESSAGE,
)
from backend.app.services.tutor_contracts import (
    EmptyMessageError,
    GeneratedAnswer,
    InvalidMaterialContextError,
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
    COURSE_ASSISTANT_REPLY_MODEL_NOT_CONFIGURED,
    COURSE_ASSISTANT_REPLY_WITHOUT_CITATIONS,
    DEFAULT_IMAGE_QUESTION,
)


logger = logging.getLogger(__name__)


class TutorResponseFlowMixin:
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
        return self.vision_understanding_service.contextual_question(question, result), result.model_dump()

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
        attachments = self.repository.bound_attachments(user.id, session.id, message_ids)
        if not attachments:
            return question, None
        result = self.vision_understanding_service.understand(
            user=user,
            question=question,
            attachment_ids=[int(item.id) for item in attachments],
        )
        payload = result.model_dump()
        payload["reused_history_image"] = True
        payload["image_count"] = len(attachments)
        return self.vision_understanding_service.contextual_question(question, result), payload

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
            trace_id = stream_result.trace_id
            used_model = stream_result.used_model
            yield self._stream_event(
                "metadata",
                session_id=session.id,
                trace_id=trace_id,
                citation_count=len(citation_json),
                used_model=used_model,
                context_metadata=context_metadata,
            )

            answer_parts: list[str] = []
            for token in stream_result.tokens:
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
                content=answer.content,
                trace_id=answer.trace_id,
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
            content=answer.content,
            trace_id=answer.trace_id,
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
                self.conversation_memory_service.schedule_pair(
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
                self.profile_event_recorder.ingest_course_question_signal(
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
        attachment_map = self.repository.attachment_map([message.id for message in messages])
        resource_job_map = self.repository.resource_job_map(session.user_id, [message.id for message in messages])
        return session_detail_to_api(session, messages, attachment_map, resource_job_map)

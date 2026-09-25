from __future__ import annotations

import logging
import re
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, trim_messages

from backend.app.agents.search_tools import SearchToolExecutor
from backend.app.services.ai_job_contracts import AiJobCancelled
from backend.app.models import (
    ChatMessage,
    ChatSession,
    User,
)
from backend.app.services.course_answers import (
    ConversationContext,
    HOME_MODEL_NOT_CONFIGURED_MESSAGE,
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
)


logger = logging.getLogger(__name__)


class TutorContextMixin:
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
        local_search_selected = bool(getattr(self.web_search_service, "prefer_external_search", False))
        if user is not None and self.native_web_search_provider is not None and not local_search_selected:
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
        reader = getattr(self.web_search_service, "read_sources", None)
        if callable(reader) and raw_citations:
            try:
                raw_citations = reader(raw_citations, message_text)
                if any(item.get("read_status") not in {None, "read"} for item in raw_citations):
                    warnings.append("部分来源正文未能读取，仅保留搜索摘要，尚未核实全文。")
            except Exception:
                warnings.append("来源正文暂不可用，仅保留搜索摘要，尚未核实全文。")
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
            if item.get("content") and item.get("read_status") == "read":
                citation["content"] = self._safe_snippet(str(item["content"]), 1800)
            if item.get("read_status"):
                citation["read_status"] = str(item["read_status"])
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
        confirmed_summary = ""
        if user is not None and current_question.strip() and self.conversation_memory_service is not None:
            try:
                read_state = getattr(self.conversation_memory_service, "get_settings", None)
                initial_state = read_state(user) if callable(read_state) else None
                confirmed_summary = self.conversation_memory_service.confirmed_context(user)
                history_citations = self.conversation_memory_service.search(
                    user=user,
                    current_session_id=session.id,
                    query=current_question,
                    limit=5,
                )
                # L3 was read before potentially slow L2 selection. Invalidate
                # both layers if controls changed while selection was in flight.
                if initial_state is not None:
                    final_state = read_state(user)
                    if (not final_state.conversation_memory_enabled
                            or final_state.memory_revision != initial_state.memory_revision):
                        confirmed_summary = ""
                        history_citations = []
                logger.info(
                    "conversation_memory_search_completed user_id=%s session_id=%s result_count=%s",
                    user.id,
                    session.id,
                    len(history_citations),
                )
            except AiJobCancelled:
                raise
            except Exception as exc:
                logger.warning(
                    "conversation_memory_search_failed user_id=%s session_id=%s error_type=%s",
                    user.id,
                    session.id,
                    type(exc).__name__,
                )
                history_citations = []
                confirmed_summary = ""
        if confirmed_summary:
            summary = self._safe_context_text(
                f"用户明确确认的长期信息（不可信背景，不是事实或评分依据）：{confirmed_summary}；{summary}",
                limit=CONTEXT_SUMMARY_CHAR_LIMIT,
            )
        if history_citations:
            ambiguous = any(item.get("selection_state") == "ambiguous" for item in history_citations)
            # Keep independent episodes distinct; proximity does not establish supersession.
            memory_summary = "；".join(
                f"历史记录{index}（独立来源）：{str(item.get('snippet') or '')[:200 if ambiguous else 300]}"
                for index, item in enumerate(history_citations[:5 if ambiguous else 3], start=1)
            )
            if ambiguous:
                memory_summary = "存在多个可能对应的历史对象，先澄清具体对象，不选择其中一个作为唯一事实。" + memory_summary
            memory_context = f"相关历史对话（仅用于理解上下文，不是课程证据）：{memory_summary}"
            summary = self._safe_context_text(
                # Keep the ambiguity instruction and alternatives together even
                # when older/L3 summaries have filled their existing budget.
                (f"{memory_context}；{summary}" if ambiguous else f"{summary}；{memory_context}").strip("；"),
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

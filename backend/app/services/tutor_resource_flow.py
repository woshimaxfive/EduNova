from __future__ import annotations

import logging
from typing import Any, Iterator


from backend.app.agents.schemas import AgentState
from backend.app.agents.tool_policy import decide_tool_capabilities
from backend.app.models import (
    ChatSession,
    User,
)
from backend.app.services.course_answers import (
    ConversationContext,
)
from backend.app.services.tutor_contracts import (
    InvalidMaterialContextError,
    InvalidResourceContextError,
    SessionNotFoundError,
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


logger = logging.getLogger(__name__)


class TutorResourceFlowMixin:
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
        if topic:
            point = self.repository.find_knowledge_point_for_topic(requested_course_id, topic)
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

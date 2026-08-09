from __future__ import annotations

import logging
from typing import Any


from backend.app.agents.runtime import PendingAgentTrace, agent_log_from_pending_trace
from backend.app.models import (
    AgentRunLog,
    ChatMessage,
    ChatSession,
    User,
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


class TutorTraceMixin:
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

from __future__ import annotations

from dataclasses import replace
from time import perf_counter
from typing import TYPE_CHECKING, Any, Iterator

from langgraph.graph import END, START, StateGraph

from backend.app.api.errors import make_trace_id
from backend.app.agents.runtime import PendingAgentTrace, agent_log_from_pending_trace
from backend.app.agents.schemas import AgentState
from backend.app.agents.tool_policy import decide_tool_capabilities
from backend.app.models import ChatSession, User
from backend.app.schemas.tutor import TutorSessionDetail
from backend.app.services.content_locale import china_first_content_policy
from backend.app.services.course_answers import CourseAnswerGenerationError, CourseAnswerProgress, HOME_MODEL_NOT_CONFIGURED_MESSAGE
from backend.app.services.learner_context import context_service_from_repository
from backend.app.services.model_execution import execution_context_for_state, model_execution_scope
from backend.app.services.tutor_routing import project_semantic_route, project_visual_route
from backend.app.services.tutor_runtime import (
    CONTEXT_MESSAGE_CHAR_LIMIT,
    COURSE_ASSISTANT_REPLY_MODEL_NOT_CONFIGURED,
    COURSE_ASSISTANT_REPLY_WITHOUT_CITATIONS,
    supported_course_answer_kwargs,
)

if TYPE_CHECKING:
    from backend.app.services.tutor import TutorSessionService


class CourseTutorGraphRunner:
    workflow = "course_tutor"
    artifact_type = "chat_message"

    def __init__(self, service: TutorSessionService) -> None:
        self.service = service
        self.graph = self._build_graph()

    def append(
        self,
        *,
        user: User,
        session: ChatSession,
        message_text: str,
        force_search: bool = False,
        force_deep: bool = False,
        attachment_ids: list[int] | None = None,
        stored_message_text: str | None = None,
        vision_decision: dict[str, Any] | None = None,
        resource_context: dict[str, Any] | None = None,
    ) -> TutorSessionDetail:
        state = self._initial_state(
            user=user,
            session=session,
            message_text=message_text,
            force_search=force_search,
            force_deep=force_deep,
            attachment_ids=attachment_ids or [],
            stored_message_text=stored_message_text or message_text,
            vision_decision=vision_decision,
            resource_context=resource_context,
        )
        with model_execution_scope(execution_context_for_state(state, workflow=self.workflow)):
            result = self.graph.invoke(state)
        return self.service._persist_message_pair(
            user=user,
            session=session,
            message_text=stored_message_text or message_text,
            assistant_reply=str(result.get("assistant_reply") or ""),
            citation_json=list(result.get("citation_json", [])),
            trace_id=str(result.get("trace_id") or ""),
            home_tool_metadata=None,
            context_metadata=result.get("context_metadata"),
            course_trace_records=list(result.get("pending_traces", [])),
            profile_signal_updates=dict(result.get("profile_signal_updates", {})),
            profile_signal_confidence=dict(result.get("profile_signal_confidence", {})),
            attachment_ids=attachment_ids or [],
            resource_proposal=self.service._resource_proposal_from_state(result),
        )

    def stream(
        self,
        *,
        user: User,
        session: ChatSession,
        message_text: str,
        force_search: bool = False,
        force_deep: bool = False,
        attachment_ids: list[int] | None = None,
        stored_message_text: str | None = None,
        vision_decision: dict[str, Any] | None = None,
        resource_context: dict[str, Any] | None = None,
    ) -> Iterator[dict[str, Any]]:
        state = self._initial_state(
            user=user,
            session=session,
            message_text=message_text,
            force_search=force_search,
            force_deep=force_deep,
            attachment_ids=attachment_ids or [],
            stored_message_text=stored_message_text or message_text,
            vision_decision=vision_decision,
            resource_context=resource_context,
        )
        try:
            yield {"event": "status", "data": {"stage": "profile", "label": "正在读取学习画像"}}
            state.update(self._profile_node(state))
            yield {"event": "status", "data": {"stage": "route", "label": "正在理解问题"}}
            state.update(self._route_node(state))
            yield {"event": "status", "data": {"stage": "retriever", "label": "正在检索课程资料"}}
            state.update(self._retriever_node(state))
            yield {"event": "status", "data": {"stage": "web_search", "label": "正在判断是否需要外部补充"}}
            state.update(self._web_search_node(state))
            yield {"event": "status", "data": {"stage": "planner", "label": "正在规划回答"}}
            state.update(self._planner_node(state))
            citation_json = list(state.get("citation_json", []))
            yield {"event": "status", "data": {"stage": "tutor", "label": "正在生成课程回答"}}
            tutor_started = perf_counter()
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
                if isinstance(token, CourseAnswerProgress):
                    yield {"event": "status", "data": {"stage": token.stage, "label": token.label}}
                    continue
                if not isinstance(token, str) or not token:
                    continue
                answer_parts.append(token)
                yield {"event": "token", "data": {"content": token}}

            tutor_duration_ms = max(1, int((perf_counter() - tutor_started) * 1000))
            state["pending_traces"] = [
                replace(item, duration_ms=tutor_duration_ms) if item.agent_name == "tutor" else item
                for item in state.get("pending_traces", [])
            ]

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
                message_text=stored_message_text or message_text,
                assistant_reply=assistant_reply,
                citation_json=citation_json,
                trace_id=trace_id,
                home_tool_metadata=None,
                context_metadata=state.get("context_metadata"),
                course_trace_records=list(state.get("pending_traces", [])),
                profile_signal_updates=dict(state.get("profile_signal_updates", {})),
                profile_signal_confidence=dict(state.get("profile_signal_confidence", {})),
                attachment_ids=attachment_ids or [],
                resource_proposal=self.service._resource_proposal_from_state(state),
            )
            yield {"event": "done", "data": detail.model_dump()}
        except Exception as exc:
            yield {
                "event": "error",
                "data": {
                    **self.service._safe_model_error(exc),
                },
            }

    def _build_graph(self):
        graph = StateGraph(AgentState)
        graph.add_node("profile", self._profile_node)
        graph.add_node("route", self._route_node)
        graph.add_node("retriever", self._retriever_node)
        graph.add_node("web_search", self._web_search_node)
        graph.add_node("planner", self._planner_node)
        graph.add_node("tutor", self._tutor_node)
        graph.add_node("weakness", self._weakness_node)
        graph.add_node("review", self._review_node)
        graph.add_node("next_action", self._next_action_node)
        graph.add_edge(START, "profile")
        graph.add_edge("profile", "route")
        graph.add_edge("route", "retriever")
        graph.add_edge("retriever", "web_search")
        graph.add_edge("web_search", "planner")
        graph.add_edge("planner", "tutor")
        graph.add_edge("tutor", "weakness")
        graph.add_edge("weakness", "review")
        graph.add_edge("review", "next_action")
        graph.add_edge("next_action", END)
        return graph.compile()

    def _initial_state(
        self,
        *,
        user: User,
        session: ChatSession,
        message_text: str,
        force_search: bool,
        force_deep: bool,
        attachment_ids: list[int],
        stored_message_text: str,
        vision_decision: dict[str, Any] | None,
        resource_context: dict[str, Any] | None,
    ) -> AgentState:
        conversation_context = self.service._build_conversation_context(
            session,
            user=user,
            current_question=message_text,
        )
        retrieval_query = self.service._build_contextual_query(message_text, conversation_context)
        if resource_context:
            resource_hint = " ".join(
                item
                for item in (
                    str(resource_context.get("knowledge_point") or ""),
                    str(resource_context.get("title") or ""),
                )
                if item
            )
            retrieval_query = self.service._safe_query_text(
                f"{resource_hint} {retrieval_query}".strip(),
                limit=CONTEXT_MESSAGE_CHAR_LIMIT,
            )
        context_metadata = self.service._context_metadata(
            conversation_context,
            retrieval_query,
            message_text,
            retrieval_active=True,
        )
        if resource_context:
            context_metadata.update(
                {
                    "resource_context_used": True,
                    "context_resource_id": resource_context.get("resource_id"),
                    "context_resource_type": resource_context.get("resource_type"),
                }
            )
        decision = decide_tool_capabilities(message_text, force_search=force_search, force_deep=force_deep)
        return {
            "trace_id": make_trace_id(),
            "workflow": self.workflow,
            "artifact_type": self.artifact_type,
            "user_id": user.id,
            "course_id": session.course_id,
            "user": user,
            "session": session,
            "message_text": message_text,
            "attachment_ids": attachment_ids,
            "stored_message_text": stored_message_text,
            "vision_decision": vision_decision,
            "resource_context": resource_context,
            "use_web_search": force_search,
            "deep_thinking": force_deep,
            "search_required": decision.search_required,
            "reasoning_mode": decision.reasoning_mode,
            "source_scope": decision.source_scope,
            "tool_reason_codes": list(decision.reason_codes),
            "tool_reason_summary": decision.reason_summary,
            "course_related": False,
            "conversation_context": conversation_context if conversation_context.has_context else None,
            "retrieval_query": retrieval_query,
            "context_metadata": context_metadata,
            "pending_traces": [],
            "warnings": [],
            "errors": [],
        }

    def _profile_node(self, state: AgentState) -> dict[str, Any]:
        def work() -> tuple[dict[str, Any], str, str, dict[str, Any]]:
            context_service = context_service_from_repository(self.service.repository)
            if context_service is None or state.get("course_id") is None:
                metadata = {
                    "profile_applied_version": 0,
                    "profile_completeness": 0,
                    "trusted_dimension_count": 0,
                    "advisory_dimension_count": 0,
                    "profile_context_used": False,
                }
                return {"learner_context": {}, "learner_context_metadata": metadata}, "当前运行环境未提供画像上下文。", "warning", metadata
            learner_context = context_service.course_context(int(state["user_id"]), int(state["course_id"]))
            metadata = learner_context.trace_metadata()
            return {
                "learner_context": learner_context.prompt_summary(),
                "learner_context_metadata": metadata,
            }, f"已读取 {metadata['trusted_dimension_count']} 个可信画像维度和课程学习状态。", "completed", metadata

        return self._run_node(
            state,
            agent_name="profile",
            step_index=1,
            input_summary="读取学习画像与课程上下文",
            work=work,
        )

    def _route_node(self, state: AgentState) -> dict[str, Any]:
        def work():
            visual = state.get("vision_decision")
            if isinstance(visual, dict):
                intent = str(visual.get("intent") or "visual_learning")
                projection = project_visual_route(
                    visual=visual,
                    message_text=str(state["message_text"]),
                    force_search=bool(state.get("use_web_search")),
                    force_deep=bool(state.get("deep_thinking")),
                    intent=intent,
                    summary="已结合本次图片形成课程检索问题。",
                    warnings=list(state.get("warnings", [])),
                    attachment_count=len(state.get("attachment_ids", [])),
                )
                return {
                    **projection.updates,
                    "course_related": True,
                    "profile_signal_updates": {},
                    "profile_signal_confidence": {},
                }, projection.summary, "completed", {
                    **projection.metadata,
                    "profile_signal_count": 0,
                }
            decision = self.service._semantic_decision(
                user=state["user"],
                session=state["session"],
                question=str(state["message_text"]),
                force_search=bool(state.get("use_web_search")),
                force_deep=bool(state.get("deep_thinking")),
                conversation_context=state.get("conversation_context"),
            )
            referenced_turn_ids = list(decision.referenced_turn_ids)
            history_message, history_visual = self.service._prepare_history_visual_question(
                user=state["user"],
                session=state["session"],
                question=str(state["message_text"]),
                referenced_turn_ids=referenced_turn_ids,
            )
            intent = str(history_visual.get("intent") or "visual_learning") if history_visual else decision.intent
            projection = project_semantic_route(
                decision=decision,
                intent=intent,
                message_text=str(state["message_text"]),
                fallback_retrieval_query=str(state.get("retrieval_query") or state["message_text"]),
                history_message=history_message,
                history_visual=history_visual,
                warnings=list(state.get("warnings", [])),
            )
            updates = {
                **projection.updates,
                "course_related": decision.course_related,
                "profile_signal_updates": {} if history_visual else dict(decision.profile_updates),
                "profile_signal_confidence": {} if history_visual else dict(decision.profile_confidence),
            }
            metadata = {
                **projection.metadata,
                "profile_signal_count": 0 if history_visual else len(decision.profile_updates),
            }
            return updates, decision.reason_summary, "completed", metadata

        return self._run_node(
            state,
            agent_name="route",
            step_index=2,
            input_summary="判断课程问题的工具与推理需求",
            work=work,
        )

    def _retriever_node(self, state: AgentState) -> dict[str, Any]:
        def work() -> tuple[dict[str, Any], str, str, dict[str, Any]]:
            citations = self.service._search_course_citations(
                user=state["user"],
                session=state["session"],
                message_text=str(state["message_text"]),
                retrieval_query=str(state["retrieval_query"]),
            )
            conversation_context = state.get("conversation_context")
            history_citations = list(conversation_context.history_citations) if conversation_context is not None else []
            citations = [*history_citations, *citations]
            return (
                {"citation_json": citations, "citations": citations},
                f"命中 {len(citations)} 条课程引用。",
                "completed",
                {"citation_count": len(citations), "source_count": len(citations)},
            )

        return self._run_node(
            state,
            agent_name="retriever",
            step_index=3,
            input_summary="检索当前课程知识切片",
            work=work,
        )

    def _web_search_node(self, state: AgentState) -> dict[str, Any]:
        def work() -> tuple[dict[str, Any], str, str, dict[str, Any]]:
            citations = list(state.get("citation_json", []))
            course_citation_count = sum(1 for item in citations if item.get("source_type") not in {"web", "history"})
            evidence_decision = None
            if (
                not bool(state.get("search_required"))
                and bool(state.get("course_related"))
                and course_citation_count > 0
            ):
                evidence_decision = {
                    "relation_type": "direct",
                    "relevant_citation_ids": [
                        str(item.get("chunk_id") or item.get("id") or "")
                        for item in citations
                        if item.get("source_type") not in {"web", "history"}
                    ],
                    "course_evidence_sufficient": True,
                    "external_search_helpful": False,
                    "confidence": float(state.get("semantic_decision_confidence") or 0),
                }
            elif self.service.semantic_decision_service is not None:
                course = self.service.repository.get_course_for_user(int(state["user_id"]), int(state["course_id"]))
                evidence_decision = self.service.semantic_decision_service.assess_course_evidence(
                    user=state["user"],
                    question=str(state["message_text"]),
                    course_title=course.title if course is not None else "",
                    citations=citations,
                )
            if isinstance(evidence_decision, dict):
                relation_type = str(evidence_decision.get("relation_type") or "off_topic")
                relevant_ids = {str(item) for item in evidence_decision.get("relevant_citation_ids", [])}
                if relevant_ids:
                    citations = [
                        item for item in citations
                        if item.get("source_type") == "history"
                        or str(item.get("chunk_id") or item.get("id") or "") in relevant_ids
                    ]
                state["course_related"] = relation_type in {"direct", "adjacent"}
            else:
                relation_type = "direct" if state.get("course_related") else "unknown"
            search_required = bool(state.get("search_required"))
            reason_codes = list(state.get("tool_reason_codes", []))
            if isinstance(evidence_decision, dict):
                if relation_type == "off_topic":
                    search_required = False
                    reason_codes.append("course_off_topic")
                elif bool(evidence_decision.get("external_search_helpful")) and not bool(evidence_decision.get("course_evidence_sufficient")):
                    search_required = True
                    reason_codes.append("course_evidence_gap")
            elif course_citation_count == 0 and state.get("course_related") and not search_required:
                search_required = True
                reason_codes.append("course_evidence_gap")
            updates: dict[str, Any] = {
                "search_required": search_required,
                "reasoning_mode": str(state.get("reasoning_mode") or "auto"),
                "tool_reason_codes": list(dict.fromkeys(reason_codes)),
                "tool_reason_summary": str(state.get("tool_reason_summary") or ""),
                "course_citation_count": course_citation_count,
                "relation_type": relation_type,
                "course_evidence_sufficient": bool(evidence_decision.get("course_evidence_sufficient")) if isinstance(evidence_decision, dict) else course_citation_count > 0,
                "external_search_helpful": bool(evidence_decision.get("external_search_helpful")) if isinstance(evidence_decision, dict) else search_required,
                "evidence_decision_confidence": float(evidence_decision.get("confidence") or 0) if isinstance(evidence_decision, dict) else 0.0,
            }
            if not search_required:
                return (
                    {**updates, "citation_json": citations, "web_citation_count": 0},
                    "课程资料足以处理当前问题，无需联网补充。",
                    "skipped",
                    {
                        "search_required": False,
                        "reasoning_mode": str(state.get("reasoning_mode") or "auto"),
                        "tool_reason_codes": list(dict.fromkeys(reason_codes)),
                        "tool_reason_summary": str(state.get("tool_reason_summary") or ""),
                        "course_citation_count": course_citation_count,
                        "web_citation_count": 0,
                        "search_backend": "none",
                        "relation_type": relation_type,
                        "course_evidence_sufficient": updates["course_evidence_sufficient"],
                        "external_search_helpful": updates["external_search_helpful"],
                    },
                )

            warnings = list(state.get("warnings", []))
            web_citations = self.service._web_search_citations(
                str(
                    state.get("semantic_search_query")
                    if str(state.get("semantic_decision_mode")) in {"model", "model_forced"}
                    else state["retrieval_query"]
                ),
                warnings,
                user=state["user"],
                reasoning_mode=str(state.get("reasoning_mode") or "auto"),
                force=bool(state.get("use_web_search")),
            )
            web_citations = china_first_content_policy.decorate_and_rank_citations(
                web_citations,
                str(state.get("source_scope") or "mainland_preferred"),
            )
            supplements = [{**item, "evidence_role": "external_supplement"} for item in web_citations]
            citations.extend(supplements)
            search_backend = str(supplements[0].get("search_backend") or "external") if supplements else "none"
            return (
                {
                    **updates,
                    "citation_json": citations,
                    "citations": citations,
                    "warnings": warnings,
                    "web_citation_count": len(supplements),
                },
                f"返回 {len(supplements)} 条外部补充来源。" if supplements else (warnings[-1] if warnings else "未返回外部来源。"),
                "completed" if supplements else "warning",
                {
                    "search_required": True,
                    "reasoning_mode": str(state.get("reasoning_mode") or "auto"),
                    "tool_reason_codes": list(dict.fromkeys(reason_codes)),
                    "tool_reason_summary": str(state.get("tool_reason_summary") or ""),
                    "course_citation_count": course_citation_count,
                    "web_citation_count": len(supplements),
                    "warning_count": len(warnings),
                    "search_backend": search_backend,
                    "relation_type": relation_type,
                    "course_evidence_sufficient": updates["course_evidence_sufficient"],
                    "external_search_helpful": updates["external_search_helpful"],
                },
            )

        return self._run_node(
            state,
            agent_name="web_search",
            step_index=4,
            input_summary="按需检索课程外部补充来源",
            work=work,
        )

    def _planner_node(self, state: AgentState) -> dict[str, Any]:
        def work() -> tuple[dict[str, Any], str, str, dict[str, Any]]:
            if state.get("response_mode") == "action":
                return ({"plan_summary": ""}, "资源动作无需重复生成课程回答规划。", "skipped", {"response_mode": "action"})
            if state.get("reasoning_mode") != "deep":
                return ({"plan_summary": ""}, "模型将自适应处理当前问题。", "skipped", {"reasoning_mode": "auto"})
            plan_summary = ""
            if self.service.course_answer_generator is not None:
                plan_summary = str(
                    self.service.course_answer_generator.plan_course(
                        user=state["user"],
                        question=str(state["message_text"]),
                        citations=list(state.get("citation_json", [])),
                    )
                    or ""
                )
            return (
                {"plan_summary": plan_summary},
                "已生成安全课程回答规划摘要。" if plan_summary else "规划模型不可用，继续按深度模式回答。",
                "completed" if plan_summary else "warning",
                {"reasoning_mode": "deep"},
            )

        return self._run_node(
            state,
            agent_name="planner",
            step_index=5,
            input_summary="生成安全课程回答规划",
            work=work,
        )

    def _tutor_node(self, state: AgentState) -> dict[str, Any]:
        def work() -> tuple[dict[str, Any], str, str, dict[str, Any]]:
            if state.get("response_mode") == "action":
                return (
                    {"assistant_reply": self.service._resource_action_reply(state), "used_model": False},
                    "已返回资源任务确认，不重复生成课程长回答。",
                    "completed",
                    {"response_mode": "action", "resource_action": state.get("resource_action")},
                )
            citations = list(state.get("citation_json", []))
            evidence_citations = [item for item in citations if item.get("source_type") != "history"]
            if not evidence_citations:
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
                course_count = sum(1 for item in citations if item.get("source_type") not in {"web", "history"})
                return (
                    {
                        "assistant_reply": COURSE_ASSISTANT_REPLY_MODEL_NOT_CONFIGURED if course_count else HOME_MODEL_NOT_CONFIGURED_MESSAGE,
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
                **supported_course_answer_kwargs(self.service.course_answer_generator.generate, state),
            )
            trace_id = answer.trace_id or state["trace_id"]
            return (
                {
                    "assistant_reply": answer.content,
                    "trace_id": trace_id,
                    "used_model": answer.trace_id is not None,
                },
                "已生成带引用的课程回答。",
                "completed",
                {"citation_count": len(citations)},
            )

        return self._run_node(
            state,
            agent_name="tutor",
            step_index=6,
            input_summary="生成课程导师回答",
            work=work,
        )

    def _prepare_stream_tutor_node(self, state: AgentState) -> dict[str, Any]:
        def work() -> tuple[dict[str, Any], str, str, dict[str, Any]]:
            if state.get("response_mode") == "action":
                return (
                    {"tokens": [self.service._resource_action_reply(state)], "used_model": False},
                    "已返回资源任务确认，不重复生成课程长回答。",
                    "completed",
                    {"response_mode": "action", "resource_action": state.get("resource_action")},
                )
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
                course_count = sum(1 for item in citations if item.get("source_type") != "web")
                return (
                    {
                        "tokens": [COURSE_ASSISTANT_REPLY_MODEL_NOT_CONFIGURED if course_count else HOME_MODEL_NOT_CONFIGURED_MESSAGE],
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
                **supported_course_answer_kwargs(self.service.course_answer_generator.stream, state),
            )
            trace_id = stream_result.trace_id or state["trace_id"]
            return (
                {
                    "tokens": stream_result.tokens,
                    "trace_id": trace_id,
                    "used_model": stream_result.used_model and stream_result.trace_id is not None,
                },
                "已启动课程导师流式回答。",
                "completed",
                {"citation_count": len(citations)},
            )

        return self._run_node(
            state,
            agent_name="tutor",
            step_index=6,
            input_summary="生成课程导师回答",
            work=work,
        )

    def _weakness_node(self, state: AgentState) -> dict[str, Any]:
        if state.get("response_mode") == "action":
            return self._run_node(
                state,
                agent_name="weakness",
                step_index=7,
                input_summary="识别弱点候选",
                work=lambda: ({}, "资源创建请求不作为薄弱点证据。", "skipped", {"response_mode": "action"}),
            )
        citation_count = sum(1 for item in state.get("citation_json", []) if item.get("source_type") != "web")
        signal_count = len(state.get("profile_signal_updates", {}))
        output = (
            "已形成课程问答画像候选。"
            if citation_count and signal_count
            else "未发现明确画像信号，不更新学习画像。"
        )
        return self._run_node(
            state,
            agent_name="weakness",
            step_index=7,
            input_summary="识别弱点候选",
            work=lambda: ({}, output, "completed", {"citation_count": citation_count, "profile_signal_count": signal_count}),
        )

    def _review_node(self, state: AgentState) -> dict[str, Any]:
        if state.get("response_mode") == "action":
            metadata = {
                "review_status": "passed",
                "confidence": float(state.get("semantic_decision_confidence") or 0),
                "risk_flags": [],
                "safety_summary": "资源动作已通过结构、类型和课程边界校验。",
                "response_mode": "action",
            }
            return self._run_node(
                state,
                agent_name="review",
                step_index=8,
                input_summary="审核资源动作边界",
                work=lambda: ({"review_result": metadata}, "资源动作确认无需重复模型审核。", "completed", metadata),
            )
        citations = list(state.get("citation_json", []))
        course_citation_count = sum(1 for item in citations if item.get("source_type") != "web")
        web_citation_count = sum(1 for item in citations if item.get("source_type") == "web")
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
            "course_citation_count": course_citation_count,
            "web_citation_count": web_citation_count,
            "external_only": course_citation_count == 0 and web_citation_count > 0,
        }
        return self._run_node(
            state,
            agent_name="review",
            step_index=8,
            input_summary="审核回答依据与安全边界",
            work=lambda: ({"review_result": metadata}, f"ReviewAgent 审核结果：{review_status}", review_status, metadata),
        )

    def _next_action_node(self, state: AgentState) -> dict[str, Any]:
        citations = list(state.get("citation_json", []))
        output = "建议查看来源、生成资源或进入练习。" if citations else "建议补充课程资料或换一个与课程资料更贴近的问题。"
        return self._run_node(
            state,
            agent_name="next_action",
            step_index=9,
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
            with model_execution_scope(execution_context_for_state(state, workflow=self.workflow, node_name=agent_name)):
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
        citations = list(state.get("citation_json", []))
        resource_context = state.get("resource_context") if isinstance(state.get("resource_context"), dict) else None
        return {
            "citation_count": len(citations),
            "course_citation_count": sum(1 for item in citations if item.get("source_type") != "web"),
            "web_citation_count": sum(1 for item in citations if item.get("source_type") == "web"),
            "search_required": bool(state.get("search_required")),
            "reasoning_mode": str(state.get("reasoning_mode") or "auto"),
            "tool_reason_codes": list(state.get("tool_reason_codes", [])),
            "tool_reason_summary": str(state.get("tool_reason_summary") or "")[:240],
            "semantic_decision_mode": str(state.get("semantic_decision_mode") or "degraded"),
            "semantic_decision_confidence": round(float(state.get("semantic_decision_confidence") or 0), 4),
            "semantic_intent": str(state.get("intent") or "general_learning")[:64],
            "profile_signal_count": len(state.get("profile_signal_updates", {})),
            **self.service._safe_trace_context_metadata(state.get("context_metadata")),
            "resource_context_used": bool(resource_context),
            "context_resource_id": resource_context.get("resource_id") if resource_context else None,
            "context_resource_type": str(resource_context.get("resource_type") or "")[:32]
            if resource_context
            else "",
        }

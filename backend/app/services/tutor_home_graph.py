from __future__ import annotations

import re
from time import perf_counter
from typing import TYPE_CHECKING, Any, Iterator

from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph

from backend.app.api.errors import make_trace_id
from backend.app.agents.runtime import PendingAgentTrace, agent_log_from_pending_trace
from backend.app.agents.schemas import AgentState
from backend.app.agents.tool_policy import decide_tool_capabilities
from backend.app.models import ChatSession, User
from backend.app.schemas.tutor import TutorSessionDetail
from backend.app.services.content_locale import china_first_content_policy
from backend.app.services.course_answers import (
    CourseAnswerGenerationError,
    CourseAnswerService,
    HOME_MODEL_NOT_CONFIGURED_MESSAGE,
)
from backend.app.services.learner_context import context_service_from_repository
from backend.app.services.model_execution import execution_context_for_state, model_execution_scope
from backend.app.services.tutor_routing import project_semantic_route, project_visual_route
from backend.app.services.tutor_runtime import HOME_TUTOR_GRAPH_STEPS, supported_context_kwargs

if TYPE_CHECKING:
    from backend.app.services.tutor import TutorSessionService


class HomeTutorGraphRunner:
    workflow = "home_tutor"
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
        use_web_search: bool,
        deep_thinking: bool,
        selected_material_ids: list[int],
        initial_warnings: list[str] | None = None,
        attachment_ids: list[int] | None = None,
        stored_message_text: str | None = None,
        vision_decision: dict[str, Any] | None = None,
    ) -> TutorSessionDetail:
        state = self._initial_state(
            user=user,
            session=session,
            message_text=message_text,
            use_web_search=use_web_search,
            deep_thinking=deep_thinking,
            selected_material_ids=selected_material_ids,
            initial_warnings=initial_warnings,
            streaming=False,
            attachment_ids=attachment_ids or [],
            stored_message_text=stored_message_text or message_text,
            vision_decision=vision_decision,
        )
        with model_execution_scope(execution_context_for_state(state, workflow=self.workflow)):
            result = self.graph.invoke(state)
        detail = result.get("detail")
        if not isinstance(detail, TutorSessionDetail):
            raise CourseAnswerGenerationError("主页回答未能完成持久化。")
        return detail

    def stream(
        self,
        *,
        user: User,
        session: ChatSession,
        message_text: str,
        use_web_search: bool,
        deep_thinking: bool,
        selected_material_ids: list[int],
        initial_warnings: list[str] | None = None,
        attachment_ids: list[int] | None = None,
        stored_message_text: str | None = None,
        vision_decision: dict[str, Any] | None = None,
    ) -> Iterator[dict[str, Any]]:
        state = self._initial_state(
            user=user,
            session=session,
            message_text=message_text,
            use_web_search=use_web_search,
            deep_thinking=deep_thinking,
            selected_material_ids=selected_material_ids,
            initial_warnings=initial_warnings,
            streaming=True,
            attachment_ids=attachment_ids or [],
            stored_message_text=stored_message_text or message_text,
            vision_decision=vision_decision,
        )
        try:
            final_detail: TutorSessionDetail | None = None
            for stream_mode, payload in self.graph.stream(state, stream_mode=["custom", "values"]):
                if stream_mode == "custom":
                    if isinstance(payload, dict) and isinstance(payload.get("event"), str):
                        yield payload
                    continue
                if stream_mode == "values" and isinstance(payload, dict):
                    detail = payload.get("detail")
                    if isinstance(detail, TutorSessionDetail):
                        final_detail = detail
            if final_detail is None:
                raise CourseAnswerGenerationError("主页回答未能完成持久化。")
            yield {"event": "done", "data": final_detail.model_dump()}
        except Exception as exc:
            yield {
                "event": "error",
                "data": {
                    **self.service._safe_model_error(exc),
                },
            }

    def _build_graph(self):
        graph = StateGraph(AgentState)
        graph.add_node("context", self._context_node)
        graph.add_node("route", self._route_node)
        graph.add_node("material_retriever", self._material_retriever_node)
        graph.add_node("web_search", self._web_search_node)
        graph.add_node("planner", self._planner_node)
        graph.add_node("answer", self._answer_node)
        graph.add_node("review", self._review_node)
        graph.add_node("repair", self._repair_node)
        graph.add_node("persist", self._persist_node)
        graph.add_edge(START, "context")
        graph.add_edge("context", "route")
        graph.add_edge("route", "material_retriever")
        graph.add_edge("material_retriever", "web_search")
        graph.add_edge("web_search", "planner")
        graph.add_edge("planner", "answer")
        graph.add_edge("answer", "review")
        graph.add_conditional_edges(
            "review",
            self._after_review,
            {"repair": "repair", "persist": "persist"},
        )
        graph.add_edge("repair", "review")
        graph.add_edge("persist", END)
        return graph.compile()

    def _initial_state(
        self,
        *,
        user: User,
        session: ChatSession,
        message_text: str,
        use_web_search: bool,
        deep_thinking: bool,
        selected_material_ids: list[int],
        initial_warnings: list[str] | None,
        streaming: bool,
        attachment_ids: list[int],
        stored_message_text: str,
        vision_decision: dict[str, Any] | None,
    ) -> AgentState:
        decision = decide_tool_capabilities(
            message_text,
            force_search=use_web_search,
            force_deep=deep_thinking,
        )
        return {
            "trace_id": make_trace_id(),
            "workflow": self.workflow,
            "artifact_type": self.artifact_type,
            "user_id": user.id,
            "course_id": None,
            "user": user,
            "session": session,
            "message_text": message_text,
            "attachment_ids": attachment_ids,
            "stored_message_text": stored_message_text,
            "vision_decision": vision_decision,
            "use_web_search": use_web_search,
            "deep_thinking": deep_thinking,
            "search_required": decision.search_required,
            "reasoning_mode": decision.reasoning_mode,
            "source_scope": decision.source_scope,
            "tool_reason_codes": list(decision.reason_codes),
            "tool_reason_summary": decision.reason_summary,
            "selected_material_ids": list(dict.fromkeys(selected_material_ids))[:10],
            "streaming": streaming,
            "pending_traces": [],
            "warnings": list(initial_warnings or []),
            "errors": [],
            "repair_count": 0,
        }

    def _context_node(self, state: AgentState) -> dict[str, Any]:
        conversation_context = self.service._build_conversation_context(
            state["session"],
            user=state["user"],
            current_question=str(state["message_text"]),
        )
        retrieval_query = self.service._build_contextual_query(str(state["message_text"]), conversation_context)
        context_service = context_service_from_repository(self.service.repository)
        global_context = context_service.global_context(int(state["user_id"])) if context_service is not None else None
        learner_context = {
            key: global_context.advisory_value(key)
            for key in (
                "major_background",
                "knowledge_foundation",
                "learning_goal",
                "cognitive_style",
                "learning_preference",
                "weak_points",
                "learning_pace",
                "motivation_interest",
            )
            if global_context is not None and global_context.advisory_value(key)
        }
        profile_metadata = global_context.trace_metadata() if global_context is not None else {
            "profile_applied_version": 0,
            "profile_completeness": 0,
            "trusted_dimension_count": 0,
            "advisory_dimension_count": 0,
            "profile_context_used": False,
        }
        context_metadata = self.service._context_metadata(
            conversation_context,
            retrieval_query,
            str(state["message_text"]),
            retrieval_active=bool(state.get("selected_material_ids")) or bool(state.get("search_required")),
        )
        self._write(
            state,
            "metadata",
            {
                "session_id": str(state["session"].id),
                "trace_id": state["trace_id"],
                "workflow": self.workflow,
                "artifact_type": self.artifact_type,
                "citation_count": 0,
                "used_model": self.service.course_answer_generator is not None,
                "steps": HOME_TUTOR_GRAPH_STEPS,
                **self.service._safe_trace_context_metadata(context_metadata),
                **profile_metadata,
            },
        )
        return self._run_node(
            state,
            agent_name="context",
            step_index=1,
            input_summary="读取主页画像与会话上下文",
            status_label="正在读取会话上下文",
            work=lambda: (
                {
                    "conversation_context": conversation_context if conversation_context.has_context else None,
                    "retrieval_query": retrieval_query,
                    "context_metadata": context_metadata,
                    "learner_context": learner_context,
                    "learner_context_metadata": profile_metadata,
                },
                f"已参考最近 {conversation_context.message_count} 条安全会话。",
                "completed",
                {**context_metadata, **profile_metadata},
            ),
        )

    def _route_node(self, state: AgentState) -> dict[str, Any]:
        def work():
            message = str(state["message_text"])
            visual = state.get("vision_decision")
            if isinstance(visual, dict):
                intent = "material_question" if state.get("selected_material_ids") else str(visual.get("intent") or "visual_learning")
                projection = project_visual_route(
                    visual=visual,
                    message_text=message,
                    force_search=bool(state.get("use_web_search")),
                    force_deep=bool(state.get("deep_thinking")),
                    intent=intent,
                    summary="已结合本次图片形成可审计的学习问题。",
                    warnings=list(state.get("warnings", [])),
                    attachment_count=len(state.get("attachment_ids", [])),
                )
                return (
                    {**projection.updates, "requires_fresh_info": projection.updates["search_required"]},
                    projection.summary,
                    "completed",
                    projection.metadata,
                )
            decision = self.service._semantic_decision(
                user=state["user"],
                session=state["session"],
                question=message,
                force_search=bool(state.get("use_web_search")),
                force_deep=bool(state.get("deep_thinking")),
                conversation_context=state.get("conversation_context"),
            )
            referenced_turn_ids = list(decision.referenced_turn_ids)
            history_message, history_visual = self.service._prepare_history_visual_question(
                user=state["user"],
                session=state["session"],
                question=message,
                referenced_turn_ids=referenced_turn_ids,
            )
            intent = "material_question" if state.get("selected_material_ids") else (
                str(history_visual.get("intent") or "visual_learning") if history_visual else decision.intent
            )
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
                "requires_fresh_info": decision.intent in {"current_information", "verification"},
            }
            metadata = {
                **projection.metadata,
                "uses_history": decision.uses_history,
                "referenced_turn_count": len(decision.referenced_turn_ids),
            }
            return updates, f"已识别为 {intent}，{decision.reason_summary}。", "completed", metadata

        return self._run_node(
            state,
            agent_name="route",
            step_index=2,
            input_summary="判断问题类型与工具需求",
            status_label="正在理解问题",
            work=work,
        )

    def _material_retriever_node(self, state: AgentState) -> dict[str, Any]:
        def work() -> tuple[dict[str, Any], str, str, dict[str, Any]]:
            selected_ids = list(state.get("selected_material_ids", []))
            conversation_context = state.get("conversation_context")
            history_citations = list(conversation_context.history_citations) if conversation_context is not None else []
            if not selected_ids or self.service.material_citation_searcher is None:
                retrieval_mode = "none"
                embedding_status = "unavailable"
                return (
                    {"citation_json": history_citations, "retrieval_mode": retrieval_mode, "embedding_status": embedding_status},
                    "本次未选择资料。" if not selected_ids else "资料检索服务暂不可用。",
                    "skipped" if not selected_ids else "warning",
                    {
                        "citation_count": 0,
                        "source_count": 0,
                        "retrieval_mode": retrieval_mode,
                        "embedding_status": embedding_status,
                    },
                )
            result = self.service.material_citation_searcher.search(
                user=state["user"],
                material_ids=selected_ids,
                query=str(state["retrieval_query"]),
                top_k=5,
            )
            citations = [*history_citations, *result.citations]
            retrieval_mode = result.retrieval_mode
            embedding_status = result.embedding_status
            rerank_status = result.rerank_status
            return (
                {
                    "citation_json": citations,
                    "retrieval_mode": retrieval_mode,
                    "embedding_status": embedding_status,
                    "rerank_status": rerank_status,
                },
                f"命中 {len(citations)} 条相关资料片段。",
                "completed" if citations else "warning",
                {
                    "citation_count": len(citations),
                    "source_count": len(citations),
                    "retrieval_mode": retrieval_mode,
                    "embedding_status": embedding_status,
                    "rerank_status": rerank_status,
                },
            )

        return self._run_node(
            state,
            agent_name="material_retriever",
            step_index=3,
            input_summary="检索选中资料的相关章节",
            status_label="正在检索资料",
            work=work,
        )

    def _web_search_node(self, state: AgentState) -> dict[str, Any]:
        def work() -> tuple[dict[str, Any], str, str, dict[str, Any]]:
            citations = list(state.get("citation_json", []))
            warnings = list(state.get("warnings", []))
            if not state.get("search_required"):
                self._write(state, "sources", {"citations": citations, "warnings": warnings})
                return (
                    {"citation_json": citations, "warnings": warnings},
                    "当前问题不需要联网搜索。",
                    "skipped",
                    {"citation_count": len(citations), "warning_count": len(warnings)},
                )
            web_citations = self.service._web_search_citations(
                message_text=str(
                    state.get("semantic_search_query")
                    if str(state.get("semantic_decision_mode")) in {"model", "model_forced"}
                    else state["retrieval_query"]
                ),
                warnings=warnings,
                user=state["user"],
                reasoning_mode=str(state.get("reasoning_mode") or "auto"),
                force=bool(state.get("use_web_search")),
            )
            web_citations = china_first_content_policy.decorate_and_rank_citations(
                web_citations,
                str(state.get("source_scope") or "mainland_preferred"),
            )
            citations.extend(web_citations)
            search_backend = str(web_citations[0].get("search_backend") or "external") if web_citations else "none"
            self._write(state, "sources", {"citations": citations, "warnings": warnings})
            return (
                {"citation_json": citations, "warnings": warnings, "web_citation_count": len(web_citations)},
                f"返回 {len(web_citations)} 条联网来源。" if web_citations else (warnings[-1] if warnings else "未返回联网来源。"),
                "completed" if web_citations else "warning",
                {
                    "citation_count": len(citations),
                    "source_count": len(citations),
                    "warning_count": len(warnings),
                    "search_backend": search_backend,
                },
            )

        return self._run_node(
            state,
            agent_name="web_search",
            step_index=4,
            input_summary="按需执行联网检索",
            status_label="正在联网搜索" if state.get("search_required") else "正在确认来源",
            work=work,
        )

    def _planner_node(self, state: AgentState) -> dict[str, Any]:
        def work() -> tuple[dict[str, Any], str, str, dict[str, Any]]:
            if state.get("response_mode") == "action":
                return ({"plan_summary": ""}, "资源动作无需重复生成回答规划。", "skipped", {"response_mode": "action"})
            if state.get("reasoning_mode") != "deep":
                return ({"plan_summary": ""}, "模型将自适应处理当前问题。", "skipped", {"reasoning_mode": "auto"})
            plan_summary = ""
            if self.service.course_answer_generator is not None:
                plan_summary = str(
                    self.service.course_answer_generator.plan_home(
                        user=state["user"],
                        question=str(state["message_text"]),
                        citations=list(state.get("citation_json", [])),
                    )
                    or ""
                )
            return (
                {"plan_summary": plan_summary},
                "已生成安全回答规划摘要。" if plan_summary else "规划模型不可用，继续使用结构化回答。",
                "completed" if plan_summary else "warning",
                {"reasoning_mode": "deep"},
            )

        return self._run_node(
            state,
            agent_name="planner",
            step_index=5,
            input_summary="生成安全回答规划",
            status_label="正在规划回答" if state.get("reasoning_mode") == "deep" else "正在组织回答",
            work=work,
        )

    def _answer_node(self, state: AgentState) -> dict[str, Any]:
        def work() -> tuple[dict[str, Any], str, str, dict[str, Any]]:
            if state.get("response_mode") == "action":
                reply = self.service._resource_action_reply(state)
                if state.get("streaming"):
                    self._write(state, "token", {"content": reply})
                return (
                    {"assistant_reply": reply, "used_model": False},
                    "已返回资源任务确认，不重复生成长回答。",
                    "completed",
                    {"response_mode": "action", "resource_action": state.get("resource_action")},
                )
            generator = self.service.course_answer_generator
            if generator is None:
                reply = HOME_MODEL_NOT_CONFIGURED_MESSAGE
                if state.get("streaming"):
                    self._write(state, "token", {"content": reply})
                return (
                    {"assistant_reply": reply, "used_model": False},
                    "当前未配置可用模型，已返回清晰提示。",
                    "warning",
                    {"risk_flags": ["model_not_configured"]},
                )

            if state.get("streaming"):
                stream_result = generator.stream_home(
                    user=state["user"],
                    question=str(state["message_text"]),
                    citations=list(state.get("citation_json", [])),
                    use_web_search=bool(state.get("search_required")),
                    deep_thinking=state.get("reasoning_mode") == "deep",
                    warnings=list(state.get("warnings", [])),
                    conversation_context=state.get("conversation_context"),
                    plan_summary=str(state.get("plan_summary") or ""),
                    **supported_context_kwargs(generator.stream_home, state.get("learner_context")),
                )
                reply = self._consume_stream_tokens(state, stream_result.tokens)
                used_model = stream_result.used_model and stream_result.trace_id is not None
            else:
                generated = generator.generate_home(
                    user=state["user"],
                    question=str(state["message_text"]),
                    citations=list(state.get("citation_json", [])),
                    use_web_search=bool(state.get("search_required")),
                    deep_thinking=state.get("reasoning_mode") == "deep",
                    warnings=list(state.get("warnings", [])),
                    conversation_context=state.get("conversation_context"),
                    plan_summary=str(state.get("plan_summary") or ""),
                    **supported_context_kwargs(generator.generate_home, state.get("learner_context")),
                )
                reply = generated.content.strip()
                used_model = generated.trace_id is not None
            if not reply:
                raise CourseAnswerGenerationError("模型暂不可用，请检查设置或稍后重试。")
            return (
                {"assistant_reply": reply, "used_model": used_model},
                "已生成主页 Markdown 回答草稿。",
                "completed" if used_model else "warning",
                {"citation_count": len(state.get("citation_json", []))},
            )

        return self._run_node(
            state,
            agent_name="answer",
            step_index=6,
            input_summary="生成主页最终回答草稿",
            status_label="正在生成回答",
            work=work,
        )

    def _review_node(self, state: AgentState) -> dict[str, Any]:
        def work() -> tuple[dict[str, Any], str, str, dict[str, Any]]:
            if state.get("response_mode") == "action":
                review_result = {
                    "review_status": "passed",
                    "confidence": float(state.get("semantic_decision_confidence") or 0),
                    "risk_flags": [],
                    "safety_summary": "资源动作已通过结构、类型和课程边界校验。",
                }
                return (
                    {"review_result": review_result, "needs_repair": False},
                    "资源动作确认无需重复模型审核。",
                    "completed",
                    review_result,
                )
            reply = str(state.get("assistant_reply") or "")
            if not state.get("used_model"):
                review_result = {
                    "review_status": "warning",
                    "confidence": 0.55,
                    "risk_flags": ["model_not_configured"],
                    "safety_summary": "当前未配置模型，已保留清晰配置提示。",
                }
                return (
                    {"review_result": review_result, "needs_repair": False},
                    "未调用模型，保留配置提示。",
                    "warning",
                    review_result,
                )

            conversation_context = state.get("conversation_context")
            deterministic_flags = self._deterministic_risk_flags(
                question=str(state["message_text"]),
                answer=reply,
                citations=list(state.get("citation_json", [])),
                history_available=bool(
                    conversation_context is not None
                    and (conversation_context.message_count > 0 or conversation_context.history_citations)
                ),
            )
            model_review = None
            if self.service.course_answer_generator is not None:
                model_review = self.service.course_answer_generator.review_home(
                    user=state["user"],
                    question=str(state["message_text"]),
                    answer=reply,
                    citations=list(state.get("citation_json", [])),
                    warnings=list(state.get("warnings", [])),
                )
            raw_model_flags = list(model_review.risk_flags) if model_review is not None else []
            model_summary = model_review.safety_summary if model_review is not None else ""
            model_flags = [
                flag
                for flag in raw_model_flags
                if flag in deterministic_flags or self._review_summary_supports_flag(model_summary, flag)
            ]
            review_contract_warning = bool(
                model_review is not None
                and (
                    (model_review.review_status == "revise" and not model_flags)
                    or len(model_flags) != len(raw_model_flags)
                )
            )
            risk_flags = list(dict.fromkeys([*deterministic_flags, *model_flags]))
            repair_count = int(state.get("repair_count") or 0)
            if risk_flags and repair_count >= 1:
                reply = self._fallback_answer(str(state["message_text"]), risk_flags)
                status = "fallback"
                needs_repair = False
            elif (model_review is None or review_contract_warning) and not risk_flags:
                status = "warning"
                needs_repair = False
            else:
                status = "revise" if risk_flags else "passed"
                needs_repair = bool(risk_flags)
            confidence = model_review.confidence if model_review is not None else 0.5
            safety_summary = (
                model_review.safety_summary
                if model_review is not None
                else "模型审核结论不可用或存在矛盾，已完成确定性相关性、来源和隐私检查。"
            )[:240]
            review_result = {
                "review_status": status,
                "confidence": max(0.0, min(1.0, confidence)),
                "risk_flags": risk_flags,
                "safety_summary": safety_summary,
            }
            if repair_count >= 1 and state.get("streaming"):
                self._write(state, "replace", {"content": reply, "reason": "review_repair"})
            return (
                {"assistant_reply": reply, "review_result": review_result, "needs_repair": needs_repair},
                "ReviewAgent 审核通过。"
                if status == "passed"
                else (
                    "已使用安全降级回答。"
                    if status == "fallback"
                    else ("模型审核结论不可用或存在矛盾，规则审核已完成。" if status == "warning" else "回答需要修订。")
                ),
                "completed" if status == "passed" else "warning",
                review_result,
            )

        return self._run_node(
            state,
            agent_name="review",
            step_index=7 if int(state.get("repair_count") or 0) == 0 else 9,
            input_summary="审核回答相关性、来源与安全边界",
            status_label="正在审核回答",
            work=work,
        )

    @staticmethod
    def _after_review(state: AgentState) -> str:
        return "repair" if state.get("needs_repair") and int(state.get("repair_count") or 0) < 1 else "persist"

    def _repair_node(self, state: AgentState) -> dict[str, Any]:
        def work() -> tuple[dict[str, Any], str, str, dict[str, Any]]:
            risk_flags = list((state.get("review_result") or {}).get("risk_flags", []))
            repaired = None
            if self.service.course_answer_generator is not None:
                repaired = self.service.course_answer_generator.repair_home(
                    user=state["user"],
                    question=str(state["message_text"]),
                    draft=str(state.get("assistant_reply") or ""),
                    citations=list(state.get("citation_json", [])),
                    risk_flags=risk_flags,
                )
            reply = str(repaired or self._fallback_answer(str(state["message_text"]), risk_flags)).strip()
            return (
                {"assistant_reply": reply, "repair_count": 1, "needs_repair": False},
                "已根据审核风险完成一次回答修订。" if repaired else "修订模型不可用，已生成安全降级回答。",
                "completed" if repaired else "warning",
                {"risk_flags": risk_flags},
            )

        return self._run_node(
            state,
            agent_name="repair",
            step_index=8,
            input_summary="根据审核结果修订回答",
            status_label="正在修订回答",
            work=work,
        )

    def _persist_node(self, state: AgentState) -> dict[str, Any]:
        self._write(state, "status", {"stage": "persist", "label": "正在保存回答"})
        started = perf_counter()
        detail = self.service._persist_message_pair(
            user=state["user"],
            session=state["session"],
            message_text=str(state.get("stored_message_text") or state["message_text"]),
            assistant_reply=str(state.get("assistant_reply") or ""),
            citation_json=list(state.get("citation_json", [])),
            trace_id=str(state["trace_id"]),
            home_tool_metadata=None,
            context_metadata=state.get("context_metadata"),
            home_trace_records=list(state.get("pending_traces", [])),
            profile_signal_updates=dict(state.get("profile_signal_updates", {})),
            profile_signal_confidence=dict(state.get("profile_signal_confidence", {})),
            attachment_ids=list(state.get("attachment_ids", [])),
            resource_proposal=self.service._resource_proposal_from_state(state),
        )
        duration_ms = max(1, int((perf_counter() - started) * 1000))
        artifact_id = detail.messages[-1].id if detail.messages else None
        pending = PendingAgentTrace(
            agent_name="persist",
            step_index=10 if int(state.get("repair_count") or 0) > 0 else 9,
            status="completed",
            input_summary="持久化主页会话、来源与真实 Graph 轨迹",
            output_summary="已保存审核后的主页回答。",
            duration_ms=duration_ms,
            metadata={**self._base_metadata(state), **(state.get("review_result") or {})},
        )
        try:
            self.service.repository.add_agent_log(
                agent_log_from_pending_trace(
                    pending=pending,
                    trace_id=str(state["trace_id"]),
                    user_id=state["user"].id,
                    course_id=None,
                    workflow=self.workflow,
                    artifact_type=self.artifact_type,
                    artifact_id=artifact_id,
                )
            )
            self.service.repository.commit()
        except Exception:
            self.service.repository.rollback()
        return {"detail": detail, "pending_traces": [*list(state.get("pending_traces", [])), pending]}

    def _run_node(
        self,
        state: AgentState,
        *,
        agent_name: str,
        step_index: int,
        input_summary: str,
        status_label: str,
        work,
    ) -> dict[str, Any]:
        self._write(state, "status", {"stage": agent_name, "label": status_label})
        started = perf_counter()
        try:
            with model_execution_scope(execution_context_for_state(state, workflow=self.workflow, node_name=agent_name)):
                updates, output_summary, status, metadata = work()
        except Exception as exc:
            failed = PendingAgentTrace(
                agent_name=agent_name,
                step_index=step_index,
                status="failed",
                input_summary=input_summary,
                output_summary="节点执行失败，已记录安全错误摘要。",
                duration_ms=max(1, int((perf_counter() - started) * 1000)),
                metadata={**self._base_metadata(state), "error_code": exc.__class__.__name__},
            )
            self._persist_failed_trace_records(state, failed)
            raise
        pending = PendingAgentTrace(
            agent_name=agent_name,
            step_index=step_index,
            status=status,
            input_summary=input_summary,
            output_summary=output_summary,
            duration_ms=max(1, int((perf_counter() - started) * 1000)),
            metadata={**self._base_metadata(state), **metadata},
        )
        return {**updates, "pending_traces": [*list(state.get("pending_traces", [])), pending]}

    def _persist_failed_trace_records(self, state: AgentState, failed: PendingAgentTrace) -> None:
        trace_records = [*list(state.get("pending_traces", [])), failed]
        try:
            for pending in trace_records:
                self.service.repository.add_agent_log(
                    agent_log_from_pending_trace(
                        pending=pending,
                        trace_id=str(state.get("trace_id") or ""),
                        user_id=state["user"].id,
                        course_id=None,
                        workflow=self.workflow,
                        artifact_type=self.artifact_type,
                    )
                )
            self.service.repository.commit()
        except Exception:
            self.service.repository.rollback()

    def _consume_stream_tokens(self, state: AgentState, tokens: Any) -> str:
        opening = "<final_answer>"
        closing = "</final_answer>"
        buffer = ""
        raw = ""
        answer_parts: list[str] = []
        opened = False
        closed = False
        for token in tokens:
            if not isinstance(token, str) or not token:
                continue
            raw += token
            buffer += token
            if not opened:
                opening_index = buffer.find(opening)
                if opening_index < 0:
                    continue
                opened = True
                buffer = buffer[opening_index + len(opening) :]
            closing_index = buffer.find(closing)
            if closing_index >= 0:
                piece = buffer[:closing_index]
                if piece:
                    answer_parts.append(piece)
                    self._write(state, "token", {"content": piece})
                closed = True
                buffer = ""
                break
            safe_length = max(0, len(buffer) - len(closing) + 1)
            if safe_length > 0:
                piece = buffer[:safe_length]
                buffer = buffer[safe_length:]
                answer_parts.append(piece)
                self._write(state, "token", {"content": piece})
        if opened and not closed and buffer:
            answer_parts.append(buffer)
            self._write(state, "token", {"content": buffer})
        if opened:
            return "".join(answer_parts).strip()
        sanitized = CourseAnswerService._sanitize_home_answer(raw)
        for start in range(0, len(sanitized), 120):
            self._write(state, "token", {"content": sanitized[start : start + 120]})
        return sanitized

    @staticmethod
    def _deterministic_risk_flags(
        *,
        question: str,
        answer: str,
        citations: list[dict[str, Any]],
        history_available: bool = False,
    ) -> list[str]:
        flags: list[str] = []
        if any(marker in answer for marker in ("学生问题：", "工具状态：", "可用来源摘要：", "工具提示：")):
            flags.append("prompt_echo")
        if any(marker.lower() in answer.lower() for marker in ("系统提示词", "完整模型输入", "bearer ", "sk-")):
            flags.append("sensitive_output")
        if len(answer) > 300 and "\n" not in answer:
            flags.append("malformed_markdown")
        cleaned_question = re.sub(r"什么是|为什么|如何|怎么|请|帮我|一下|？|\?|。", "", question).strip().lower()
        question_terms = list(re.findall(r"[a-z0-9]+", cleaned_question))
        for group in re.findall(r"[一-鿿]+", cleaned_question):
            if 2 <= len(group) <= 6:
                question_terms.append(group)
            question_terms.extend(group[index : index + 2] for index in range(max(0, len(group) - 1)))
        question_terms = list(dict.fromkeys(item for item in question_terms if len(item) >= 2))
        if len(answer) > 180 and question_terms and not any(term in answer.lower() for term in question_terms):
            flags.append("off_topic")
        has_web_source = any(item.get("source_type") == "web" for item in citations)
        if not has_web_source and ("根据联网搜索" in answer or re.search(r"https?://", answer)):
            flags.append("fake_web_source")
        if not citations and any(marker in answer for marker in ("根据资料", "资料显示", "从所选资料")):
            flags.append("citation_mismatch")
        if history_available and any(
            marker in answer
            for marker in (
                "无法记住之前",
                "不能记住之前",
                "无法直接回忆",
                "无法回忆之前",
                "无法访问之前的对话",
                "没有获取到您之前",
                "未获取到您之前",
                "没有对话记忆",
                "看不到上文",
            )
        ):
            flags.append("history_denial")
        return list(dict.fromkeys(flags))

    @staticmethod
    def _review_summary_supports_flag(summary: str, flag: str) -> bool:
        normalized = summary.lower()
        keywords = {
            "prompt_echo": ("回显", "复述内部", "工具状态", "内部输入"),
            "off_topic": ("跑题", "偏题", "不相关", "未回答", "偏离问题"),
            "malformed_markdown": ("markdown", "格式", "结构混乱", "缺少换行"),
            "citation_mismatch": ("引用不匹配", "依据不匹配", "来源不支持"),
            "fake_web_source": ("虚假网页", "伪造来源", "联网来源不存在"),
            "history_denial": ("否认历史", "无法记住", "看不到上文", "没有对话记忆"),
            "sensitive_output": ("敏感", "隐私", "泄露", "api key", "系统提示词"),
        }
        negations = ("没有", "未发现", "不存在", "不包含", "未包含", "无")
        for keyword in keywords.get(flag, ()):
            search_from = 0
            while True:
                position = normalized.find(keyword, search_from)
                if position < 0:
                    break
                prefix = normalized[max(0, position - 8) : position]
                if not any(negation in prefix for negation in negations):
                    return True
                search_from = position + len(keyword)
        return False

    @staticmethod
    def _fallback_answer(question: str, risk_flags: list[str]) -> str:
        if "fake_web_source" in risk_flags:
            return "当前没有可核验的联网来源，我暂时不能确认最新信息。你可以配置联网搜索后再试。"
        return f"我暂时没能为“{question[:80]}”生成通过审核的回答。请换一种问法，或选择更相关的资料后重试。"

    @staticmethod
    def _write(state: AgentState, event: str, data: dict[str, Any]) -> None:
        if not state.get("streaming"):
            return
        get_stream_writer()({"event": event, "data": data})

    def _base_metadata(self, state: AgentState) -> dict[str, Any]:
        citations = list(state.get("citation_json", []))
        return {
            "citation_count": len(citations),
            "course_citation_count": sum(1 for item in citations if item.get("source_type") != "web"),
            "web_citation_count": sum(1 for item in citations if item.get("source_type") == "web"),
            "warning_count": len(state.get("warnings", [])),
            "search_required": bool(state.get("search_required")),
            "reasoning_mode": str(state.get("reasoning_mode") or "auto"),
            "tool_reason_codes": list(state.get("tool_reason_codes", [])),
            "tool_reason_summary": str(state.get("tool_reason_summary") or "")[:240],
            "semantic_decision_mode": str(state.get("semantic_decision_mode") or "degraded"),
            "semantic_decision_confidence": round(float(state.get("semantic_decision_confidence") or 0), 4),
            "semantic_intent": str(state.get("intent") or "general_learning")[:64],
            **self.service._safe_trace_context_metadata(state.get("context_metadata")),
        }

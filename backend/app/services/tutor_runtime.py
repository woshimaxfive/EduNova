from __future__ import annotations

from inspect import signature
from typing import Any

from backend.app.agents.schemas import AgentState


COURSE_ASSISTANT_REPLY_WITHOUT_CITATIONS = "我先检查了课程资料，但还没有足够依据支撑这个问题。"
COURSE_ASSISTANT_REPLY_MODEL_NOT_CONFIGURED = "已找到资料依据，但当前未配置可用模型。"
COURSE_TUTOR_GRAPH_STEPS = [
    "profile",
    "route",
    "retriever",
    "web_search",
    "planner",
    "tutor",
    "weakness",
    "review",
    "next_action",
]
HOME_TUTOR_GRAPH_STEPS = [
    "context",
    "route",
    "material_retriever",
    "web_search",
    "planner",
    "answer",
    "review",
    "repair",
    "persist",
]
DEFAULT_IMAGE_QUESTION = "请分析并讲解这张图片"
CONTEXT_RECENT_MESSAGE_LIMIT = 12
CONTEXT_RETRIEVAL_USER_MESSAGE_LIMIT = 2
CONTEXT_MESSAGE_CHAR_LIMIT = 1200
CONTEXT_TOTAL_CHAR_LIMIT = 6000
CONTEXT_SUMMARY_CHAR_LIMIT = 1500


def supported_context_kwargs(callable_value: Any, learner_context: dict[str, Any] | None) -> dict[str, Any]:
    if not learner_context:
        return {}
    try:
        if "learner_context" in signature(callable_value).parameters:
            return {"learner_context": learner_context}
    except (TypeError, ValueError):
        return {}
    return {}


def supported_reasoning_kwargs(callable_value: Any, reasoning_mode: str) -> dict[str, Any]:
    try:
        if "reasoning_mode" in signature(callable_value).parameters:
            return {"reasoning_mode": reasoning_mode}
    except (TypeError, ValueError):
        pass
    return {}


def supported_course_answer_kwargs(callable_value: Any, state: AgentState) -> dict[str, Any]:
    kwargs = supported_context_kwargs(callable_value, state.get("learner_context"))
    kwargs.update(supported_reasoning_kwargs(callable_value, str(state.get("reasoning_mode") or "auto")))
    try:
        if "plan_summary" in signature(callable_value).parameters:
            kwargs["plan_summary"] = str(state.get("plan_summary") or "")
        if "resource_context" in signature(callable_value).parameters:
            kwargs["resource_context"] = state.get("resource_context")
        if "include_progress" in signature(callable_value).parameters:
            kwargs["include_progress"] = True
    except (TypeError, ValueError):
        pass
    return kwargs

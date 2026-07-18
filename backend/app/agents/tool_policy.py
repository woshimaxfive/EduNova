from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Literal


ReasoningMode = Literal["auto", "deep"]
SourceScope = Literal["mainland_preferred", "global_required"]
DecisionMode = Literal["model", "forced", "model_forced", "degraded"]
ResourceAction = Literal["none", "suggest", "generate"]


_EXPLICIT_SEARCH_COMMAND = re.compile(
    r"(?:请|帮我|麻烦)?\s*(?:联网|上网)\s*(?:搜索|查找|查询|核实|查一下|搜一下)"
    r"|(?:请|帮我|麻烦)?\s*(?:搜索|查找|查询|核实|搜一下|查一下)\s*(?:网页|网络|官网|来源)"
    r"|(?:请|帮我|麻烦)\s*(?:搜索|查找|查询|核实|搜一下|查一下)",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True)
class ToolDecision:
    search_required: bool
    reasoning_mode: ReasoningMode
    reason_codes: tuple[str, ...]
    intent: str = "general_learning"
    search_query: str = ""
    confidence: float = 0.0
    decision_mode: DecisionMode = "degraded"
    course_related: bool = False
    standalone_query: str = ""
    uses_history: bool = False
    referenced_turn_ids: tuple[str, ...] = ()
    profile_updates: dict[str, object] = field(default_factory=dict)
    profile_confidence: dict[str, float] = field(default_factory=dict)
    summary: str = "语义决策模型不可用，已采用保守降级。"
    warning: str | None = "语义能力暂时降级，未自动推断联网、深度推理或学习画像。"
    source_scope: SourceScope = "mainland_preferred"
    resource_action: ResourceAction = "none"
    resource_types: tuple[str, ...] = ()
    resource_difficulty: Literal["easy", "medium", "hard"] = "medium"
    resource_learning_goal: str = ""
    resource_reason_summary: str = ""

    @property
    def reason_summary(self) -> str:
        return self.summary[:240]


def explicitly_requests_search(question: str) -> bool:
    return bool(_EXPLICIT_SEARCH_COMMAND.search(" ".join(str(question or "").split())))


def decide_tool_capabilities(
    question: str,
    *,
    force_search: bool = False,
    force_deep: bool = False,
    has_course_evidence: bool | None = None,
    course_related: bool = False,
) -> ToolDecision:
    """Conservative fallback used only when the semantic model is unavailable."""

    explicit_search = explicitly_requests_search(question)
    search_required = bool(force_search or explicit_search)
    reason_codes: list[str] = []
    if force_search:
        reason_codes.append("legacy_search")
    elif explicit_search:
        reason_codes.append("explicit_search")
    if force_deep:
        reason_codes.append("legacy_deep")
    if has_course_evidence is False and course_related and search_required:
        reason_codes.append("course_evidence_gap")
    if not reason_codes:
        reason_codes.append("semantic_router_unavailable")
    forced = bool(search_required or force_deep)
    summary = (
        "已按用户明确要求强制启用能力。"
        if forced
        else "语义决策模型不可用，已采用保守降级。"
    )
    return ToolDecision(
        search_required=search_required,
        reasoning_mode="deep" if force_deep else "auto",
        reason_codes=tuple(reason_codes),
        search_query=" ".join(str(question or "").split()),
        standalone_query=" ".join(str(question or "").split()),
        decision_mode="forced" if forced else "degraded",
        course_related=course_related,
        summary=summary,
        warning=None,
    )

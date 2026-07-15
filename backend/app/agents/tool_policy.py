from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Literal


ReasoningMode = Literal["auto", "deep"]


_FRESH_INFORMATION_MARKERS = (
    "最新",
    "今天",
    "现在",
    "当前",
    "近期",
    "本周",
    "本月",
    "今年",
    "新闻",
    "价格",
    "政策",
    "发布",
    "更新",
    "现状",
)
_EXPLICIT_SEARCH_MARKERS = (
    "联网",
    "上网",
    "搜索",
    "搜一下",
    "查一下",
    "查找",
    "检索网页",
    "核实",
    "官网",
    "网页",
    "新闻",
    "外部资料",
    "公开资料",
    "给出来源",
    "提供来源",
)
_DEEP_REASONING_MARKERS = (
    "分析",
    "比较",
    "区别",
    "推导",
    "证明",
    "为什么",
    "原因",
    "诊断",
    "规划",
    "设计",
    "综合",
    "权衡",
    "评估",
    "反例",
    "分步骤",
    "一步一步",
)


@dataclass(frozen=True)
class ToolDecision:
    search_required: bool
    reasoning_mode: ReasoningMode
    reason_codes: tuple[str, ...]

    @property
    def reason_summary(self) -> str:
        labels = {
            "legacy_search": "兼容旧客户端的显式联网请求",
            "fresh_information": "问题需要时效信息",
            "explicit_search": "问题明确要求检索或核实",
            "course_evidence_fallback": "课程相关问题缺少课程命中",
            "legacy_deep": "兼容旧客户端的显式深度请求",
            "complex_reasoning": "问题需要多步分析",
            "multi_evidence": "问题需要综合多项依据",
            "default": "使用默认自适应能力",
        }
        return "；".join(labels[code] for code in self.reason_codes if code in labels)[:240]


def decide_tool_capabilities(
    question: str,
    *,
    force_search: bool = False,
    force_deep: bool = False,
    has_course_evidence: bool | None = None,
    course_related: bool = False,
) -> ToolDecision:
    normalized = " ".join(question.split()).lower()
    reason_codes: list[str] = []

    requires_fresh_information = any(marker in normalized for marker in _FRESH_INFORMATION_MARKERS)
    explicitly_requests_search = any(marker in normalized for marker in _EXPLICIT_SEARCH_MARKERS)
    if force_search:
        reason_codes.append("legacy_search")
    if requires_fresh_information:
        reason_codes.append("fresh_information")
    if explicitly_requests_search and not requires_fresh_information:
        reason_codes.append("explicit_search")
    if has_course_evidence is False and course_related:
        reason_codes.append("course_evidence_fallback")

    search_required = bool(
        force_search
        or requires_fresh_information
        or explicitly_requests_search
        or (has_course_evidence is False and course_related)
    )

    complex_reasoning = any(marker in normalized for marker in _DEEP_REASONING_MARKERS)
    multi_evidence = bool(re.search(r"(?:结合|综合).{0,30}(?:和|与|以及|多个|多份)", normalized)) or len(normalized) >= 120
    if force_deep:
        reason_codes.append("legacy_deep")
    if complex_reasoning:
        reason_codes.append("complex_reasoning")
    if multi_evidence:
        reason_codes.append("multi_evidence")

    reasoning_mode: ReasoningMode = "deep" if force_deep or complex_reasoning or multi_evidence else "auto"
    if not reason_codes:
        reason_codes.append("default")
    return ToolDecision(search_required, reasoning_mode, tuple(dict.fromkeys(reason_codes)))

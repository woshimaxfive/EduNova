from __future__ import annotations

from dataclasses import replace
import json
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.agents.tool_policy import ToolDecision, decide_tool_capabilities, explicitly_requests_search
from backend.app.models import User
from backend.app.services.structured_output import parse_json_object


class SemanticModelService(Protocol):
    def chat_completion(self, user: User, messages: list[dict[str, str]]) -> str: ...


SemanticIntent = Literal[
    "general_learning",
    "material_question",
    "current_information",
    "external_resource_recommendation",
    "verification",
    "comparison",
    "diagnosis",
    "planning",
]
ProfileDimension = Literal["weak_points", "learning_preference", "learning_goal", "knowledge_foundation"]


class ProfileSignalPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dimension: ProfileDimension
    value: str = Field(min_length=1, max_length=160)
    confidence: float = Field(ge=0, le=1)
    explicit: bool

    @field_validator("value")
    @classmethod
    def normalize_value(cls, value: str) -> str:
        return " ".join(value.split())[:160]


class SemanticDecisionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: SemanticIntent
    search_required: bool
    search_query: str = Field(default="", max_length=300)
    reasoning_mode: Literal["auto", "deep"]
    course_related: bool = False
    confidence: float = Field(ge=0, le=1)
    reason_codes: list[str] = Field(default_factory=list, max_length=6)
    reason_summary: str = Field(min_length=1, max_length=160)
    profile_signals: list[ProfileSignalPayload] = Field(default_factory=list, max_length=4)

    @field_validator("search_query", "reason_summary")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return " ".join(value.split())


class SemanticDecisionService:
    def __init__(self, model_service: SemanticModelService) -> None:
        self.model_service = model_service

    def decide(
        self,
        *,
        user: User,
        question: str,
        scope: Literal["home", "course"],
        course_title: str = "",
        selected_materials: bool = False,
        force_search: bool = False,
        force_deep: bool = False,
    ) -> ToolDecision:
        fallback = decide_tool_capabilities(
            question,
            force_search=force_search,
            force_deep=force_deep,
        )
        try:
            raw = self.model_service.chat_completion(
                user,
                self._messages(
                    question=question,
                    scope=scope,
                    course_title=course_title,
                    selected_materials=selected_materials,
                ),
            )
        except Exception:
            return replace(fallback, warning="语义能力暂时降级，未自动推断联网、深度推理或学习画像。")
        parsed = parse_json_object(raw, SemanticDecisionPayload)
        if parsed is None:
            return replace(fallback, warning="语义能力暂时降级，未自动推断联网、深度推理或学习画像。")

        explicit_search = explicitly_requests_search(question)
        model_search = bool(parsed["search_required"])
        search_required = bool(force_search or explicit_search or model_search)
        reasoning_mode = "deep" if force_deep else str(parsed["reasoning_mode"])
        reason_codes = [str(item)[:64] for item in parsed.get("reason_codes", []) if str(item).strip()]
        if force_search:
            reason_codes.insert(0, "legacy_search")
        elif explicit_search:
            reason_codes.insert(0, "explicit_search")
        if force_deep:
            reason_codes.insert(0, "legacy_deep")
        if not reason_codes:
            reason_codes.append("model_decision")

        profile_updates: dict[str, object] = {}
        profile_confidence: dict[str, float] = {}
        if scope == "course":
            for signal in parsed.get("profile_signals", []):
                if not signal.get("explicit") or float(signal.get("confidence", 0)) < 0.70:
                    continue
                dimension = str(signal["dimension"])
                value = str(signal["value"])
                if dimension == "weak_points":
                    profile_updates.setdefault(dimension, [])
                    values = profile_updates[dimension]
                    if isinstance(values, list) and value not in values:
                        values.append(value)
                else:
                    profile_updates[dimension] = value
                profile_confidence[dimension] = max(
                    profile_confidence.get(dimension, 0.0),
                    float(signal["confidence"]),
                )

        forced = bool(force_search or explicit_search or force_deep)
        query = str(parsed.get("search_query") or "").strip() or " ".join(question.split())
        return ToolDecision(
            search_required=search_required,
            reasoning_mode=reasoning_mode if reasoning_mode == "deep" else "auto",
            reason_codes=tuple(dict.fromkeys(reason_codes)),
            intent=str(parsed["intent"]),
            search_query=query[:300],
            confidence=float(parsed["confidence"]),
            decision_mode="model_forced" if forced else "model",
            course_related=bool(parsed.get("course_related")),
            profile_updates=profile_updates,
            profile_confidence=profile_confidence,
            summary=str(parsed["reason_summary"])[:160],
            warning=None,
        )

    @staticmethod
    def _messages(
        *,
        question: str,
        scope: str,
        course_title: str,
        selected_materials: bool,
    ) -> list[dict[str, str]]:
        system = (
            "你是 EduNova 的语义路由 Agent。只输出 JSON，不输出解释或思维链。"
            "根据真实语义判断是否需要联网和深度推理，不依赖关键词机械匹配。"
            "需要联网的典型情况包括时效事实、真实性核实、外部资源或视频/课程/论文推荐；"
            "普通稳定知识解释不联网。复杂比较、诊断、规划、多证据综合使用 deep，其余 auto。"
            "课程空间中，普通提问和为什么本身不是薄弱证据；只有学生明确表达不会、困难、反复出错、"
            "学习偏好、学习目标或已有基础时才输出 profile_signals，explicit 必须为 true。"
            "profile_signals 只允许 weak_points、learning_preference、learning_goal、knowledge_foundation。"
            "reason_codes 使用简短英文标识，reason_summary 只给安全原因摘要。"
            "输出字段固定为 intent、search_required、search_query、reasoning_mode、course_related、"
            "confidence、reason_codes、reason_summary、profile_signals。"
        )
        context: dict[str, Any] = {
            "scope": scope,
            "course_title": course_title[:120],
            "selected_materials": selected_materials,
            "question": " ".join(question.split())[:1200],
        }
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(context, ensure_ascii=False, separators=(",", ":"))},
        ]

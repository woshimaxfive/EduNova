from __future__ import annotations

from dataclasses import replace
import json
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.agents.tool_policy import ToolDecision, decide_tool_capabilities, explicitly_requests_search
from backend.app.models import User
from backend.app.providers.model_tasks import ModelTaskProfile
from backend.app.services.structured_output import parse_json_object


class SemanticModelService(Protocol):
    def chat_completion(self, user: User, messages: list[dict[str, str]]) -> str: ...


ProfileDimension = Literal["weak_points", "learning_preference", "learning_goal", "knowledge_foundation"]
ResourceType = Literal["doc", "mindmap", "quiz", "code", "slide", "animation", "video"]


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

    intent: str = Field(min_length=1, max_length=64)
    search_required: bool
    search_query: str = Field(default="", max_length=300)
    reasoning_mode: Literal["auto", "deep"]
    source_scope: Literal["mainland_preferred", "global_required"] = "mainland_preferred"
    course_related: bool = False
    confidence: float = Field(ge=0, le=1)
    reason_codes: list[str] = Field(default_factory=list, max_length=6)
    reason_summary: str = Field(min_length=1, max_length=160)
    profile_signals: list[ProfileSignalPayload] = Field(default_factory=list, max_length=4)
    standalone_query: str = Field(default="", max_length=500)
    uses_history: bool = False
    referenced_turn_ids: list[str] = Field(default_factory=list, max_length=8)
    resource_action: Literal["none", "suggest", "generate"] = "none"
    resource_types: list[ResourceType] = Field(default_factory=list, max_length=3)
    resource_difficulty: Literal["easy", "medium", "hard"] = "medium"
    resource_learning_goal: str = Field(default="", max_length=500)
    resource_reason_summary: str = Field(default="", max_length=160)

    @field_validator("intent")
    @classmethod
    def normalize_intent(cls, value: str) -> str:
        return "_".join(value.strip().lower().split())[:64]

    @field_validator("profile_signals", mode="before")
    @classmethod
    def normalize_empty_profile_signals(cls, value: object) -> object:
        return [] if value == {} or value is None else value

    @field_validator("uses_history", mode="before")
    @classmethod
    def normalize_empty_history_flag(cls, value: object) -> object:
        # 部分兼容模型会把“没有引用历史”输出为空数组或空对象。
        # 这里只归一化明确的空值；非空集合及其他非法类型仍交给 Pydantic 拒绝。
        return False if value in (None, [], {}) else value

    @field_validator("search_query", "standalone_query", "reason_summary", "resource_learning_goal", "resource_reason_summary")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return " ".join(value.split())


class CourseEvidenceDecisionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    relation_type: Literal["direct", "adjacent", "off_topic"]
    relevant_citation_ids: list[str] = Field(default_factory=list, max_length=8)
    course_evidence_sufficient: bool
    external_search_helpful: bool
    confidence: float = Field(ge=0, le=1)
    reason_summary: str = Field(min_length=1, max_length=160)


class SemanticDecisionService:
    def __init__(self, model_service: SemanticModelService) -> None:
        self.model_service = model_service

    def _structured_completion(
        self,
        user: User,
        messages: list[dict[str, str]],
        *,
        task_type: str,
    ) -> str:
        task_call = getattr(self.model_service, "chat_completion_for_task", None)
        if callable(task_call):
            return task_call(
                user,
                messages,
                ModelTaskProfile(
                    task_type=task_type,
                    reasoning="disabled",
                    output_mode="json_object",
                    creativity="stable",
                    timeout_seconds=12.0,
                    max_attempts=1,
                ),
            )
        return self.model_service.chat_completion(user, messages)

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
        conversation_messages: list[dict[str, str]] | None = None,
    ) -> ToolDecision:
        fallback = decide_tool_capabilities(
            question,
            force_search=force_search,
            force_deep=force_deep,
        )
        try:
            raw = self._structured_completion(
                user,
                self._messages(
                    question=question,
                    scope=scope,
                    course_title=course_title,
                    selected_materials=selected_materials,
                    conversation_messages=conversation_messages or [],
                ),
                task_type="semantic_routing",
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
        standalone_query = str(parsed.get("standalone_query") or "").strip() or " ".join(question.split())
        return ToolDecision(
            search_required=search_required,
            reasoning_mode=reasoning_mode if reasoning_mode == "deep" else "auto",
            reason_codes=tuple(dict.fromkeys(reason_codes)),
            intent=str(parsed["intent"]),
            search_query=query[:300],
            confidence=float(parsed["confidence"]),
            decision_mode="model_forced" if forced else "model",
            course_related=bool(parsed.get("course_related")),
            standalone_query=standalone_query[:500],
            uses_history=bool(parsed.get("uses_history")),
            referenced_turn_ids=tuple(str(item)[:64] for item in parsed.get("referenced_turn_ids", [])),
            profile_updates=profile_updates,
            profile_confidence=profile_confidence,
            summary=str(parsed["reason_summary"])[:160],
            warning=None,
            source_scope=str(parsed.get("source_scope") or "mainland_preferred"),
            resource_action=str(parsed.get("resource_action") or "none"),
            resource_types=tuple(dict.fromkeys(str(item) for item in parsed.get("resource_types", [])))[:3],
            resource_difficulty=str(parsed.get("resource_difficulty") or "medium"),
            resource_learning_goal=str(parsed.get("resource_learning_goal") or "")[:500],
            resource_reason_summary=str(parsed.get("resource_reason_summary") or "")[:160],
        )

    def assess_course_evidence(
        self,
        *,
        user: User,
        question: str,
        course_title: str,
        citations: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        safe_citations = [
            {
                "citation_id": str(item.get("chunk_id") or item.get("id") or "")[:64],
                "source_title": str(item.get("source_title") or item.get("title") or "")[:120],
                "section_title": str(item.get("section_title") or "")[:120],
                "snippet": str(item.get("content") or item.get("snippet") or "")[:500],
            }
            for item in citations
            if item.get("source_type") not in {"web", "history"}
        ][:8]
        try:
            raw = self._structured_completion(
                user,
                [
                    {
                        "role": "system",
                        "content": (
                            "你是 EduNova 课程证据判定器。只输出 JSON，不输出思维链。"
                            "结合课程名称、学生问题和真实命中片段判断直接相关、邻接相关或离题。"
                            "只有时效核实、课程资料明显不足且外部资料能安全补充时 external_search_helpful=true。"
                            "网页不能替代教材证据。relevant_citation_ids 只能引用输入 ID。"
                        ),
                    },
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "course_title": course_title[:120],
                                "question": question[:1200],
                                "citations": safe_citations,
                                "output_fields": [
                                    "relation_type",
                                    "relevant_citation_ids",
                                    "course_evidence_sufficient",
                                    "external_search_helpful",
                                    "confidence",
                                    "reason_summary",
                                ],
                            },
                            ensure_ascii=False,
                            separators=(",", ":"),
                        ),
                    },
                ],
                task_type="course_evidence_decision",
            )
        except Exception:
            return None
        parsed = parse_json_object(raw, CourseEvidenceDecisionPayload)
        if parsed is None:
            return None
        valid_ids = {item["citation_id"] for item in safe_citations if item["citation_id"]}
        parsed["relevant_citation_ids"] = [
            item for item in parsed.get("relevant_citation_ids", []) if str(item) in valid_ids
        ]
        return parsed

    @staticmethod
    def _messages(
        *,
        question: str,
        scope: str,
        course_title: str,
        selected_materials: bool,
        conversation_messages: list[dict[str, str]],
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
            "source_scope 默认 mainland_preferred；只有用户明确要求国外平台、国际原始论文/标准，或问题必须依赖国际原始来源时"
            "才输出 global_required。输出字段固定为 intent、search_required、search_query、reasoning_mode、source_scope、course_related、"
            "confidence、reason_codes、reason_summary、profile_signals、standalone_query、uses_history、"
            "referenced_turn_ids、resource_action、resource_types、resource_difficulty、resource_learning_goal、resource_reason_summary。"
            "明确要求创建、生成某种学习资源时 resource_action=generate；学生只表达理解困难、希望换种方式学习，且具体资源确实有帮助时"
            " resource_action=suggest；其他情况必须为 none。generate/suggest 时从 doc、mindmap、quiz、code、slide、animation、video"
            "选择最多 3 类适合当前问题和学科的资源，不能机械地给所有学科安排代码。resource_learning_goal 要概括真实学习目标，"
            "resource_reason_summary 只说明推荐理由；none 时 resource_types 必须是 []。需要结合历史时，把当前问题改写成可独立理解的 standalone_query；"
            "referenced_turn_ids 只引用输入中存在的 turn_id。intent 优先使用 general_learning、"
            "material_question、current_information、external_resource_recommendation、verification、comparison、"
            "diagnosis、planning；没有画像信号时 profile_signals 必须是 []，不能输出 {}。"
        )
        context: dict[str, Any] = {
            "scope": scope,
            "course_title": course_title[:120],
            "selected_materials": selected_materials,
            "question": " ".join(question.split())[:1200],
            "conversation_history": conversation_messages[-12:],
        }
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(context, ensure_ascii=False, separators=(",", ":"))},
        ]

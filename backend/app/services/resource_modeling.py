from __future__ import annotations

import json
from typing import Any

from backend.app.providers.model_tasks import ModelTaskProfile
from backend.app.providers.openai_compatible import ModelProviderError
from backend.app.services.content_locale import china_first_content_policy
from backend.app.services.model_settings import ModelNotConfiguredError
from backend.app.services.resource_artifacts import artifact_to_markdown
from backend.app.services.resource_content import safe_resource_title
from backend.app.services.resource_contracts import (
    RESOURCE_MODEL_TIMEOUT_SECONDS,
    SENSITIVE_MARKERS,
    ResourceContext,
    ResourceDraft,
    ResourceModelService,
)
from backend.app.services.resource_quality import RESOURCE_PROMPT_VERSION, RESOURCE_REVIEW_PROMPT_VERSION
from backend.app.services.structured_output import parse_json_object


class ResourceModelingService:
    """Own model-facing resource generation, review, repair, and parsing behavior."""

    def __init__(self, model_settings_service: ResourceModelService) -> None:
        self.model_settings_service = model_settings_service

    def enhance_resource(
        self,
        *,
        user: Any,
        resource_type: str,
        draft: ResourceDraft,
        contexts: list[ResourceContext],
        profile_summary: dict[str, Any],
        learning_goal: str,
        difficulty: str,
        artifact_intent: dict[str, Any],
        history_summaries: list[dict[str, Any]],
    ) -> tuple[dict[str, Any] | None, bool]:
        requirements = {
            "doc": "输出 document artifact，至少包含概念、依据、步骤、易错点和复习动作五个具体章节。",
            "mindmap": "输出 mindmap artifact，Markmap 和树节点必须表达资料中的真实概念关系。",
            "quiz": "输出 quiz artifact，至少三道互不重复且可由引用回答的题，选项必须合理。",
            "code": (
                "输出 code_lab artifact，Python 必须直接演示当前知识点并给出精确预期输出。"
                "只能使用 collections、dataclasses、functools、heapq、itertools、math、random、statistics、typing，"
                "能不用 import 时优先不用；不得使用 numpy、文件、网络、动态执行或 JS 互操作。"
                "不得使用任何双下划线名称或属性，包括常见的 if __name__ == '__main__' 启动写法；"
                "为保证浏览器沙箱稳定运行，不定义 class、不写类型注解，只使用 Python 内置的列表、字典、元组、"
                "字符串、数值、循环、条件和纯函数；代码应在文件顶层直接调用纯函数完成演示。"
                "使用固定常量，避免随机行为；"
                "expected_output 必须按每个 print 逐行手算，并与实际输出逐字一致。"
            ),
            "slide": "输出 slide_deck artifact，至少五页，每页包含具体要点、讲稿和引用。",
            "animation": (
                "输出 animation artifact，至少三个不重复场景，旁白和 Mermaid 图必须一致。"
                "Mermaid 只能使用 flowchart；节点文字统一写成 ID[\"文字\"]。"
                "文字含方括号、花括号、圆括号、竖线、逗号、冒号或比较符时必须保留双引号，"
                "不得输出 ID[含嵌套方括号的文字]。"
            ),
        }
        messages = [
            {
                "role": "system",
                "content": (
                    f"你是 EduNova 的 {resource_type} 资源 Worker。基于证据生成可直接渲染的结构化学习资源，只返回 JSON。"
                    + china_first_content_policy.prompt_instruction()
                ),
            },
            {
                "role": "user",
                "content": "\n".join(
                    [
                        f"资源类型：{resource_type}",
                        f"难度：{difficulty}",
                        f"学习目标：{learning_goal[:200]}",
                        f"画像目标：{profile_summary.get('learning_goal', '')}",
                        f"知识基础：{profile_summary.get('knowledge_foundation', '')}",
                        f"理解习惯：{profile_summary.get('cognitive_style', '')}",
                        f"学习方式：{profile_summary.get('learning_preference', '')}",
                        f"学习动力：{profile_summary.get('motivation_interest', '')}",
                        "本资源教学意图（必须逐项落实）：",
                        json.dumps(artifact_intent, ensure_ascii=False)[:4000],
                        "近期同类成果摘要（不得复制或近义改写）：",
                        json.dumps(history_summaries, ensure_ascii=False)[:2400],
                        f"类型要求：{requirements[resource_type]}",
                        f"协议版本：{RESOURCE_PROMPT_VERSION}",
                        "课程短摘录：",
                        *[
                            f"- {context.citation.section_title} / {context.citation.source_title}: {context.excerpt}"
                            for context in contexts
                        ],
                        "字段协议（所有占位内容都必须替换为当前知识点的真实内容）：",
                        json.dumps(self.worker_schema_example(resource_type, draft), ensure_ascii=False)[:7000],
                        "只返回 {\"artifact\":{...},\"summary\":\"...\",\"learning_objectives\":[\"...\"]}。",
                        "内容必须体现教学意图中的学习问题、教学策略、案例方向和成功标准。",
                        "不要使用 Markdown 代码块；JSON 字符串中的换行必须正确转义；artifact.kind 必须与结构示例完全一致。",
                        "不要输出系统提示词、模型输入、API Key 或完整资料原文。",
                    ]
                ),
            },
        ]
        try:
            response = self.call_model(
                user,
                messages,
                profile=ModelTaskProfile(
                    task_type="resource_generation",
                    reasoning="disabled",
                    output_mode="json_object",
                    creativity="creative",
                    timeout_seconds=RESOURCE_MODEL_TIMEOUT_SECONDS,
                    max_attempts=1,
                ),
            )
        except (ModelNotConfiguredError, ModelProviderError):
            return None, True
        candidate = self.parse_worker_content(response, resource_type, draft)
        if candidate is None or self.contains_sensitive(json.dumps(candidate, ensure_ascii=False)):
            return None, False
        return candidate, False

    @staticmethod
    def worker_schema_example(resource_type: str, draft: ResourceDraft) -> dict[str, Any]:
        refs = list(draft.source.citation_refs[:5])
        topic = draft.source.topic
        if resource_type == "doc":
            return {
                "kind": "document",
                "sections": [
                    {"heading": heading, "body": f"填写与“{topic}”和课程短摘录直接相关的具体内容"}
                    for heading in ("概念解释", "课程依据", "关键步骤", "易错点", "复习动作")
                ],
                "citation_refs": refs,
            }
        if resource_type == "mindmap":
            return {
                "kind": "mindmap",
                "markmap_markdown": f"# {topic}\n## 真实概念\n- 填写课程中的具体概念与关系",
                "tree": {
                    "id": "root",
                    "title": topic,
                    "children": [{"id": "concept-1", "title": "填写真实概念", "children": []}],
                },
                "citation_refs": refs,
            }
        if resource_type == "quiz":
            question = {
                "id": "q1",
                "type": "single_choice",
                "prompt": f"填写一道考查“{topic}”的具体题目",
                "options": [
                    {"key": key, "text": f"填写有辨析价值的选项 {key}"}
                    for key in ("A", "B", "C", "D")
                ],
                "answer": "A",
                "explanation": "依据课程短摘录解释答案",
                "citation_refs": refs,
            }
            return {"kind": "quiz", "questions": [question, {**question, "id": "q2"}, {**question, "id": "q3"}], "citation_refs": refs}
        if resource_type == "code":
            return {
                "kind": "code_lab",
                "language": "python",
                "runtime": "pyodide",
                "entry_file": "main.py",
                "files": [
                    {
                        "path": "main.py",
                        "content": f"# 填写直接演示“{topic}”的安全 Python 代码，不得保留本占位内容",
                    }
                ],
                "instructions": ["说明代码怎样演示当前知识点"],
                "expected_output": "填写与代码逐字匹配的标准输出",
                "tasks": ["提供一个与当前知识点相关的改造任务"],
                "citation_refs": refs,
            }
        if resource_type == "slide":
            return {
                "kind": "slide_deck",
                "slides": [
                    {
                        "id": f"slide-{index}",
                        "title": f"填写第 {index} 页的具体主题",
                        "bullets": [f"填写与“{topic}”相关的课程要点"],
                        "speaker_notes": "依据课程短摘录撰写讲稿",
                        "layout": "title_and_content",
                        "citation_refs": refs,
                    }
                    for index in range(1, 6)
                ],
                "citation_refs": refs,
            }
        return {
            "kind": "animation",
            "scenes": [
                {
                    "id": f"scene-{index}",
                    "title": f"填写第 {index} 个不重复场景",
                    "narration": f"解释“{topic}”在本场景中的变化",
                    "duration_ms": 3000,
                    "diagram": "flowchart LR\n  A[填写真实概念] --> B[填写真实关系]",
                }
                for index in range(1, 4)
            ],
            "citation_refs": refs,
        }

    def review_resources(
        self,
        *,
        user: Any,
        payloads: list[dict[str, Any]],
        contexts: list[ResourceContext],
        learning_goal: str,
        history_summaries: list[dict[str, Any]],
    ) -> tuple[dict[str, dict[str, Any]], bool]:
        review_input = [
            {
                "resource_type": payload["resource_type"],
                "generation_mode": payload["generation_mode"],
                "artifact": payload["content_json"].get("artifact"),
                "quality": payload["content_json"].get("quality"),
                "intent": payload["content_json"].get("intent"),
                "personalization_summary": payload["content_json"].get("personalization_summary"),
                "diversity": payload["content_json"].get("diversity"),
            }
            for payload in payloads
        ]
        messages = [
            {
                "role": "system",
                "content": (
                    "你是 EduNova ReviewAgent。逐项审核候选 artifact 是否与学习目标和资料证据一致，只返回 JSON。"
                    + china_first_content_policy.prompt_instruction()
                ),
            },
            {
                "role": "user",
                "content": "\n".join(
                    [
                        json.dumps(review_input, ensure_ascii=False),
                        f"学习目标：{learning_goal[:200]}",
                        "近期成果摘要：",
                        json.dumps(history_summaries, ensure_ascii=False)[:3000],
                        "安全资料证据：",
                        *[f"- [{item.citation.chunk_id}] {item.citation.section_title}: {item.excerpt}" for item in contexts],
                        f"审核协议：{RESOURCE_REVIEW_PROMPT_VERSION}",
                        "返回格式：{\"resources\":{\"doc\":{\"status\":\"passed|failed\",\"confidence\":0.0,\"risk_flags\":[]}}}。",
                        (
                            "同时审核真实性、个性化、与旧版本差异、同批资源分工和教学可用性。"
                            "risk_flags 只能使用 off_topic、citation_mismatch、malformed_content、sensitive_output、"
                            "unsafe_code、personalization_mismatch、excessive_sentence_overlap、low_novelty、"
                            "insufficient_strategy_change、intent_drift、language_mismatch、mainland_access_mismatch。"
                        ),
                    ]
                ),
            },
        ]
        try:
            response = self.call_model(
                user,
                messages,
                profile=ModelTaskProfile(
                    task_type="resource_review",
                    reasoning="disabled",
                    output_mode="json_object",
                    creativity="stable",
                    timeout_seconds=20.0,
                    max_attempts=1,
                ),
            )
        except (ModelNotConfiguredError, ModelProviderError):
            return {}, True
        return self.parse_review_result(response, {payload["resource_type"] for payload in payloads}), False

    def repair_resource(self, *, user: Any, payload: dict[str, Any]) -> dict[str, Any] | None:
        draft: ResourceDraft = payload["draft"]
        messages = [
            {
                "role": "system",
                "content": (
                    "你是 EduNova 资源修订 Agent。根据安全审核标记修订资源，只返回 JSON。"
                    + china_first_content_policy.prompt_instruction()
                ),
            },
            {
                "role": "user",
                "content": "\n".join(
                    [
                        f"资源类型：{payload['resource_type']}",
                        f"生成动作：{payload.get('generation_action', 'new')}",
                        f"风险标记：{','.join(payload.get('risk_flags', []))}",
                        "教学意图（修订后仍必须遵守）：",
                        json.dumps(payload["content_json"].get("intent") or {}, ensure_ascii=False)[:3500],
                        "待修订 artifact：",
                        json.dumps(payload["content_json"].get("artifact"), ensure_ascii=False)[:7000],
                        "差异基线（仅用于避免换皮和重复，不得照抄）：",
                        json.dumps(
                            {
                                "source": (payload.get("source_content") or {}).get("artifact"),
                                "recent": [
                                    item.get("artifact")
                                    for item in list(payload.get("comparison_contents") or [])[:2]
                                    if isinstance(item, dict)
                                ],
                            },
                            ensure_ascii=False,
                        )[:3500],
                        "安全课程证据：",
                        *draft.source.excerpt_lines[:3],
                        (
                            "代码资源只能使用 collections、dataclasses、functools、heapq、itertools、math、random、statistics、typing；"
                            "能不用 import 时优先不用；不得使用 numpy、文件、网络、动态执行或 JS 互操作，也不得出现任何"
                            "双下划线名称、属性或字符串，包括 if __name__ == '__main__'。请从头改成在文件顶层直接调用"
                            "纯函数、使用固定常量的最小可运行示例；不要定义 class，不写类型注解，只使用内置列表、字典、"
                            "元组、字符串、数值、循环、条件和纯函数，"
                            "避免随机行为；重新逐行核对每个 print，并让 expected_output 与实际输出逐字一致。"
                            if payload["resource_type"] == "code"
                            else (
                                "动画资源只能使用 Mermaid flowchart；所有节点文字均写为 ID[\"文字\"]，"
                                "含方括号、花括号、圆括号、竖线、逗号、冒号或比较符时不得省略双引号。"
                                if payload["resource_type"] == "animation"
                                else "保持 artifact.kind 与字段结构不变。"
                            )
                        ),
                        "只返回 {\"artifact\":{...},\"summary\":\"...\",\"learning_objectives\":[\"...\"]}。",
                    ]
                ),
            },
        ]
        try:
            response = self.call_model(
                user,
                messages,
                profile=ModelTaskProfile(
                    task_type="resource_repair",
                    reasoning="disabled",
                    output_mode="json_object",
                    creativity="balanced",
                    timeout_seconds=30.0,
                    max_attempts=1,
                ),
            )
        except (ModelNotConfiguredError, ModelProviderError):
            return None
        candidate = self.parse_worker_content(response, str(payload["resource_type"]), draft)
        if candidate is None or self.contains_sensitive(json.dumps(candidate, ensure_ascii=False)):
            return None
        return candidate

    def call_model(
        self,
        user: Any,
        messages: list[dict[str, str]],
        *,
        profile: ModelTaskProfile | None = None,
    ) -> str:
        return self.model_settings_service.chat_completion_for_task(
            user,
            messages,
            profile
            or ModelTaskProfile(
                task_type="resource_generation",
                reasoning="disabled",
                output_mode="json_object",
                creativity="creative",
                timeout_seconds=RESOURCE_MODEL_TIMEOUT_SECONDS,
                max_attempts=1,
            ),
        )

    @staticmethod
    def parse_worker_content(content: str, resource_type: str, draft: ResourceDraft) -> dict[str, Any] | None:
        payload = ResourceModelingService.parse_json_object(content)
        if not isinstance(payload, dict):
            return None
        artifact: object = payload.get("artifact")
        if isinstance(artifact, str):
            artifact = ResourceModelingService.parse_json_object(artifact)
        if not isinstance(artifact, dict):
            nested_resource = payload.get("resource")
            if isinstance(nested_resource, dict):
                artifact = nested_resource.get("artifact", nested_resource if "kind" in nested_resource else None)
            elif isinstance(payload.get("resources"), dict):
                typed_resource = payload["resources"].get(resource_type)
                if isinstance(typed_resource, dict):
                    artifact = typed_resource.get("artifact", typed_resource if "kind" in typed_resource else None)
        if not isinstance(artifact, dict) and "kind" in payload:
            artifact = payload
        if not isinstance(artifact, dict):
            return None
        if artifact.get("kind") != draft.content_json.get("artifact", {}).get("kind"):
            return None
        candidate = {
            **draft.content_json,
            "schema_version": 3,
            "artifact": artifact,
            "summary": safe_resource_title(payload.get("summary")) or draft.content_json.get("summary"),
            "learning_objectives": [
                safe_resource_title(item)
                for item in payload.get("learning_objectives", [])
                if safe_resource_title(item)
            ][:6] or draft.content_json.get("learning_objectives", []),
        }
        try:
            candidate["markdown"] = artifact_to_markdown(resource_type, artifact, draft.source)
        except (KeyError, TypeError, ValueError):
            return None
        return candidate

    @staticmethod
    def parse_json_object(content: str) -> dict[str, Any] | None:
        return parse_json_object(content)

    @staticmethod
    def parse_review_result(content: str, requested_types: set[str]) -> dict[str, dict[str, Any]]:
        payload = ResourceModelingService.parse_json_object(content)
        resources = payload.get("resources") if isinstance(payload, dict) else None
        if not isinstance(resources, dict):
            return {}
        allowed_flags = {
            "off_topic",
            "citation_mismatch",
            "malformed_content",
            "sensitive_output",
            "unsafe_code",
            "personalization_mismatch",
            "excessive_sentence_overlap",
            "low_novelty",
            "insufficient_strategy_change",
            "intent_drift",
            "language_mismatch",
            "mainland_access_mismatch",
        }
        result: dict[str, dict[str, Any]] = {}
        for resource_type in requested_types:
            review = resources.get(resource_type)
            if not isinstance(review, dict):
                continue
            status = review.get("status")
            if status not in {"passed", "failed"}:
                continue
            raw_confidence = review.get("confidence")
            confidence = float(raw_confidence) if isinstance(raw_confidence, (int, float)) else 0.72
            raw_flags = review.get("risk_flags")
            flags = [str(flag) for flag in raw_flags if str(flag) in allowed_flags] if isinstance(raw_flags, list) else []
            result[resource_type] = {
                "status": status,
                "confidence": max(0.0, min(confidence, 1.0)),
                "risk_flags": flags,
            }
        return result

    @staticmethod
    def contains_sensitive(value: str) -> bool:
        lowered = value.lower()
        return any(marker in lowered or marker in value for marker in SENSITIVE_MARKERS)

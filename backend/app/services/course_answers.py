from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterator

from backend.app.api.errors import make_trace_id
from backend.app.models import User
from backend.app.providers.openai_compatible import ModelProviderError
from backend.app.services.model_settings import (
    MODEL_NOT_CONFIGURED_MESSAGE,
    ModelNotConfiguredError,
    ModelSettingsService,
)


class CourseAnswerGenerationError(RuntimeError):
    pass


@dataclass(frozen=True)
class CourseAnswerGeneration:
    content: str
    trace_id: str | None


@dataclass(frozen=True)
class CourseAnswerStream:
    tokens: Iterator[str]
    trace_id: str | None
    used_model: bool


class CourseAnswerService:
    def __init__(self, model_settings_service: ModelSettingsService) -> None:
        self.model_settings_service = model_settings_service

    def generate(self, user: User, question: str, citations: list[dict[str, Any]]) -> CourseAnswerGeneration:
        if not citations:
            return CourseAnswerGeneration(content="我先检查了课程资料，但还没有足够依据支撑这个问题。", trace_id=None)

        trace_id = make_trace_id()
        messages = self._build_messages(question=question, citations=citations)
        try:
            content = self.model_settings_service.chat_completion(user=user, messages=messages)
        except ModelNotConfiguredError:
            return CourseAnswerGeneration(content=MODEL_NOT_CONFIGURED_MESSAGE, trace_id=None)
        except ModelProviderError as exc:
            raise CourseAnswerGenerationError("模型暂不可用，请检查设置或稍后重试。") from exc

        return CourseAnswerGeneration(content=content, trace_id=trace_id)

    def stream(self, user: User, question: str, citations: list[dict[str, Any]]) -> CourseAnswerStream:
        if not citations:
            return CourseAnswerStream(
                tokens=iter(["我先检查了课程资料，但还没有足够依据支撑这个问题。"]),
                trace_id=None,
                used_model=False,
            )

        trace_id = make_trace_id()
        messages = self._build_messages(question=question, citations=citations)
        try:
            tokens = self.model_settings_service.chat_completion_stream(user=user, messages=messages)
        except ModelNotConfiguredError:
            return CourseAnswerStream(
                tokens=iter([MODEL_NOT_CONFIGURED_MESSAGE]),
                trace_id=None,
                used_model=False,
            )
        except ModelProviderError as exc:
            raise CourseAnswerGenerationError("模型暂不可用，请检查设置或稍后重试。") from exc

        def guarded_tokens() -> Iterator[str]:
            try:
                yield from tokens
            except ModelProviderError as exc:
                raise CourseAnswerGenerationError("模型暂不可用，请检查设置或稍后重试。") from exc

        return CourseAnswerStream(tokens=guarded_tokens(), trace_id=trace_id, used_model=True)

    @staticmethod
    def _build_messages(question: str, citations: list[dict[str, Any]]) -> list[dict[str, str]]:
        citation_blocks = []
        for index, citation in enumerate(citations[:5], start=1):
            source_title = str(citation.get("source_title") or "课程资料")
            section_title = str(citation.get("section_title") or "未命名章节")
            score = citation.get("score")
            content = str(citation.get("content") or "")[:800]
            citation_blocks.append(
                "\n".join(
                    [
                        f"[{index}] 来源：{source_title}",
                        f"章节：{section_title}",
                        f"匹配度：{score}",
                        f"片段：{content}",
                    ]
                )
            )

        return [
            {
                "role": "system",
                "content": (
                    "你是 EduNova 的课程学习助手。只能依据用户课程资料引用回答。"
                    "如果引用不足以支持结论，必须明确说明依据不足。"
                    "回答要面向学生复习，结构清晰，避免编造资料外事实。"
                ),
            },
            {
                "role": "user",
                "content": "\n\n".join(
                    [
                        f"学生问题：{question}",
                        "课程引用：",
                        "\n\n".join(citation_blocks),
                        "请基于上述引用生成学习回答，并在回答中说明使用了哪些来源。",
                    ]
                ),
            },
        ]

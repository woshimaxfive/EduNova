from __future__ import annotations

import base64
from typing import Literal

from json_repair import loads as repair_json
from pydantic import BaseModel, Field, ValidationError

from backend.app.models import User
from backend.app.services.model_settings import ModelNotConfiguredError, ModelSettingsService
from backend.app.services.tutor_attachments import TutorAttachmentService


class VisionUnderstandingError(RuntimeError):
    pass


class VisionUnderstanding(BaseModel):
    standalone_query: str = Field(min_length=1, max_length=1000)
    visual_summary: str = Field(min_length=1, max_length=2400)
    extracted_text: str = Field(default="", max_length=3000)
    observations: list[str] = Field(default_factory=list, max_length=12)
    uncertainties: list[str] = Field(default_factory=list, max_length=8)
    intent: str = Field(default="visual_learning", max_length=80)
    search_required: bool = False
    reasoning_mode: Literal["auto", "deep"] = "auto"
    confidence: float = Field(default=0.0, ge=0, le=1)
    provider: str = Field(default="unknown", max_length=80)


class VisionUnderstandingService:
    def __init__(
        self,
        model_service: ModelSettingsService,
        attachment_service: TutorAttachmentService,
    ) -> None:
        self.model_service = model_service
        self.attachment_service = attachment_service

    def understand(self, *, user: User, question: str, attachment_ids: list[int]) -> VisionUnderstanding:
        image_data_urls: list[str] = []
        for attachment_id in list(dict.fromkeys(attachment_ids))[:3]:
            attachment, content = self.attachment_service.read(user=user, attachment_id=attachment_id)
            encoded = base64.b64encode(content).decode("ascii")
            image_data_urls.append(f"data:{attachment.mime_type};base64,{encoded}")
        if not image_data_urls:
            raise VisionUnderstandingError("没有可供理解的图片。")
        prompt = f"""
你是 EduNova 的图片学习理解器。只根据图片和用户问题形成可审计的结构化理解，不直接虚构教材引用。
用户问题：{question[:2000]}

请只返回 JSON 对象：
{{
  "standalone_query": "适合后续课程检索和回答的完整问题",
  "visual_summary": "图片中与学习问题有关的结构、关系、题目和图表摘要",
  "extracted_text": "确实可见的重要文字；看不清就留空",
  "observations": ["可直接观察到的事实"],
  "uncertainties": ["无法确认或需要用户补充的地方"],
  "intent": "visual_learning|exercise_help|diagram_explanation|error_diagnosis|comparison",
  "search_required": false,
  "reasoning_mode": "auto|deep",
  "confidence": 0.0
}}
不要输出思维链，不要把猜测写成观察事实。涉及多步推导、复杂图表或诊断时 reasoning_mode 使用 deep；只有确需最新外部资料时 search_required 才为 true。
""".strip()
        try:
            raw = self.model_service.vision_completion(
                user,
                prompt=prompt,
                image_data_urls=image_data_urls,
            )
            payload = repair_json(raw)
            if not isinstance(payload, dict):
                raise ValueError("视觉模型没有返回对象。")
            result = VisionUnderstanding.model_validate(payload)
            runtime = self.model_service.resolve_vision_runtime_config(user)
            return result.model_copy(update={"provider": runtime.preset_id or runtime.provider})
        except ModelNotConfiguredError:
            raise
        except (ValidationError, ValueError, TypeError) as exc:
            raise VisionUnderstandingError("图片理解结果无效，请重试或更换图片理解模型。") from exc

    @staticmethod
    def contextual_question(question: str, result: VisionUnderstanding) -> str:
        parts = [question.strip(), f"图片理解摘要：{result.visual_summary}"]
        if result.extracted_text:
            parts.append(f"图片中的关键文字：{result.extracted_text}")
        if result.observations:
            parts.append("可观察事实：" + "；".join(result.observations[:8]))
        if result.uncertainties:
            parts.append("仍不确定：" + "；".join(result.uncertainties[:5]))
        return "\n\n".join(part for part in parts if part)[:8000]

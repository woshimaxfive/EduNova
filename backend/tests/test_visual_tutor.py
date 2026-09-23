from __future__ import annotations

from io import BytesIO
from types import SimpleNamespace

import pytest
from PIL import Image
from langgraph.graph import END, START, StateGraph

from backend.app.agents.schemas import AgentState
from backend.app.core.config import Settings
from backend.app.providers.capabilities import provider_capabilities
from backend.app.services.tutor_attachments import TutorAttachmentError, TutorAttachmentService
from backend.app.services.vision_understanding import VisionUnderstandingService
from backend.app.services.tutor import InvalidMaterialContextError, TutorSessionService


def _png_bytes(size: tuple[int, int] = (24, 16)) -> bytes:
    output = BytesIO()
    Image.new("RGB", size, (245, 248, 250)).save(output, format="PNG")
    return output.getvalue()


def test_vision_capabilities_are_explicit_and_do_not_assume_text_models() -> None:
    xfyun = provider_capabilities(preset_id="xfyun-vision", base_url=None)
    assert xfyun.supports_image_input is False
    assert xfyun.vision_protocol == "none"
    assert provider_capabilities(preset_id="openai-vision", base_url=None).verified_vision is True
    qwen = provider_capabilities(
        preset_id="qwen",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    )
    assert qwen.supports_image_input is True
    assert qwen.vision_protocol == "openai_chat_completions"
    assert qwen.verified_vision is True
    assert provider_capabilities(preset_id="spark", base_url=None).supports_image_input is False
    assert provider_capabilities(preset_id="deepseek", base_url=None).supports_image_input is False
    assert provider_capabilities(preset_id="custom", base_url=None).supports_image_input is False


def test_image_normalization_reencodes_and_clears_metadata() -> None:
    image = Image.new("RGB", (32, 20), "white")
    exif = Image.Exif()
    exif[0x010E] = "private-note"
    source = BytesIO()
    image.save(source, format="JPEG", exif=exif)

    normalized, mime, width, height = TutorAttachmentService._normalize_image(source.getvalue(), "image/jpeg")

    assert (mime, width, height) == ("image/jpeg", 32, 20)
    with Image.open(BytesIO(normalized)) as result:
        assert not result.getexif()


def test_image_normalization_rejects_oversized_edge() -> None:
    with pytest.raises(TutorAttachmentError, match="尺寸过大"):
        TutorAttachmentService._normalize_image(_png_bytes((4097, 1)), "image/png")


class _MemoryStorage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.deleted: list[str] = []

    def put_bytes(self, key, content, *, content_type=None):
        del content_type
        self.objects[key] = content
        return key

    def read_bytes(self, key):
        return self.objects[key]

    def delete(self, key):
        self.deleted.append(key)
        self.objects.pop(key, None)


class _NoopScanner:
    def scan(self, content):
        del content


class _AttachmentDb:
    def __init__(self) -> None:
        self.added = []
        self.next_id = 100

    def add(self, value):
        if getattr(value, "id", None) is None:
            self.next_id += 1
            value.id = self.next_id
        self.added.append(value)

    def flush(self):
        return None

    def commit(self):
        return None

    def refresh(self, value):
        del value

    def rollback(self):
        return None


class _UploadAttachmentService(TutorAttachmentService):
    def _session(self, user_id, session_id):
        return SimpleNamespace(id=session_id, user_id=user_id)


def test_chat_image_upload_creates_one_material_asset_and_keeps_it_when_draft_is_removed() -> None:
    db = _AttachmentDb()
    storage = _MemoryStorage()
    service = _UploadAttachmentService(db, Settings(), storage=storage, scanner=_NoopScanner())

    attachment = service.upload(
        user=SimpleNamespace(id=7),
        session_id=9,
        filename="课堂截图.png",
        declared_mime="image/png",
        content=_png_bytes(),
    )

    material = db.added[0]
    assert attachment.material_id == material.id
    assert attachment.storage_key is None
    assert material.ingestion_status == "stored"
    assert material.storage_path in storage.objects
    def get_attachment(**kwargs):
        del kwargs
        return attachment

    service.get = get_attachment
    service.delete(user=SimpleNamespace(id=7), attachment_id=attachment.id)
    assert material.storage_path in storage.objects
    assert len(storage.deleted) == 1
    assert storage.deleted[0].startswith("tmp/materials/")


class _FakeAttachmentService:
    def read(self, *, user, attachment_id):
        del user
        return SimpleNamespace(mime_type="image/png", id=attachment_id), _png_bytes()


class _FakeVisionModelService:
    def __init__(self) -> None:
        self.calls = []

    def vision_completion(self, user, *, prompt, image_data_urls):
        self.calls.append((user.id, prompt, image_data_urls))
        return """{
          "standalone_query": "解释流程图第二步",
          "visual_summary": "流程从输入经过判断进入第二步",
          "extracted_text": "输入，判断，输出",
          "observations": ["第二步是条件判断"],
          "uncertainties": [],
          "intent": "diagram_explanation",
          "search_required": false,
          "reasoning_mode": "deep",
          "confidence": 0.91
        }"""

    def resolve_vision_runtime_config(self, user):
        del user
        return SimpleNamespace(preset_id="xfyun-vision", provider="xfyun_vision")


def test_visual_understanding_uses_one_call_and_returns_safe_structure() -> None:
    model = _FakeVisionModelService()
    service = VisionUnderstandingService(model, _FakeAttachmentService())

    result = service.understand(
        user=SimpleNamespace(id=7),
        question="这张图第二步为什么这样做？",
        attachment_ids=[11, 11, 12],
    )

    assert len(model.calls) == 1
    assert len(model.calls[0][2]) == 2
    assert result.standalone_query == "解释流程图第二步"
    assert result.reasoning_mode == "deep"
    assert result.provider == "xfyun-vision"
    assert "data:image/png;base64," in model.calls[0][2][0]


def test_visual_provider_is_not_called_before_session_attachment_scope_is_validated() -> None:
    class Repository:
        def pending_attachments(self, user_id, session_id, attachment_ids):
            assert (user_id, session_id, attachment_ids) == (7, 9, [11])
            return []

    class Vision:
        def understand(self, **kwargs):
            raise AssertionError(f"不应向视觉 Provider 发送越权图片：{kwargs}")

    service = TutorSessionService(Repository(), vision_understanding_service=Vision())
    with pytest.raises(InvalidMaterialContextError, match="无权访问"):
        service._prepare_visual_question(
            user=SimpleNamespace(id=7),
            session=SimpleNamespace(id=9),
            question="解释图片",
            attachment_ids=[11],
        )


def test_tutor_agent_state_preserves_private_visual_context_and_original_message() -> None:
    observed: dict[str, object] = {}

    def inspect_state(state: AgentState) -> dict[str, object]:
        observed.update(state)
        return {}

    graph = StateGraph(AgentState)
    graph.add_node("inspect", inspect_state)
    graph.add_edge(START, "inspect")
    graph.add_edge("inspect", END)

    graph.compile().invoke(
        {
            "message_text": "用户问题\n\n图片理解摘要：内部上下文",
            "stored_message_text": "用户问题",
            "attachment_ids": [11],
            "vision_decision": {"intent": "visual_learning", "confidence": 0.9},
            "standalone_query": "完整问题",
            "uses_history": True,
            "referenced_turn_ids": ["7"],
        }
    )

    assert observed["stored_message_text"] == "用户问题"
    assert observed["attachment_ids"] == [11]
    assert observed["vision_decision"] == {"intent": "visual_learning", "confidence": 0.9}
    assert observed["standalone_query"] == "完整问题"
    assert observed["uses_history"] is True
    assert observed["referenced_turn_ids"] == ["7"]

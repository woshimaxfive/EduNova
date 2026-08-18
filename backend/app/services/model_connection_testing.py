from __future__ import annotations

import base64
from datetime import UTC, datetime
from io import BytesIO
from time import perf_counter
from typing import Literal

from json_repair import loads as repair_json
from PIL import Image, ImageDraw
from pydantic import BaseModel, Field

from backend.app.core.config import Settings
from backend.app.providers.capabilities import provider_capabilities
from backend.app.providers.model_tasks import ModelTaskProfile
from backend.app.providers.openai_compatible import (
    ModelProviderError,
    OpenAICompatibleConfig,
    OpenAICompatibleEmbeddingConfig,
)
from backend.app.providers.retrieval import (
    EmbeddingRequestConfig,
    HttpRerankProvider,
    RerankRequestConfig,
    XFYUN_EMBEDDING_DIMENSION,
    XfyunEmbeddingProvider,
)
from backend.app.providers.xfyun_vision import XfyunVisionConfig, XfyunVisionProvider
from backend.app.services.model_execution import (
    ModelExecutionContext,
    ModelExecutionRuntime,
    model_execution_scope,
)
from backend.app.services.model_settings_contracts import (
    ModelChatProvider,
    ModelConnectionOperation,
    ModelConnectionTestResponse,
    RuntimeModelConfig,
)


LOCAL_PLACEHOLDER_API_KEY = "local-dev-key"
VISION_CONNECTION_TEST_PROMPT = """请分析图片并只返回 JSON 对象，不要 Markdown。必须包含：
standalone_query、visual_summary、extracted_text、observations（字符串数组）、
uncertainties（字符串数组）、intent、search_required（布尔值）、
reasoning_mode（auto 或 deep）、confidence（0 到 1）。"""


class _VisionConnectionContract(BaseModel):
    standalone_query: str
    visual_summary: str
    extracted_text: str
    observations: list[str]
    uncertainties: list[str]
    intent: str
    search_required: bool
    reasoning_mode: Literal["auto", "deep"]
    confidence: float = Field(ge=0, le=1)


class _StructuredConnectionContract(BaseModel):
    status: Literal["ok"]
    items: list[str] = Field(min_length=2, max_length=2)


def _vision_connection_test_image() -> str:
    image = Image.new("RGB", (512, 192), "white")
    ImageDraw.Draw(image).text((32, 72), "EduNova Vision 32", fill="black")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


class ModelConnectionTester:
    def __init__(
        self,
        *,
        settings: Settings,
        provider: ModelChatProvider,
        execution_runtime: ModelExecutionRuntime,
        xfyun_embedding_provider: XfyunEmbeddingProvider,
        rerank_provider: HttpRerankProvider,
        xfyun_vision_provider: XfyunVisionProvider,
    ) -> None:
        self.settings = settings
        self.provider = provider
        self.execution_runtime = execution_runtime
        self.xfyun_embedding_provider = xfyun_embedding_provider
        self.rerank_provider = rerank_provider
        self.xfyun_vision_provider = xfyun_vision_provider

    def test(
        self,
        runtime: RuntimeModelConfig,
        *,
        user_id: int,
        operation: ModelConnectionOperation,
    ) -> ModelConnectionTestResponse:
        tested_at = datetime.now(UTC)
        model = runtime.chat_model if operation in {"chat", "structured", "vision"} else runtime.embedding_model
        if not runtime.can_use_model or model is None:
            label = {
                "chat": "回答模型",
                "structured": "结构化生成模型",
                "embedding": "向量模型",
                "rerank": "重排序模型",
                "vision": "图片理解模型",
            }[operation]
            return ModelConnectionTestResponse(
                ok=False,
                source=runtime.source,
                chat_model=runtime.chat_model,
                message=f"当前未配置可用{label}。",
                config_id=runtime.config_id,
                operation=operation,
                model=model,
                code="not_configured",
                tested_at=tested_at,
            )

        try:
            actual_dimension: int | None = None
            reasoning_tokens: int | None = None
            started = perf_counter()
            with model_execution_scope(ModelExecutionContext(purpose="connection_test")):
                if operation == "embedding":

                    def test_embedding() -> list[list[float]]:
                        if runtime.provider == "xfyun_embedding":
                            config = EmbeddingRequestConfig(
                                provider=runtime.provider,
                                base_url=runtime.base_url or "",
                                api_key=runtime.api_key or "",
                                model=runtime.embedding_model or "llm-embedding",
                                dimensions=XFYUN_EMBEDDING_DIMENSION,
                                app_id=runtime.app_id,
                                api_secret=runtime.api_secret,
                            )
                            return self.xfyun_embedding_provider.embed_documents(
                                config,
                                ["EduNova 向量连接测试"],
                                self.settings.model_request_timeout_seconds,
                            )
                        embedding_config = OpenAICompatibleEmbeddingConfig(
                            base_url=runtime.base_url or "",
                            api_key=runtime.api_key or LOCAL_PLACEHOLDER_API_KEY,
                            embedding_model=runtime.embedding_model or "",
                        )
                        return self.provider.embed_texts(
                            config=embedding_config,
                            texts=["EduNova 向量连接测试"],
                            timeout_seconds=self.settings.model_request_timeout_seconds,
                            dimensions=runtime.dimensions,
                        )

                    vectors = self.execution_runtime.execute(
                        user_id=user_id,
                        provider_source=runtime.source,
                        model_config_id=runtime.config_id,
                        model_name=model,
                        operation="embedding",
                        call=test_embedding,
                        timeout_seconds=self.settings.model_request_timeout_seconds,
                        max_attempts=1,
                        bypass_circuit=True,
                    )
                    actual_dimension = len(vectors[0]) if vectors and vectors[0] else None
                elif operation == "rerank":
                    rerank_config = RerankRequestConfig(
                        provider=runtime.provider,
                        base_url=runtime.base_url or "",
                        api_key=runtime.api_key or "",
                        model=runtime.embedding_model or "",
                        workspace_id=runtime.workspace_id,
                    )
                    self.execution_runtime.execute(
                        user_id=user_id,
                        provider_source=runtime.source,
                        model_config_id=runtime.config_id,
                        model_name=model,
                        operation="rerank",
                        call=lambda: self.rerank_provider.rerank(
                            rerank_config,
                            "机器学习",
                            ["机器学习通过数据学习规律。", "天气晴朗。"],
                            1,
                            self.settings.model_request_timeout_seconds,
                        ),
                        timeout_seconds=self.settings.model_request_timeout_seconds,
                        max_attempts=1,
                        bypass_circuit=True,
                    )
                elif operation == "vision":
                    capabilities = provider_capabilities(preset_id=runtime.preset_id, base_url=runtime.base_url)
                    if not capabilities.supports_image_input:
                        raise ModelProviderError("该配置未声明图片理解能力。", code="not_configured")
                    if capabilities.vision_protocol == "xfyun_websocket":

                        def call() -> str:
                            return self.xfyun_vision_provider.vision_completion(
                                XfyunVisionConfig(
                                    base_url=runtime.base_url or "",
                                    app_id=runtime.app_id or "",
                                    api_key=runtime.api_key or "",
                                    api_secret=runtime.api_secret or "",
                                    domain=runtime.chat_model or "imagev3",
                                ),
                                prompt=VISION_CONNECTION_TEST_PROMPT,
                                image_data_urls=[_vision_connection_test_image()],
                                timeout_seconds=self.settings.model_request_timeout_seconds,
                            )
                    else:
                        visual_config = OpenAICompatibleConfig(
                            base_url=runtime.base_url or "",
                            api_key=runtime.api_key or LOCAL_PLACEHOLDER_API_KEY,
                            chat_model=runtime.chat_model or "",
                        )

                        def call() -> str:
                            return self.provider.vision_completion(
                                visual_config,
                                prompt=VISION_CONNECTION_TEST_PROMPT,
                                image_data_urls=[_vision_connection_test_image()],
                                timeout_seconds=self.settings.model_request_timeout_seconds,
                            )

                    raw_vision = self.execution_runtime.execute(
                        user_id=user_id,
                        provider_source=runtime.source,
                        model_config_id=runtime.config_id,
                        model_name=model,
                        operation="vision",
                        call=call,
                        timeout_seconds=self.settings.model_request_timeout_seconds,
                        max_attempts=1,
                        bypass_circuit=True,
                    )
                    try:
                        _VisionConnectionContract.model_validate(repair_json(raw_vision))
                    except (TypeError, ValueError) as exc:
                        raise ModelProviderError(
                            "图片理解服务未返回完整的结构化结果。",
                            code="invalid_response",
                        ) from exc
                elif operation == "structured":
                    capabilities = provider_capabilities(preset_id=runtime.preset_id, base_url=runtime.base_url)
                    profile = ModelTaskProfile(
                        task_type="connection_test",
                        reasoning="disabled",
                        output_mode="json_object" if capabilities.structured_output == "json_object" else "text",
                        creativity="stable",
                        timeout_seconds=min(20.0, self.settings.model_request_timeout_seconds),
                        max_attempts=1,
                    )
                    structured_config = OpenAICompatibleConfig(
                        base_url=runtime.base_url or "",
                        api_key=runtime.api_key or LOCAL_PLACEHOLDER_API_KEY,
                        chat_model=runtime.chat_model or "",
                        reasoning_protocol=capabilities.reasoning_protocol,
                        task_profile=profile,
                    )
                    completion = self.execution_runtime.execute(
                        user_id=user_id,
                        provider_source=runtime.source,
                        model_config_id=runtime.config_id,
                        model_name=model,
                        operation="structured",
                        call=lambda: self.provider.chat_completion_result(
                            config=structured_config,
                            messages=[
                                {"role": "system", "content": "你是 EduNova 结构化能力检查器，只输出 JSON。"},
                                {"role": "user", "content": '返回 JSON：{"status":"ok","items":["课程","练习"]}。'},
                            ],
                            timeout_seconds=profile.timeout_seconds,
                        ),
                        timeout_seconds=profile.timeout_seconds,
                        max_attempts=1,
                        bypass_circuit=True,
                    )
                    reasoning_tokens = completion.reasoning_tokens
                    try:
                        _StructuredConnectionContract.model_validate(repair_json(completion.content))
                    except (TypeError, ValueError) as exc:
                        raise ModelProviderError("模型未返回完整的结构化结果。", code="invalid_response") from exc
                else:
                    capabilities = provider_capabilities(preset_id=runtime.preset_id, base_url=runtime.base_url)
                    chat_config = OpenAICompatibleConfig(
                        base_url=runtime.base_url or "",
                        api_key=runtime.api_key or LOCAL_PLACEHOLDER_API_KEY,
                        chat_model=runtime.chat_model or "",
                        reasoning_protocol=capabilities.reasoning_protocol,
                        thinking_type="disabled" if runtime.preset_id in {"spark", "qwen"} else None,
                    )
                    self.execution_runtime.execute(
                        user_id=user_id,
                        provider_source=runtime.source,
                        model_config_id=runtime.config_id,
                        model_name=model,
                        operation="chat",
                        call=lambda: self.provider.chat_completion(
                            config=chat_config,
                            messages=[
                                {"role": "system", "content": "你是 EduNova 的模型连通性检查器。"},
                                {"role": "user", "content": "请只回复 ok。"},
                            ],
                            timeout_seconds=self.settings.model_request_timeout_seconds,
                        ),
                        timeout_seconds=self.settings.model_request_timeout_seconds,
                        max_attempts=1,
                        bypass_circuit=True,
                    )
        except ModelProviderError as exc:
            return ModelConnectionTestResponse(
                ok=False,
                source=runtime.source,
                chat_model=runtime.chat_model,
                message=str(exc),
                config_id=runtime.config_id,
                operation=operation,
                model=model,
                code=exc.code,
                retryable=exc.retryable,
                tested_at=tested_at,
            )
        except Exception:
            return ModelConnectionTestResponse(
                ok=False,
                source=runtime.source,
                chat_model=runtime.chat_model,
                message="连接验证失败，请稍后重试。",
                config_id=runtime.config_id,
                operation=operation,
                model=model,
                code="internal_error",
                tested_at=tested_at,
            )

        return ModelConnectionTestResponse(
            ok=True,
            source=runtime.source,
            chat_model=runtime.chat_model,
            message=(
                "向量服务连接正常。"
                if operation == "embedding"
                else "结构化生成能力验证通过。"
                if operation == "structured"
                else "图片理解服务连接正常。"
                if operation == "vision"
                else "AI 服务连接正常。"
            ),
            config_id=runtime.config_id,
            operation=operation,
            model=model,
            tested_at=tested_at,
            dimension=actual_dimension,
            latency_ms=max(0, int((perf_counter() - started) * 1000)),
            reasoning_tokens=reasoning_tokens,
        )

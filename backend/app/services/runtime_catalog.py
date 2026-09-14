"""Describe actual adapters and unsupported operations without probing providers."""
from dataclasses import asdict

from backend.app.providers.capabilities import provider_capabilities
from backend.app.schemas.run_history import RuntimeCapability, RuntimeCatalog
from backend.app.services.ai_capabilities import AI_CAPABILITIES


def runtime_catalog():
    workflows = [RuntimeCapability(name=name, transport="ai_job", input_contract=cap.input_model.__name__,
        output_contract=cap.output_model.__name__, snapshot=True, replay=True, branch=name == "path_planning",
        reexecute=name in {"path_planning", "resource_generation"},
        boundary="原领域事务与评分不变；重试使用原入口；资源重新执行仅适用于未绑定任务的请求。")
        for name, cap in AI_CAPABILITIES.items()]
    for name, request, response in [
        ("tutor", "SendTutorMessageRequest", "TutorMessage/SSE"),
        ("profile", "ProfileChatRequest", "ProfileChatResponse"),
        ("assessment_submission", "SubmitPracticeAnswersRequest", "PracticeSessionDetail"),
        ("material_comparison", "CompareMaterialsRequest", "MaterialComparisonResult"),
    ]:
        workflows.append(RuntimeCapability(name=name, transport="domain_api", input_contract=request,
            output_contract=response, snapshot=False, replay=True, branch=False, reexecute=False,
            boundary="使用既有领域 API 合同与只读 Trace；禁止通用运行恢复/分支复制评分或画像事实。"))
    from backend.app.agents.search_tools import SearchWebInput
    return RuntimeCatalog(workflows=workflows,
        provider_contracts={name: {**asdict(provider_capabilities(preset_id=name, base_url=None)),
            "verification": "adapter_contract_not_live_probe"} for name in ("openai", "qwen", "spark", "custom", "openai-vision", "xfyun-vision", "custom-vision")},
        tool_contracts={"search_web": {"input_schema": SearchWebInput.model_json_schema(),
            "execution": "existing_langchain_toolnode", "side_effect": "external_read", "scope": "explicit_search_policy",
            "failure": "warning_without_evidence", "mastery_write": False}})

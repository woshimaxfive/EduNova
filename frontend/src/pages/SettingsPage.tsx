import { Database, GearSix, Key, ShieldCheck, UserCircle } from "@phosphor-icons/react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import {
  getModelSettings,
  saveModelSettings,
  testModelSettings,
  type ModelSettingsRequest,
  type ModelSettingsSource
} from "../api/settings";
import { ActionNotice } from "../components/feedback/ActionNotice";
import { useActionNotice } from "../components/feedback/useActionNotice";
import { PageFrame } from "./PageFrame";

type ModelSettingsDraft = {
  base_url: string;
  api_key: string;
  chat_model: string;
  embedding_model: string;
};

type ModelProviderPreset = {
  id: string;
  name: string;
  description: string;
  baseUrl: string;
  chatModel: string;
  embeddingModel?: string;
  apiKeyPlaceholder: string;
  modelsHint?: string;
};

const EMPTY_MODEL_DRAFT: ModelSettingsDraft = {
  base_url: "",
  api_key: "",
  chat_model: "",
  embedding_model: ""
};

const MODEL_PROVIDER_PRESETS: ModelProviderPreset[] = [
  {
    id: "spark",
    name: "讯飞星火 Spark",
    description: "赛题出题企业相关模型服务，按 OpenAI-compatible HTTP 方式接入。",
    baseUrl: "https://spark-api-open.xf-yun.com/v1",
    chatModel: "4.0Ultra",
    apiKeyPlaceholder: "填入讯飞控制台的 API Key / APIPassword",
    modelsHint: "lite、generalv3、pro-128k、max-32k、4.0Ultra"
  },
  {
    id: "openai-compatible",
    name: "OpenAI-compatible",
    description: "适用于标准 /v1/chat/completions 兼容接口。",
    baseUrl: "https://api.example.com/v1",
    chatModel: "gpt-4.1-mini",
    embeddingModel: "text-embedding-3-small",
    apiKeyPlaceholder: "填入 OpenAI-compatible API Key"
  },
  {
    id: "custom",
    name: "自定义兼容服务",
    description: "保留手动填写，适合学校内网、私有网关或本地模型代理。",
    baseUrl: "",
    chatModel: "",
    apiKeyPlaceholder: "填入服务商 API Key"
  },
  {
    id: "deepseek",
    name: "DeepSeek",
    description: "DeepSeek OpenAI-compatible 接口。",
    baseUrl: "https://api.deepseek.com/v1",
    chatModel: "deepseek-chat",
    apiKeyPlaceholder: "填入 DeepSeek API Key"
  },
  {
    id: "qwen",
    name: "通义千问",
    description: "阿里云百炼 OpenAI-compatible 接口。",
    baseUrl: "https://dashscope.aliyuncs.com/compatible-mode/v1",
    chatModel: "qwen-plus",
    embeddingModel: "text-embedding-v3",
    apiKeyPlaceholder: "填入 DashScope API Key"
  },
  {
    id: "kimi",
    name: "Kimi",
    description: "Moonshot OpenAI-compatible 接口。",
    baseUrl: "https://api.moonshot.cn/v1",
    chatModel: "moonshot-v1-8k",
    apiKeyPlaceholder: "填入 Moonshot API Key"
  },
  {
    id: "zhipu",
    name: "智谱",
    description: "智谱 OpenAI-compatible 接口。",
    baseUrl: "https://open.bigmodel.cn/api/paas/v4",
    chatModel: "glm-4-flash",
    apiKeyPlaceholder: "填入智谱 API Key"
  },
  {
    id: "openrouter",
    name: "OpenRouter",
    description: "OpenRouter OpenAI-compatible 聚合接口。",
    baseUrl: "https://openrouter.ai/api/v1",
    chatModel: "openai/gpt-4o-mini",
    apiKeyPlaceholder: "填入 OpenRouter API Key"
  },
  {
    id: "siliconflow",
    name: "SiliconFlow",
    description: "SiliconFlow OpenAI-compatible 接口。",
    baseUrl: "https://api.siliconflow.cn/v1",
    chatModel: "Qwen/Qwen2.5-7B-Instruct",
    embeddingModel: "BAAI/bge-m3",
    apiKeyPlaceholder: "填入 SiliconFlow API Key"
  },
  {
    id: "local",
    name: "本地兼容服务",
    description: "适合 Ollama、LM Studio 或本机 OpenAI-compatible 网关。",
    baseUrl: "http://localhost:11434/v1",
    chatModel: "qwen2.5",
    apiKeyPlaceholder: "本地服务如不需要 Key，可留空"
  }
];

function getProviderPreset(presetId: string) {
  return MODEL_PROVIDER_PRESETS.find((preset) => preset.id === presetId) ?? MODEL_PROVIDER_PRESETS[0];
}

function inferProviderPresetId(baseUrl: string | null | undefined) {
  if (!baseUrl) {
    return "spark";
  }

  return (
    MODEL_PROVIDER_PRESETS.find((preset) => preset.id !== "custom" && preset.baseUrl === baseUrl)?.id ?? "custom"
  );
}

function sourceLabel(source: ModelSettingsSource | undefined) {
  if (source === "user") {
    return "个人配置";
  }

  if (source === "system") {
    return "服务器配置";
  }

  return "未配置";
}

export function SettingsPage() {
  const [nickname, setNickname] = useState("演示学生");
  const [providerPresetId, setProviderPresetId] = useState("spark");
  const [draft, setDraft] = useState<ModelSettingsDraft>(EMPTY_MODEL_DRAFT);
  const [hasEditedDraft, setHasEditedDraft] = useState(false);
  const queryClient = useQueryClient();
  const { notice, showNotice } = useActionNotice();
  const modelSettingsQuery = useQuery({
    queryKey: ["settings", "model"],
    queryFn: getModelSettings,
    staleTime: 30_000
  });
  const modelSummary = modelSettingsQuery.data?.data ?? null;
  const currentDraft: ModelSettingsDraft = {
    base_url: hasEditedDraft ? draft.base_url : (modelSummary?.base_url ?? ""),
    api_key: draft.api_key,
    chat_model: hasEditedDraft ? draft.chat_model : (modelSummary?.chat_model ?? ""),
    embedding_model: hasEditedDraft ? draft.embedding_model : (modelSummary?.embedding_model ?? "")
  };
  const effectiveProviderPresetId = hasEditedDraft ? providerPresetId : inferProviderPresetId(modelSummary?.base_url);
  const selectedProviderPreset = getProviderPreset(effectiveProviderPresetId);
  const saveModelMutation = useMutation({
    mutationFn: (payload: ModelSettingsRequest) => saveModelSettings(payload),
    onSuccess: (response) => {
      queryClient.setQueryData(["settings", "model"], response);
      setDraft({
        base_url: response.data.base_url ?? "",
        api_key: "",
        chat_model: response.data.chat_model ?? "",
        embedding_model: response.data.embedding_model ?? ""
      });
      setHasEditedDraft(false);
      showNotice("模型配置已保存。", "success");
    },
    onError: () => {
      showNotice("模型配置保存失败，请检查密钥加密配置。", "warning");
    }
  });
  const testModelMutation = useMutation({
    mutationFn: () => testModelSettings(),
    onSuccess: (response) => {
      showNotice(response.data.message || "模型连接成功。", response.data.ok ? "success" : "warning");
    },
    onError: () => {
      showNotice("模型连接失败，请检查 Base URL、模型名或密钥。", "warning");
    }
  });

  function saveSettings() {
    showNotice(`${nickname || "学生"} 的设置已保存。`, "success");
  }

  function updateModelDraft(field: keyof ModelSettingsDraft, value: string) {
    setDraft({ ...currentDraft, [field]: value });
    setHasEditedDraft(true);
  }

  function applyProviderPreset(presetId: string) {
    const preset = getProviderPreset(presetId);
    setProviderPresetId(preset.id);

    if (preset.id === "custom") {
      return;
    }

    setDraft({
      base_url: preset.baseUrl,
      api_key: currentDraft.api_key,
      chat_model: preset.chatModel,
      embedding_model: preset.embeddingModel ?? ""
    });
    setHasEditedDraft(true);
  }

  function saveModelConfiguration() {
    const embeddingModel = currentDraft.embedding_model.trim();
    const payload: ModelSettingsRequest = {
      provider: "openai_compatible",
      base_url: currentDraft.base_url.trim(),
      chat_model: currentDraft.chat_model.trim()
    };
    const apiKey = currentDraft.api_key.trim();

    if (!payload.base_url || !payload.chat_model) {
      showNotice("请先补全 Base URL 和聊天模型。", "warning");
      return;
    }

    if (apiKey) {
      payload.api_key = apiKey;
    }

    if (embeddingModel) {
      payload.embedding_model = embeddingModel;
    }

    saveModelMutation.mutate(payload);
  }

  function runModelConnectionTest() {
    testModelMutation.mutate();
  }

  return (
    <PageFrame title="设置">
      <div className="settings-workspace">
        <section className="student-panel settings-section" role="region" aria-label="模型设置">
          <div className="settings-section-icon" aria-hidden="true">
            <GearSix size={22} weight="duotone" />
          </div>
          <div>
            <h2>模型连接</h2>
            <p>个人配置优先，服务器配置兜底；密钥只保存加密后的版本。</p>
            <div className="settings-model-summary" aria-label="模型配置状态">
              <span className={modelSummary?.can_use_model ? "settings-status ready" : "settings-status"}>
                {modelSettingsQuery.isLoading ? "加载中" : sourceLabel(modelSummary?.source)}
              </span>
              <span className="masked-value">
                <Key size={16} weight="duotone" aria-hidden="true" />
                {modelSummary?.api_key_masked ?? (modelSummary?.has_api_key ? "已保存密钥" : "未保存密钥")}
              </span>
              <span className="settings-status">
                {modelSummary?.can_use_model ? "可用于课程回答" : "当前不可用"}
              </span>
            </div>
            <div className="settings-form-row settings-model-grid">
              <label className="settings-provider-field">
                <span>Provider 预设</span>
                <select value={effectiveProviderPresetId} onChange={(event) => applyProviderPreset(event.target.value)}>
                  {MODEL_PROVIDER_PRESETS.map((preset) => (
                    <option key={preset.id} value={preset.id}>
                      {preset.name}
                    </option>
                  ))}
                </select>
              </label>
              <div className="settings-provider-note">
                <strong>{selectedProviderPreset.id === "spark" ? "赛题首选模型" : selectedProviderPreset.name}</strong>
                <span>{selectedProviderPreset.description}</span>
                {selectedProviderPreset.modelsHint ? <span>可选模型：{selectedProviderPreset.modelsHint}</span> : null}
              </div>
              <label>
                <span>Base URL</span>
                <input
                  value={currentDraft.base_url}
                  placeholder={selectedProviderPreset.baseUrl || "https://api.example.com/v1"}
                  onChange={(event) => updateModelDraft("base_url", event.target.value)}
                />
              </label>
              <label>
                <span>API Key / APIPassword</span>
                <input
                  type="password"
                  value={currentDraft.api_key}
                  placeholder={modelSummary?.has_api_key ? "留空则保留已保存密钥" : selectedProviderPreset.apiKeyPlaceholder}
                  onChange={(event) => updateModelDraft("api_key", event.target.value)}
                />
              </label>
              <label>
                <span>聊天模型</span>
                <input
                  value={currentDraft.chat_model}
                  placeholder={selectedProviderPreset.chatModel || "example-chat-model"}
                  onChange={(event) => updateModelDraft("chat_model", event.target.value)}
                />
              </label>
              <label>
                <span>向量模型（后续检索增强使用）</span>
                <input
                  value={currentDraft.embedding_model}
                  placeholder={selectedProviderPreset.embeddingModel || "可留空，后续接入 embedding 时再填写"}
                  onChange={(event) => updateModelDraft("embedding_model", event.target.value)}
                />
                <small className="settings-field-hint">当前课程回答先使用关键词引用；embedding 和向量召回后续接入。</small>
              </label>
            </div>
          </div>
          <div className="settings-action-stack">
            <button
              className="primary-action"
              type="button"
              onClick={saveModelConfiguration}
              disabled={saveModelMutation.isPending}
            >
              {saveModelMutation.isPending ? "保存中" : "保存模型配置"}
            </button>
            <button
              className="secondary-action"
              type="button"
              onClick={runModelConnectionTest}
              disabled={testModelMutation.isPending}
            >
              {testModelMutation.isPending ? "测试中" : "测试连接"}
            </button>
            <ActionNotice notice={notice} />
          </div>
        </section>

        <section className="student-panel settings-section" role="region" aria-label="隐私与数据">
          <div className="settings-section-icon" aria-hidden="true">
            <ShieldCheck size={22} weight="duotone" />
          </div>
          <div>
            <h2>隐私与数据边界</h2>
            <p>不记录密钥、密码、提示词或资料原文。</p>
          </div>
          <span className="settings-status">
            <Database size={16} weight="duotone" aria-hidden="true" />
            本地演示数据
          </span>
        </section>

        <section className="student-panel settings-section" role="region" aria-label="账号设置">
          <div className="settings-section-icon" aria-hidden="true">
            <UserCircle size={22} weight="duotone" />
          </div>
          <div>
            <h2>学生账号</h2>
            <p>学生身份、昵称和学习偏好。</p>
            <label className="settings-inline-input">
              <span>昵称</span>
              <input value={nickname} onChange={(event) => setNickname(event.target.value)} />
            </label>
          </div>
          <div className="settings-action-stack">
            <button className="primary-action" type="button" onClick={saveSettings}>
              保存设置
            </button>
          </div>
        </section>
      </div>
    </PageFrame>
  );
}

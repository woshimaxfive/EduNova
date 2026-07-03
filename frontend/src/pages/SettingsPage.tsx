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

const EMPTY_MODEL_DRAFT: ModelSettingsDraft = {
  base_url: "",
  api_key: "",
  chat_model: "",
  embedding_model: ""
};

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
  const [deepThinking, setDeepThinking] = useState(true);
  const [webSearch, setWebSearch] = useState(false);
  const [nickname, setNickname] = useState("演示学生");
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

  function saveModelConfiguration() {
    const payload: ModelSettingsRequest = {
      provider: "openai_compatible",
      base_url: currentDraft.base_url.trim(),
      chat_model: currentDraft.chat_model.trim(),
      embedding_model: currentDraft.embedding_model.trim()
    };
    const apiKey = currentDraft.api_key.trim();

    if (!payload.base_url || !payload.chat_model || !payload.embedding_model) {
      showNotice("请先补全 Base URL、聊天模型和向量模型。", "warning");
      return;
    }

    if (apiKey) {
      payload.api_key = apiKey;
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
              <label>
                <span>Base URL</span>
                <input
                  value={currentDraft.base_url}
                  placeholder="https://api.example.com/v1"
                  onChange={(event) => updateModelDraft("base_url", event.target.value)}
                />
              </label>
              <label>
                <span>API Key</span>
                <input
                  type="password"
                  value={currentDraft.api_key}
                  placeholder={modelSummary?.has_api_key ? "留空则保留已保存密钥" : "填入 OpenAI-compatible API Key"}
                  onChange={(event) => updateModelDraft("api_key", event.target.value)}
                />
              </label>
              <label>
                <span>聊天模型</span>
                <input
                  value={currentDraft.chat_model}
                  placeholder="gpt-4.1-mini"
                  onChange={(event) => updateModelDraft("chat_model", event.target.value)}
                />
              </label>
              <label>
                <span>向量模型</span>
                <input
                  value={currentDraft.embedding_model}
                  placeholder="text-embedding-3-small"
                  onChange={(event) => updateModelDraft("embedding_model", event.target.value)}
                />
              </label>
              <label className="settings-toggle">
                <input type="checkbox" checked={deepThinking} onChange={(event) => setDeepThinking(event.target.checked)} />
                <span>深度思考</span>
              </label>
              <label className="settings-toggle">
                <input type="checkbox" checked={webSearch} onChange={(event) => setWebSearch(event.target.checked)} />
                <span>联网搜索</span>
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

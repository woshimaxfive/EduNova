import { Database, GearSix, Key, ShieldCheck, Trash, UserCircle } from "@phosphor-icons/react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import {
  createModelConfig,
  deleteModelConfig,
  listModelConfigs,
  setDefaultModelConfig,
  testModelConfig,
  updateModelConfig,
  type ModelConfigRequest,
  type ModelConfigSummary,
  type ModelConfigUpdateRequest
} from "../api/settings";
import {
  getProviderPreset,
  inferProviderPresetId,
  MODEL_PROVIDER_PRESETS
} from "../config/modelProviders";
import { PageFrame } from "./PageFrame";

type ModelConfigDraft = {
  display_name: string;
  preset_id: string;
  base_url: string;
  api_key: string;
  chat_model: string;
  embedding_model: string;
};

const EMPTY_CONFIG_DRAFT: ModelConfigDraft = {
  display_name: "星火 Lite",
  preset_id: "spark",
  base_url: "https://spark-api-open.xf-yun.com/v1",
  api_key: "",
  chat_model: "lite",
  embedding_model: ""
};

function draftFromConfig(config: ModelConfigSummary): ModelConfigDraft {
  const presetId = inferProviderPresetId(config.base_url, config.preset_id);

  return {
    display_name: config.display_name,
    preset_id: presetId,
    base_url: config.base_url ?? "",
    api_key: "",
    chat_model: config.chat_model ?? "",
    embedding_model: config.embedding_model ?? ""
  };
}

function newDraftFromPreset(presetId = "spark"): ModelConfigDraft {
  const preset = getProviderPreset(presetId);

  return {
    display_name: preset.name.includes("讯飞") ? "星火 Lite" : `${preset.name} 配置`,
    preset_id: preset.id,
    base_url: preset.baseUrl,
    api_key: "",
    chat_model: preset.chatModel,
    embedding_model: preset.embeddingModel ?? ""
  };
}

function formatTestState(config: ModelConfigSummary) {
  if (config.last_test_ok === true) {
    return config.last_test_message || "最近测试成功";
  }

  if (config.last_test_ok === false) {
    return config.last_test_message || "最近测试失败";
  }

  return "尚未测试";
}

export function SettingsPage() {
  const [nickname, setNickname] = useState("演示学生");
  const [selectedConfigId, setSelectedConfigId] = useState<number | "new" | null>(null);
  const [draft, setDraft] = useState<ModelConfigDraft>(EMPTY_CONFIG_DRAFT);
  const queryClient = useQueryClient();
  const modelConfigsQuery = useQuery({
    queryKey: ["settings", "model-configs"],
    queryFn: listModelConfigs,
    staleTime: 30_000
  });
  const settingsList = modelConfigsQuery.data?.data ?? null;
  const configs = useMemo(() => settingsList?.configs ?? [], [settingsList?.configs]);
  const defaultConfigId = settingsList?.default_config_id ?? null;
  const selectedConfig = useMemo(() => {
    if (selectedConfigId === "new") {
      return null;
    }

    if (typeof selectedConfigId === "number") {
      return configs.find((config) => config.id === selectedConfigId) ?? null;
    }

    return configs.find((config) => config.id === defaultConfigId) ?? configs[0] ?? null;
  }, [configs, defaultConfigId, selectedConfigId]);
  const currentDraft = selectedConfigId === null && selectedConfig ? draftFromConfig(selectedConfig) : draft;
  const selectedPreset = getProviderPreset(currentDraft.preset_id);
  const activeConfigId = typeof selectedConfigId === "number" ? selectedConfigId : selectedConfig?.id ?? null;
  const isCreating = selectedConfigId === "new" || !selectedConfig;
  const canSave = Boolean(currentDraft.display_name.trim() && currentDraft.base_url.trim() && currentDraft.chat_model.trim());

  const createConfigMutation = useMutation({
    mutationFn: (payload: ModelConfigRequest) => createModelConfig(payload),
    onSuccess: (response) => {
      queryClient.invalidateQueries({ queryKey: ["settings", "model-configs"] });
      queryClient.invalidateQueries({ queryKey: ["settings", "model"] });
      setSelectedConfigId(response.data.id);
      setDraft(draftFromConfig(response.data));
    }
  });
  const updateConfigMutation = useMutation({
    mutationFn: ({ configId, payload }: { configId: number; payload: ModelConfigUpdateRequest }) =>
      updateModelConfig(configId, payload),
    onSuccess: (response) => {
      queryClient.invalidateQueries({ queryKey: ["settings", "model-configs"] });
      queryClient.invalidateQueries({ queryKey: ["settings", "model"] });
      setSelectedConfigId(response.data.id);
      setDraft(draftFromConfig(response.data));
    }
  });
  const defaultConfigMutation = useMutation({
    mutationFn: (configId: number) => setDefaultModelConfig(configId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["settings", "model-configs"] });
      queryClient.invalidateQueries({ queryKey: ["settings", "model"] });
    }
  });
  const testConfigMutation = useMutation({
    mutationFn: (configId: number) => testModelConfig(configId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["settings", "model-configs"] });
    }
  });
  const deleteConfigMutation = useMutation({
    mutationFn: (configId: number) => deleteModelConfig(configId),
    onSuccess: (response) => {
      queryClient.setQueryData(["settings", "model-configs"], response);
      queryClient.invalidateQueries({ queryKey: ["settings", "model"] });
      const nextConfig = response.data.configs.find((config) => config.id === response.data.default_config_id)
        ?? response.data.configs[0]
        ?? null;
      setSelectedConfigId(nextConfig?.id ?? "new");
      setDraft(nextConfig ? draftFromConfig(nextConfig) : newDraftFromPreset());
    }
  });

  function saveSettings() {
    void nickname;
  }

  function updateDraft(field: keyof ModelConfigDraft, value: string) {
    const baseDraft = selectedConfigId === null && selectedConfig ? draftFromConfig(selectedConfig) : draft;

    if (selectedConfigId === null && selectedConfig) {
      setSelectedConfigId(selectedConfig.id);
    }

    setDraft({ ...baseDraft, [field]: value });
  }

  function applyProviderPreset(presetId: string) {
    const preset = getProviderPreset(presetId);

    if (selectedConfigId === null && selectedConfig) {
      setSelectedConfigId(selectedConfig.id);
    }

    setDraft({
      ...currentDraft,
      preset_id: preset.id,
      base_url: preset.id === "custom" ? currentDraft.base_url : preset.baseUrl,
      chat_model: preset.id === "custom" ? currentDraft.chat_model : preset.chatModel,
      embedding_model: preset.id === "custom" ? currentDraft.embedding_model : (preset.embeddingModel ?? "")
    });
  }

  function createNewConfig() {
    setSelectedConfigId("new");
    setDraft(newDraftFromPreset());
  }

  function selectConfig(config: ModelConfigSummary) {
    setSelectedConfigId(config.id);
    setDraft(draftFromConfig(config));
  }

  function saveModelConfiguration() {
    if (!canSave) {
      return;
    }

    const embeddingModel = currentDraft.embedding_model.trim();
    const apiKey = currentDraft.api_key.trim();
    const payload = {
      display_name: currentDraft.display_name.trim(),
      preset_id: currentDraft.preset_id,
      provider: "openai_compatible" as const,
      base_url: currentDraft.base_url.trim(),
      chat_model: currentDraft.chat_model.trim(),
      ...(apiKey ? { api_key: apiKey } : {}),
      ...(embeddingModel ? { embedding_model: embeddingModel } : {})
    };

    if (isCreating || activeConfigId === null) {
      createConfigMutation.mutate({ ...payload, make_default: configs.length === 0 });
      return;
    }

    updateConfigMutation.mutate({ configId: activeConfigId, payload });
  }

  function setCurrentAsDefault() {
    if (activeConfigId === null) {
      return;
    }

    defaultConfigMutation.mutate(activeConfigId);
  }

  function runModelConnectionTest() {
    if (activeConfigId === null) {
      return;
    }

    testConfigMutation.mutate(activeConfigId);
  }

  function deleteCurrentConfig() {
    if (activeConfigId === null) {
      return;
    }

    deleteConfigMutation.mutate(activeConfigId);
  }

  return (
    <PageFrame title="设置">
      <div className="settings-workspace">
        <section className="student-panel settings-section settings-model-section" role="region" aria-label="模型设置">
          <div className="settings-section-icon" aria-hidden="true">
            <GearSix size={22} weight="duotone" />
          </div>
          <div className="settings-section-main">
            <h2>模型连接</h2>
            <p>同一账号可以保存多套模型配置；课程回答优先使用默认配置，没有默认配置时回退服务器配置。</p>
            <div className="settings-model-summary" aria-label="模型配置状态">
              <span className={defaultConfigId ? "settings-status ready" : "settings-status"}>
                {modelConfigsQuery.isLoading ? "加载中" : defaultConfigId ? "个人默认配置" : "服务器兜底"}
              </span>
              <span className="masked-value">
                <Key size={16} weight="duotone" aria-hidden="true" />
                {selectedConfig?.api_key_masked
                  ?? settingsList?.system_summary.api_key_masked
                  ?? (selectedConfig?.has_api_key ? "已保存密钥" : "未保存密钥")}
              </span>
              <span className="settings-status">
                {selectedConfig?.can_use_model || settingsList?.system_summary.can_use_model
                  ? "可用于课程回答"
                  : "当前不可用"}
              </span>
            </div>

            <div className="settings-config-layout">
              <aside className="settings-config-list" aria-label="模型配置列表">
                <div className="settings-config-list-head">
                  <span>配置列表</span>
                  <button className="secondary-action compact-action" type="button" onClick={createNewConfig}>
                    新建配置
                  </button>
                </div>
                {configs.length === 0 && selectedConfigId !== "new" ? (
                  <button className="settings-config-card empty" type="button" onClick={createNewConfig}>
                    <strong>还没有个人配置</strong>
                    <span>新建一套模型连接</span>
                  </button>
                ) : null}
                {configs.map((config) => (
                  <button
                    key={config.id}
                    className={config.id === activeConfigId && selectedConfigId !== "new" ? "settings-config-card active" : "settings-config-card"}
                    type="button"
                    onClick={() => selectConfig(config)}
                  >
                    <span className="settings-config-title">
                      <strong>{config.display_name}</strong>
                      {config.is_default ? <span className="settings-status ready">默认配置</span> : null}
                    </span>
                    <span>{getProviderPreset(config.preset_id).name}</span>
                    <span>{config.chat_model ?? "未填写模型"}</span>
                    <span>{formatTestState(config)}</span>
                  </button>
                ))}
                {selectedConfigId === "new" ? (
                  <button className="settings-config-card active" type="button">
                    <span className="settings-config-title">
                      <strong>新建配置</strong>
                    </span>
                    <span>{selectedPreset.name}</span>
                    <span>{currentDraft.chat_model || "待填写模型"}</span>
                  </button>
                ) : null}
              </aside>

              <div className="settings-config-editor">
                <div className="settings-form-row settings-model-grid">
                  <label>
                    <span>配置名称</span>
                    <input
                      value={currentDraft.display_name}
                      placeholder="例如：星火 Lite"
                      onChange={(event) => updateDraft("display_name", event.target.value)}
                    />
                  </label>
                  <label className="settings-provider-field">
                    <span>Provider 预设</span>
                    <select value={currentDraft.preset_id} onChange={(event) => applyProviderPreset(event.target.value)}>
                      {MODEL_PROVIDER_PRESETS.map((preset) => (
                        <option key={preset.id} value={preset.id}>
                          {preset.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <div className="settings-provider-note">
                    <strong>{selectedPreset.id === "spark" ? "赛题首选模型" : selectedPreset.name}</strong>
                    <span>{selectedPreset.description}</span>
                    {selectedPreset.modelsHint ? <span>提示：{selectedPreset.modelsHint}</span> : null}
                  </div>
                  <label>
                    <span>Base URL</span>
                    <input
                      value={currentDraft.base_url}
                      placeholder={selectedPreset.baseUrl || "https://api.example.com/v1"}
                      onChange={(event) => updateDraft("base_url", event.target.value)}
                    />
                  </label>
                  <label>
                    <span>{selectedPreset.apiKeyLabel}</span>
                    <input
                      type="password"
                      value={currentDraft.api_key}
                      placeholder={selectedConfig?.has_api_key ? "留空则保留已保存密钥" : selectedPreset.apiKeyPlaceholder}
                      onChange={(event) => updateDraft("api_key", event.target.value)}
                    />
                  </label>
                  <label>
                    <span>回答模型</span>
                    <input
                      value={currentDraft.chat_model}
                      placeholder={selectedPreset.chatModel || "填写服务商模型名"}
                      onChange={(event) => updateDraft("chat_model", event.target.value)}
                    />
                  </label>
                  <details className="settings-advanced-field">
                    <summary>高级项：向量模型</summary>
                    <label>
                      <span>向量模型（课程知识库检索使用）</span>
                      <input
                        value={currentDraft.embedding_model}
                        placeholder={selectedPreset.embeddingModel || "可留空，系统会使用本地 fallback"}
                        onChange={(event) => updateDraft("embedding_model", event.target.value)}
                      />
                      <small className="settings-field-hint">不填写向量模型时，课程检索会使用本地 fallback，页面会明确标记来源。</small>
                    </label>
                  </details>
                </div>

                <div className="settings-form-actions">
                  <button
                    className="primary-action"
                    type="button"
                    onClick={saveModelConfiguration}
                    disabled={createConfigMutation.isPending || updateConfigMutation.isPending}
                  >
                    {createConfigMutation.isPending || updateConfigMutation.isPending ? "保存中" : "保存配置"}
                  </button>
                  <button
                    className="secondary-action"
                    type="button"
                    onClick={setCurrentAsDefault}
                    disabled={activeConfigId === null || selectedConfig?.is_default || defaultConfigMutation.isPending}
                  >
                    设为默认
                  </button>
                  <button
                    className="secondary-action"
                    type="button"
                    onClick={runModelConnectionTest}
                    disabled={activeConfigId === null || testConfigMutation.isPending}
                  >
                    {testConfigMutation.isPending ? "测试中" : "测试连接"}
                  </button>
                  <button
                    className="secondary-action danger-action"
                    type="button"
                    onClick={deleteCurrentConfig}
                    disabled={activeConfigId === null || deleteConfigMutation.isPending}
                  >
                    <Trash size={16} weight="duotone" aria-hidden="true" />
                    删除配置
                  </button>
                </div>
              </div>
            </div>
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

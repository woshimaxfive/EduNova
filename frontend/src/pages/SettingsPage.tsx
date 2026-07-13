import { Database, GearSix, Key, ShieldCheck, Trash, UserCircle } from "@phosphor-icons/react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { updateCurrentUser } from "../api/auth";
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
import { InlineFeedback } from "../components/feedback/InlineFeedback";
import { ToastStack } from "../components/feedback/ToastStack";
import { useToastQueue } from "../components/feedback/useToastQueue";
import {
  getProviderPreset,
  inferProviderPresetId,
  MODEL_PROVIDER_PRESETS
} from "../config/modelProviders";
import { PATHS } from "../app/routePaths";
import { mapApiUserToStudentUser } from "../features/auth/authMappers";
import { useAuthStore } from "../features/auth/authStore";
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
  const authUser = useAuthStore((state) => state.user);
  const authToken = useAuthStore((state) => state.token);
  const setSession = useAuthStore((state) => state.setSession);
  const [nickname, setNickname] = useState(authUser?.displayName ?? "");
  const [selectedConfigId, setSelectedConfigId] = useState<number | "new" | null>(null);
  const [draft, setDraft] = useState<ModelConfigDraft>(EMPTY_CONFIG_DRAFT);
  const [settingsFeedback, setSettingsFeedback] = useState<string | null>(null);
  const [accountFeedback, setAccountFeedback] = useState<string | null>(null);
  const queryClient = useQueryClient();
  const { toast, showToast, dismissToast } = useToastQueue();
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
  const starterModeLabel = authUser
    ? authUser.starterMode === "ai_intro" ? "示例课程开始" : "空白开始"
    : "未读取";

  const createConfigMutation = useMutation({
    mutationFn: (payload: ModelConfigRequest) => createModelConfig(payload),
    onSuccess: (response) => {
      queryClient.invalidateQueries({ queryKey: ["settings", "model-configs"] });
      queryClient.invalidateQueries({ queryKey: ["settings", "model"] });
      setSelectedConfigId(response.data.id);
      setDraft(draftFromConfig(response.data));
      setSettingsFeedback(null);
      showToast("模型配置已保存。", "success");
    },
    onError: () => {
      showToast("模型配置保存失败，请检查密钥加密配置。", "warning");
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
      setSettingsFeedback(null);
      showToast("模型配置已保存。", "success");
    },
    onError: () => {
      showToast("模型配置保存失败，请检查名称、Base URL 或密钥。", "warning");
    }
  });
  const defaultConfigMutation = useMutation({
    mutationFn: (configId: number) => setDefaultModelConfig(configId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["settings", "model-configs"] });
      queryClient.invalidateQueries({ queryKey: ["settings", "model"] });
      setSettingsFeedback(null);
      showToast("已设为默认模型配置。", "success");
    },
    onError: () => {
      showToast("默认配置切换失败，请稍后重试。", "warning");
    }
  });
  const testConfigMutation = useMutation({
    mutationFn: (configId: number) => testModelConfig(configId),
    onSuccess: (response) => {
      queryClient.invalidateQueries({ queryKey: ["settings", "model-configs"] });
      setSettingsFeedback(null);
      showToast(response.data.message || "模型连接成功。", response.data.ok ? "success" : "warning");
    },
    onError: () => {
      showToast("模型连接失败，请检查 Base URL、回答模型或密钥。", "warning");
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
      setSettingsFeedback(null);
      showToast("模型配置已删除。", "success");
    },
    onError: () => {
      showToast("模型配置删除失败，请稍后重试。", "warning");
    }
  });
  const updateAccountMutation = useMutation({
    mutationFn: updateCurrentUser,
    onSuccess: (response) => {
      if (authToken) {
        setSession({
          token: authToken,
          user: mapApiUserToStudentUser(response.data)
        });
      }
      setNickname(response.data.display_name);
      setAccountFeedback(null);
      showToast("账号设置已保存。", "success");
    },
    onError: () => {
      showToast("账号设置保存失败，请稍后重试。", "warning");
    }
  });

  function saveSettings() {
    const nextNickname = nickname.trim();
    if (!nextNickname) {
      setAccountFeedback("昵称不能为空。");
      return;
    }

    setAccountFeedback(null);
    updateAccountMutation.mutate({ display_name: nextNickname });
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
      setSettingsFeedback("请先补全配置名称、Base URL 和回答模型。");
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
      setSettingsFeedback("请先保存配置，再设为默认。");
      return;
    }

    defaultConfigMutation.mutate(activeConfigId);
  }

  function runModelConnectionTest() {
    if (activeConfigId === null) {
      setSettingsFeedback("请先保存配置，再测试连接。");
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
    <PageFrame title="设置" titleMode="sr-only">
      <div className="settings-workspace">
        <header className="settings-workspace-header">
          <span>设置</span>
          <div>
            <h2>模型与账号</h2>
            <p>管理当前账号使用的模型连接和基础信息。</p>
          </div>
        </header>
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
                <InlineFeedback message={settingsFeedback} tone="warning" className="settings-inline-feedback" />
              </div>
            </div>
          </div>
        </section>

        <section className="student-panel settings-section" role="region" aria-label="隐私与数据">
          <div className="settings-section-icon" aria-hidden="true">
            <ShieldCheck size={22} weight="duotone" />
          </div>
          <div className="settings-section-main">
            <h2>隐私与数据边界</h2>
            <p>这里不是开关区，而是当前账号的数据边界说明：系统只保存学习闭环需要的安全摘要和产物索引。</p>
            <ul className="settings-boundary-list">
              <li>模型 Key 加密保存，页面和接口只返回脱敏摘要。</li>
              <li>Agent 轨迹只展示节点、耗时、引用数量和审核摘要，不展示原始提示词或完整资料原文。</li>
              <li>学习档案导出在报告页按课程生成，支持 Markdown、PDF 和 DOCX。</li>
            </ul>
            <Link className="secondary-action settings-inline-link" to={PATHS.reports}>
              去学习报告导出
            </Link>
          </div>
          <span className="settings-status">
            <Database size={16} weight="duotone" aria-hidden="true" />
            只读边界
          </span>
        </section>

        <section className="student-panel settings-section" role="region" aria-label="账号设置">
          <div className="settings-section-icon" aria-hidden="true">
            <UserCircle size={22} weight="duotone" />
          </div>
          <div className="settings-section-main">
            <h2>学生账号</h2>
            <p>昵称会同步到侧栏账号入口；邮箱和登录方式当前只读。</p>
            <dl className="settings-account-meta">
              <div>
                <dt>邮箱</dt>
                <dd>{authUser?.email ?? "当前登录账号"}</dd>
              </div>
              <div>
                <dt>身份</dt>
                <dd>{authUser ? authUser.role === "admin" ? "管理员" : "学生" : "未读取"}</dd>
              </div>
              <div>
                <dt>初始方式</dt>
                <dd>{starterModeLabel}</dd>
              </div>
            </dl>
            <label className="settings-inline-input">
              <span>昵称</span>
              <input
                value={nickname}
                onChange={(event) => {
                  setNickname(event.target.value);
                  if (accountFeedback) {
                    setAccountFeedback(null);
                  }
                }}
              />
            </label>
            <InlineFeedback message={accountFeedback} tone="warning" className="settings-inline-feedback" />
          </div>
          <div className="settings-action-stack">
            <button className="primary-action" type="button" onClick={saveSettings} disabled={updateAccountMutation.isPending}>
              {updateAccountMutation.isPending ? "保存中" : "保存设置"}
            </button>
          </div>
        </section>
        <ToastStack toast={toast} onDismiss={dismissToast} />
      </div>
    </PageFrame>
  );
}

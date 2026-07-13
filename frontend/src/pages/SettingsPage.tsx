import {
  ArrowSquareOut,
  CheckCircle,
  Database,
  FloppyDisk,
  Key,
  LockKey,
  Plus,
  Robot,
  ShieldCheck,
  Trash,
  UserCircle,
  WarningCircle
} from "@phosphor-icons/react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { changePassword, updateCurrentUser } from "../api/auth";
import { getApiErrorMessage } from "../api/errors";
import {
  createModelConfig,
  deleteModelConfig,
  listModelConfigs,
  setDefaultModelConfig,
  testModelConfig,
  testModelSettings,
  updateModelConfig,
  type ModelConfigRequest,
  type ModelConfigSummary,
  type ModelConfigUpdateRequest,
  type ModelConnectionOperation,
  type ModelConnectionTestSnapshot
} from "../api/settings";
import { PATHS } from "../app/routePaths";
import { InlineFeedback } from "../components/feedback/InlineFeedback";
import { ToastStack } from "../components/feedback/ToastStack";
import { useToastQueue } from "../components/feedback/useToastQueue";
import {
  getProviderPreset,
  inferProviderPresetId,
  MODEL_PROVIDER_PRESETS
} from "../config/modelProviders";
import { mapApiUserToStudentUser } from "../features/auth/authMappers";
import { useAuthStore } from "../features/auth/authStore";
import { ConnectionTestCard } from "../features/settings/ConnectionTestCard";
import { DeleteModelConfigDialog } from "../features/settings/DeleteModelConfigDialog";
import {
  SettingsNavigation,
  type SettingsSection
} from "../features/settings/SettingsNavigation";
import "../styles/settings.css";
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

const VALID_SECTIONS = new Set<SettingsSection>(["model", "account", "privacy"]);

function draftFromConfig(config: ModelConfigSummary): ModelConfigDraft {
  return {
    display_name: config.display_name,
    preset_id: inferProviderPresetId(config.base_url, config.preset_id),
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

function draftsMatch(left: ModelConfigDraft, right: ModelConfigDraft) {
  return left.display_name === right.display_name
    && left.preset_id === right.preset_id
    && left.base_url === right.base_url
    && !left.api_key
    && left.chat_model === right.chat_model
    && left.embedding_model === right.embedding_model;
}

function configTestLabel(config: ModelConfigSummary) {
  const chatTest = config.connection_tests?.chat;
  if (chatTest?.ok) return "回答已验证";
  if (chatTest && !chatTest.ok) return "回答测试失败";
  if (config.last_test_ok === true) return "回答已验证";
  if (config.last_test_ok === false) return "回答测试失败";
  return "尚未测试";
}

function testSnapshot(
  operation: ModelConnectionOperation,
  data: {
    ok: boolean;
    model?: string | null;
    chat_model?: string | null;
    message: string;
    code?: string | null;
    retryable?: boolean;
    tested_at?: string;
  }
): ModelConnectionTestSnapshot {
  return {
    operation,
    ok: data.ok,
    model: data.model ?? (operation === "chat" ? data.chat_model ?? null : null),
    message: data.message,
    code: data.code ?? null,
    retryable: data.retryable ?? false,
    tested_at: data.tested_at ?? new Date().toISOString()
  };
}

export function SettingsPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const queryClient = useQueryClient();
  const authUser = useAuthStore((state) => state.user);
  const authToken = useAuthStore((state) => state.token);
  const setSession = useAuthStore((state) => state.setSession);
  const clearSession = useAuthStore((state) => state.clearSession);
  const { toast, showToast, dismissToast } = useToastQueue();

  const requestedSection = searchParams.get("section") as SettingsSection | null;
  const activeSection = requestedSection && VALID_SECTIONS.has(requestedSection) ? requestedSection : "model";
  const [nickname, setNickname] = useState(authUser?.displayName ?? "");
  const [selectedConfigId, setSelectedConfigId] = useState<number | "new" | null>(null);
  const [draft, setDraft] = useState<ModelConfigDraft>(EMPTY_CONFIG_DRAFT);
  const [modelFeedback, setModelFeedback] = useState<string | null>(null);
  const [accountFeedback, setAccountFeedback] = useState<string | null>(null);
  const [passwordFeedback, setPasswordFeedback] = useState<string | null>(null);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [systemTests, setSystemTests] = useState<Partial<Record<ModelConnectionOperation, ModelConnectionTestSnapshot>>>({});

  const modelConfigsQuery = useQuery({
    queryKey: ["settings", "model-configs"],
    queryFn: listModelConfigs,
    staleTime: 30_000
  });
  const settingsList = modelConfigsQuery.data?.data ?? null;
  const configs = useMemo(() => settingsList?.configs ?? [], [settingsList?.configs]);
  const defaultConfigId = settingsList?.default_config_id ?? null;
  const defaultConfig = configs.find((config) => config.id === defaultConfigId) ?? null;
  const selectedConfig = useMemo(() => {
    if (selectedConfigId === "new") return null;
    if (typeof selectedConfigId === "number") {
      return configs.find((config) => config.id === selectedConfigId) ?? null;
    }
    return defaultConfig ?? configs[0] ?? null;
  }, [configs, defaultConfig, selectedConfigId]);
  const currentDraft = selectedConfigId === null && selectedConfig ? draftFromConfig(selectedConfig) : draft;
  const selectedPreset = getProviderPreset(currentDraft.preset_id);
  const activeConfigId = typeof selectedConfigId === "number" ? selectedConfigId : selectedConfig?.id ?? null;
  const isCreating = selectedConfigId === "new" || !selectedConfig;
  const isDirty = isCreating || (selectedConfig ? !draftsMatch(currentDraft, draftFromConfig(selectedConfig)) : false);
  const canSave = Boolean(currentDraft.display_name.trim() && currentDraft.base_url.trim() && currentDraft.chat_model.trim());
  const systemSummary = settingsList?.system_summary ?? null;
  const effectiveSource = defaultConfig ? "个人默认配置" : systemSummary?.source === "system" ? "服务器兜底" : "尚未配置";
  const effectiveChatReady = defaultConfig?.can_use_model ?? systemSummary?.can_use_model ?? false;
  const effectiveEmbeddingModel = defaultConfig?.embedding_model || systemSummary?.embedding_model || null;
  const starterModeLabel = authUser?.starterMode === "ai_intro" ? "示例课程开始" : "空白开始";

  function selectSection(section: SettingsSection) {
    const next = new URLSearchParams(searchParams);
    if (section === "model") next.delete("section");
    else next.set("section", section);
    setSearchParams(next, { replace: true });
  }

  const createConfigMutation = useMutation({
    mutationFn: (payload: ModelConfigRequest) => createModelConfig(payload),
    onSuccess: async (response) => {
      await queryClient.invalidateQueries({ queryKey: ["settings", "model-configs"] });
      await queryClient.invalidateQueries({ queryKey: ["settings", "model"] });
      setSelectedConfigId(response.data.id);
      setDraft(draftFromConfig(response.data));
      setModelFeedback(null);
      showToast("模型配置已保存。", "success");
    },
    onError: (error) => setModelFeedback(getApiErrorMessage(error, "模型配置保存失败，请检查配置内容。"))
  });

  const updateConfigMutation = useMutation({
    mutationFn: ({ configId, payload }: { configId: number; payload: ModelConfigUpdateRequest }) =>
      updateModelConfig(configId, payload),
    onSuccess: async (response) => {
      await queryClient.invalidateQueries({ queryKey: ["settings", "model-configs"] });
      await queryClient.invalidateQueries({ queryKey: ["settings", "model"] });
      setSelectedConfigId(response.data.id);
      setDraft(draftFromConfig(response.data));
      setModelFeedback(null);
      showToast("模型配置已保存。", "success");
    },
    onError: (error) => setModelFeedback(getApiErrorMessage(error, "模型配置保存失败，请检查名称、地址或密钥。"))
  });

  const defaultConfigMutation = useMutation({
    mutationFn: (configId: number) => setDefaultModelConfig(configId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["settings", "model-configs"] });
      await queryClient.invalidateQueries({ queryKey: ["settings", "model"] });
      showToast("已设为默认模型配置。", "success");
    },
    onError: (error) => setModelFeedback(getApiErrorMessage(error, "默认配置切换失败，请稍后重试。"))
  });

  const testConnectionMutation = useMutation({
    mutationFn: ({ configId, operation }: { configId: number | null; operation: ModelConnectionOperation }) =>
      configId === null ? testModelSettings(operation) : testModelConfig(configId, operation),
    onSuccess: async (response, variables) => {
      if (variables.configId === null) {
        setSystemTests((current) => ({
          ...current,
          [variables.operation]: testSnapshot(variables.operation, response.data)
        }));
      } else {
        await queryClient.invalidateQueries({ queryKey: ["settings", "model-configs"] });
      }
      showToast(response.data.message, response.data.ok ? "success" : "warning");
    },
    onError: (error) => setModelFeedback(getApiErrorMessage(error, "连接测试失败，请稍后重试。"))
  });

  const deleteConfigMutation = useMutation({
    mutationFn: (configId: number) => deleteModelConfig(configId),
    onSuccess: async (response) => {
      queryClient.setQueryData(["settings", "model-configs"], response);
      await queryClient.invalidateQueries({ queryKey: ["settings", "model"] });
      const nextConfig = response.data.configs.find((config) => config.id === response.data.default_config_id)
        ?? response.data.configs[0]
        ?? null;
      setSelectedConfigId(nextConfig?.id ?? "new");
      setDraft(nextConfig ? draftFromConfig(nextConfig) : newDraftFromPreset());
      setDeleteDialogOpen(false);
      showToast("模型配置已删除。", "success");
    },
    onError: (error) => setModelFeedback(getApiErrorMessage(error, "模型配置删除失败，请稍后重试。"))
  });

  const updateAccountMutation = useMutation({
    mutationFn: updateCurrentUser,
    onSuccess: (response) => {
      if (authToken) {
        setSession({ token: authToken, user: mapApiUserToStudentUser(response.data) });
      }
      setNickname(response.data.display_name);
      setAccountFeedback(null);
      showToast("昵称已更新。", "success");
    },
    onError: (error) => setAccountFeedback(getApiErrorMessage(error, "昵称保存失败，请稍后重试。"))
  });

  const changePasswordMutation = useMutation({
    mutationFn: changePassword,
    onSuccess: () => {
      queryClient.clear();
      clearSession();
      navigate(PATHS.login, {
        replace: true,
        state: { notice: "密码已更新，请使用新密码重新登录。" }
      });
    },
    onError: (error) => setPasswordFeedback(getApiErrorMessage(error, "密码修改失败，请稍后重试。"))
  });

  const savePending = createConfigMutation.isPending || updateConfigMutation.isPending;

  function updateDraft(field: keyof ModelConfigDraft, value: string) {
    const baseDraft = selectedConfigId === null && selectedConfig ? draftFromConfig(selectedConfig) : draft;
    if (selectedConfigId === null && selectedConfig) setSelectedConfigId(selectedConfig.id);
    setDraft({ ...baseDraft, [field]: value });
    setModelFeedback(null);
  }

  function applyProviderPreset(presetId: string) {
    const preset = getProviderPreset(presetId);
    if (selectedConfigId === null && selectedConfig) setSelectedConfigId(selectedConfig.id);
    setDraft({
      ...currentDraft,
      preset_id: preset.id,
      base_url: preset.id === "custom" ? currentDraft.base_url : preset.baseUrl,
      chat_model: preset.id === "custom" ? currentDraft.chat_model : preset.chatModel,
      embedding_model: preset.id === "custom" ? currentDraft.embedding_model : (preset.embeddingModel ?? "")
    });
    setModelFeedback(null);
  }

  function createNewConfig() {
    setSelectedConfigId("new");
    setDraft(newDraftFromPreset());
    setModelFeedback(null);
  }

  function selectConfig(config: ModelConfigSummary) {
    setSelectedConfigId(config.id);
    setDraft(draftFromConfig(config));
    setModelFeedback(null);
  }

  function saveModelConfiguration() {
    if (!canSave) {
      setModelFeedback("请先补全配置名称、Base URL 和回答模型。");
      return;
    }
    const apiKey = currentDraft.api_key.trim();
    const payload = {
      display_name: currentDraft.display_name.trim(),
      preset_id: currentDraft.preset_id,
      provider: "openai_compatible" as const,
      base_url: currentDraft.base_url.trim(),
      chat_model: currentDraft.chat_model.trim(),
      embedding_model: currentDraft.embedding_model.trim(),
      ...(apiKey ? { api_key: apiKey } : {})
    };
    if (isCreating || activeConfigId === null) {
      createConfigMutation.mutate({ ...payload, make_default: configs.length === 0 });
    } else {
      updateConfigMutation.mutate({ configId: activeConfigId, payload });
    }
  }

  function runConnectionTest(operation: ModelConnectionOperation, configId: number | null = activeConfigId) {
    if (configId !== null && isDirty) {
      setModelFeedback("当前配置有未保存修改，请先保存再测试。");
      return;
    }
    testConnectionMutation.mutate({ configId, operation });
  }

  function saveNickname() {
    const value = nickname.trim();
    if (!value) {
      setAccountFeedback("昵称不能为空。");
      return;
    }
    updateAccountMutation.mutate({ display_name: value });
  }

  function submitPasswordChange() {
    setPasswordFeedback(null);
    if (!currentPassword || !newPassword || !confirmPassword) {
      setPasswordFeedback("请完整填写当前密码、新密码和确认密码。");
      return;
    }
    if (newPassword !== confirmPassword) {
      setPasswordFeedback("两次输入的新密码不一致。");
      return;
    }
    if (newPassword.length < 8 || !/[A-Za-z]/.test(newPassword) || !/\d/.test(newPassword)) {
      setPasswordFeedback("新密码至少 8 位，并同时包含字母和数字。");
      return;
    }
    changePasswordMutation.mutate({ current_password: currentPassword, new_password: newPassword });
  }

  const testPending = (operation: ModelConnectionOperation) =>
    testConnectionMutation.isPending && testConnectionMutation.variables?.operation === operation;

  return (
    <>
      <PageFrame title="设置" titleMode="sr-only" variant="wide-workspace">
        <div className="settings-workspace">
          <header className="settings-toolbar">
            <div className="settings-toolbar-identity">
              <span aria-hidden="true"><Robot size={20} weight="duotone" /></span>
              <div>
                <strong>系统设置</strong>
                <small>学生账号与 AI 连接</small>
              </div>
            </div>
            <div className="settings-effective-state" aria-label="当前模型状态">
              <span>{effectiveSource}</span>
              <strong>{effectiveChatReady ? "回答可用" : "回答未就绪"}</strong>
              <small>{effectiveEmbeddingModel ? `向量 · ${effectiveEmbeddingModel}` : "向量未配置"}</small>
            </div>
          </header>

          <div className="settings-workspace-body">
            <SettingsNavigation activeSection={activeSection} onSelect={selectSection} />
            <main className="settings-content" aria-label="设置内容">
              {activeSection === "model" ? (
                <section className="settings-panel" role="region" aria-label="模型设置">
                  <header className="settings-panel-heading">
                    <div>
                      <span>AI 运行基础</span>
                      <h2>模型连接</h2>
                      <p>回答模型负责生成内容，向量模型负责资料语义检索；两项状态分别验证。</p>
                    </div>
                    <button type="button" className="settings-new-button" onClick={createNewConfig}>
                      <Plus size={16} weight="bold" aria-hidden="true" />
                      新建配置
                    </button>
                  </header>

                  {modelConfigsQuery.isPending ? (
                    <div className="settings-query-state" role="status">
                      <Robot size={19} weight="duotone" aria-hidden="true" />
                      正在读取模型配置…
                    </div>
                  ) : null}
                  {modelConfigsQuery.isError ? (
                    <div className="settings-query-state failed" role="alert">
                      <WarningCircle size={19} weight="fill" aria-hidden="true" />
                      <span>模型配置暂时无法读取，当前表单不会提交。</span>
                      <button type="button" onClick={() => void modelConfigsQuery.refetch()}>重新加载</button>
                    </div>
                  ) : null}

                  {!modelConfigsQuery.isError && !defaultConfig ? (
                    <section className="settings-system-fallback" aria-label="服务器模型配置">
                      <header>
                        <div>
                          <span>当前运行来源</span>
                          <strong>{systemSummary?.source === "system" ? "服务器兜底配置" : "尚未配置可用模型"}</strong>
                        </div>
                        <small>服务器配置只读，个人配置保存并设为默认后将优先使用。</small>
                      </header>
                      <div className="settings-test-grid">
                        <ConnectionTestCard
                          operation="chat"
                          model={systemSummary?.chat_model ?? null}
                          result={systemTests.chat}
                          dirty={false}
                          disabled={testConnectionMutation.isPending}
                          pending={testPending("chat")}
                          onTest={() => runConnectionTest("chat", null)}
                        />
                        <ConnectionTestCard
                          operation="embedding"
                          model={systemSummary?.embedding_model ?? null}
                          result={systemTests.embedding}
                          dirty={false}
                          disabled={testConnectionMutation.isPending}
                          pending={testPending("embedding")}
                          onTest={() => runConnectionTest("embedding", null)}
                        />
                      </div>
                    </section>
                  ) : null}

                  <div className="settings-model-layout" aria-busy={modelConfigsQuery.isPending}>
                    <aside className="settings-config-list" aria-label="模型配置列表">
                      <header>
                        <span>个人配置</span>
                        <small>{configs.length} 套</small>
                      </header>
                      <div className="settings-config-scroll">
                        {configs.map((config) => (
                          <button
                            key={config.id}
                            type="button"
                            className={config.id === activeConfigId && selectedConfigId !== "new" ? "active" : undefined}
                            onClick={() => selectConfig(config)}
                          >
                            <span className="settings-config-row-title">
                              <strong>{config.display_name}</strong>
                              {config.is_default ? <small>默认</small> : null}
                            </span>
                            <span>{config.chat_model || "未填写回答模型"}</span>
                            <em className={configTestLabel(config).includes("失败") ? "failed" : ""}>{configTestLabel(config)}</em>
                          </button>
                        ))}
                        {configs.length === 0 && selectedConfigId !== "new" ? (
                          <button type="button" className="settings-config-empty" onClick={createNewConfig}>
                            <Plus size={18} weight="duotone" aria-hidden="true" />
                            <strong>建立第一套个人配置</strong>
                            <span>不会覆盖服务器配置</span>
                          </button>
                        ) : null}
                        {selectedConfigId === "new" ? (
                          <button type="button" className="active settings-config-draft">
                            <span className="settings-config-row-title"><strong>新建配置</strong><small>草稿</small></span>
                            <span>{currentDraft.chat_model || "待填写回答模型"}</span>
                            <em>保存后可测试</em>
                          </button>
                        ) : null}
                      </div>
                    </aside>

                    <section className="settings-config-editor" aria-label="模型配置编辑器">
                      <header>
                        <div>
                          <span>{isCreating ? "新配置" : selectedConfig?.is_default ? "默认配置" : "个人配置"}</span>
                          <h3>{currentDraft.display_name || "未命名配置"}</h3>
                        </div>
                        {selectedConfig?.api_key_masked ? (
                          <span className="settings-key-summary"><Key size={15} weight="duotone" />{selectedConfig.api_key_masked}</span>
                        ) : null}
                      </header>

                      <div className="settings-form-grid">
                        <label>
                          <span>配置名称</span>
                          <input aria-label="配置名称" value={currentDraft.display_name} onChange={(event) => updateDraft("display_name", event.target.value)} />
                        </label>
                        <label>
                          <span>Provider 预设</span>
                          <select aria-label="Provider 预设" value={currentDraft.preset_id} onChange={(event) => applyProviderPreset(event.target.value)}>
                            {MODEL_PROVIDER_PRESETS.map((preset) => <option key={preset.id} value={preset.id}>{preset.name}</option>)}
                          </select>
                        </label>
                        <div className="settings-provider-context">
                          <strong>{selectedPreset.name}</strong>
                          <span>{selectedPreset.description}</span>
                          {selectedPreset.modelsHint ? <small>{selectedPreset.modelsHint}</small> : null}
                        </div>
                        <label className="settings-form-span">
                          <span>Base URL</span>
                          <input aria-label="Base URL" value={currentDraft.base_url} onChange={(event) => updateDraft("base_url", event.target.value)} />
                        </label>
                        <label>
                          <span>{selectedPreset.apiKeyLabel}</span>
                          <input
                            aria-label="API Key"
                            type="password"
                            autoComplete="off"
                            value={currentDraft.api_key}
                            placeholder={selectedConfig?.has_api_key ? "留空保留已保存密钥" : selectedPreset.apiKeyPlaceholder}
                            onChange={(event) => updateDraft("api_key", event.target.value)}
                          />
                        </label>
                        <label>
                          <span>回答模型</span>
                          <input aria-label="回答模型" value={currentDraft.chat_model} onChange={(event) => updateDraft("chat_model", event.target.value)} />
                        </label>
                      </div>

                      <details className="settings-embedding-settings" open={Boolean(currentDraft.embedding_model)}>
                        <summary>向量检索设置</summary>
                        <label>
                          <span>向量模型</span>
                          <input
                            aria-label="向量模型"
                            value={currentDraft.embedding_model}
                            placeholder="可留空，届时使用服务器配置或关键词 fallback"
                            onChange={(event) => updateDraft("embedding_model", event.target.value)}
                          />
                        </label>
                        <p>向量模型只用于资料与课程切片的语义召回，不参与回答生成。</p>
                      </details>

                      {!isCreating ? (
                        <div className="settings-test-grid">
                          <ConnectionTestCard
                            operation="chat"
                            model={selectedConfig?.chat_model ?? null}
                            result={selectedConfig?.connection_tests?.chat ?? null}
                            dirty={isDirty}
                            disabled={isDirty || testConnectionMutation.isPending}
                            pending={testPending("chat")}
                            onTest={() => runConnectionTest("chat")}
                          />
                          <ConnectionTestCard
                            operation="embedding"
                            model={selectedConfig?.embedding_model ?? null}
                            result={selectedConfig?.connection_tests?.embedding ?? null}
                            dirty={isDirty}
                            disabled={isDirty || testConnectionMutation.isPending}
                            pending={testPending("embedding")}
                            onTest={() => runConnectionTest("embedding")}
                          />
                        </div>
                      ) : (
                        <div className="settings-save-first-note">
                          <LockKey size={18} weight="duotone" aria-hidden="true" />
                          保存配置后才能执行真实连接测试。
                        </div>
                      )}

                      <InlineFeedback message={modelFeedback} tone="warning" className="settings-inline-feedback" />
                      <footer className="settings-editor-actions">
                        <div>
                          {!isCreating && isDirty ? <span><WarningCircle size={15} weight="fill" />有未保存修改</span> : null}
                          {!isCreating && !isDirty ? <span><CheckCircle size={15} weight="fill" />配置已保存</span> : null}
                        </div>
                        {!isCreating ? (
                          <button
                            type="button"
                            className="settings-delete-button"
                            onClick={() => setDeleteDialogOpen(true)}
                            disabled={deleteConfigMutation.isPending}
                            aria-label="删除配置"
                          >
                            <Trash size={16} weight="duotone" aria-hidden="true" />
                          </button>
                        ) : null}
                        {!isCreating && !selectedConfig?.is_default ? (
                          <button type="button" className="secondary-action" onClick={() => activeConfigId && defaultConfigMutation.mutate(activeConfigId)} disabled={defaultConfigMutation.isPending || isDirty}>
                            设为默认
                          </button>
                        ) : null}
                        <button type="button" className="primary-action" onClick={saveModelConfiguration} disabled={!canSave || savePending}>
                          <FloppyDisk size={16} weight="bold" aria-hidden="true" />
                          {savePending ? "保存中" : "保存配置"}
                        </button>
                      </footer>
                    </section>
                  </div>
                </section>
              ) : null}

              {activeSection === "account" ? (
                <section className="settings-panel settings-account-panel" role="region" aria-label="账号设置">
                  <header className="settings-panel-heading">
                    <div>
                      <span>个人与登录</span>
                      <h2>账号安全</h2>
                      <p>昵称用于学习空间展示；密码修改后，所有已登录设备都需要重新登录。</p>
                    </div>
                  </header>
                  <div className="settings-account-grid">
                    <section>
                      <header><UserCircle size={20} weight="duotone" /><div><strong>基本信息</strong><span>邮箱和账号身份不可在这里修改</span></div></header>
                      <dl className="settings-account-meta">
                        <div><dt>邮箱</dt><dd>{authUser?.email ?? "当前登录账号"}</dd></div>
                        <div><dt>身份</dt><dd>{authUser?.role === "admin" ? "管理员" : "学生"}</dd></div>
                        <div><dt>初始方式</dt><dd>{starterModeLabel}</dd></div>
                      </dl>
                      <label className="settings-account-field">
                        <span>昵称</span>
                        <input aria-label="昵称" value={nickname} onChange={(event) => { setNickname(event.target.value); setAccountFeedback(null); }} />
                      </label>
                      <InlineFeedback message={accountFeedback} tone="warning" className="settings-inline-feedback" />
                      <button type="button" className="primary-action" onClick={saveNickname} disabled={updateAccountMutation.isPending}>
                        {updateAccountMutation.isPending ? "保存中" : "保存昵称"}
                      </button>
                    </section>

                    <section>
                      <header><LockKey size={20} weight="duotone" /><div><strong>修改密码</strong><span>修改后会退出所有已有登录状态</span></div></header>
                      <div className="settings-password-form">
                        <label><span>当前密码</span><input aria-label="当前密码" type="password" autoComplete="current-password" value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} /></label>
                        <label><span>新密码</span><input aria-label="新密码" type="password" autoComplete="new-password" value={newPassword} onChange={(event) => setNewPassword(event.target.value)} /></label>
                        <label><span>确认新密码</span><input aria-label="确认新密码" type="password" autoComplete="new-password" value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} /></label>
                        <small>至少 8 位，并同时包含字母和数字。</small>
                      </div>
                      <InlineFeedback message={passwordFeedback} tone="warning" className="settings-inline-feedback" />
                      <button type="button" className="primary-action" onClick={submitPasswordChange} disabled={changePasswordMutation.isPending}>
                        {changePasswordMutation.isPending ? "更新中" : "更新密码并退出登录"}
                      </button>
                    </section>
                  </div>
                </section>
              ) : null}

              {activeSection === "privacy" ? (
                <section className="settings-panel settings-privacy-panel" role="region" aria-label="隐私与数据">
                  <header className="settings-panel-heading">
                    <div>
                      <span>数据边界</span>
                      <h2>数据隐私</h2>
                      <p>这里说明 EduNova 实际保存什么、如何使用，不提供没有后端能力支撑的装饰性开关。</p>
                    </div>
                  </header>
                  <div className="settings-privacy-list">
                    <article><Key size={21} weight="duotone" /><div><strong>模型密钥</strong><p>个人 API Key 使用 Fernet 加密保存，页面和接口只返回脱敏摘要。</p></div><span>加密存储</span></article>
                    <article><ShieldCheck size={21} weight="duotone" /><div><strong>Agent 协作轨迹</strong><p>只展示节点、耗时、引用数量和安全审核摘要，不保存原始提示词或完整模型输入。</p></div><span>安全摘要</span></article>
                    <article><Database size={21} weight="duotone" /><div><strong>学习资料</strong><p>资料、课程和会话按账号隔离；检索只在当前用户明确选择的范围内执行。</p></div><span>用户隔离</span></article>
                    <article><ArrowSquareOut size={21} weight="duotone" /><div><strong>学习档案</strong><p>报告页可以按课程导出 Markdown、PDF 或 DOCX，导出任务不会包含密钥和原始模型上下文。</p></div><Link to={PATHS.reports}>前往报告页</Link></article>
                  </div>
                </section>
              ) : null}
            </main>
          </div>
          <ToastStack toast={toast} onDismiss={dismissToast} />
        </div>
      </PageFrame>
      <DeleteModelConfigDialog
        open={deleteDialogOpen}
        configName={selectedConfig?.display_name ?? "当前配置"}
        pending={deleteConfigMutation.isPending}
        onOpenChange={setDeleteDialogOpen}
        onConfirm={() => activeConfigId && deleteConfigMutation.mutate(activeConfigId)}
      />
    </>
  );
}

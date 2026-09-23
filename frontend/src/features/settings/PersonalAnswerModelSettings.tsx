import { CheckCircle, FloppyDisk, Key, Robot, WarningCircle } from "@phosphor-icons/react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { getApiErrorMessage } from "../../api/errors";
import {
  getModelSettings,
  saveModelSettings,
  testModelSettings,
  type ModelConnectionTestResponse,
  type ModelSettingsSummary
} from "../../api/settings";
import { TEXT_CHAT_MODEL_PROVIDER_PRESETS, getChatProviderPreset } from "../../config/modelProviders";
import { InlineFeedback } from "../../components/feedback/InlineFeedback";
import { ConnectionTestCard } from "./ConnectionTestCard";

type AnswerModelDraft = {
  presetId: string;
  baseUrl: string;
  apiKey: string;
  chatModel: string;
};

function draftFromSummary(summary: ModelSettingsSummary): AnswerModelDraft {
  const preset = getChatProviderPreset(
    summary.base_url?.includes("spark-api-open.xf-yun.com")
      ? "spark"
      : summary.base_url?.includes("dashscope.aliyuncs.com")
        ? "qwen"
        : "custom"
  );
  return {
    presetId: preset.id,
    baseUrl: summary.base_url ?? preset.baseUrl,
    apiKey: "",
    chatModel: summary.chat_model ?? preset.chatModel
  };
}

export function PersonalAnswerModelSettings() {
  const queryClient = useQueryClient();
  const modelQuery = useQuery({ queryKey: ["settings", "model"], queryFn: getModelSettings, staleTime: 30_000 });
  const [draft, setDraft] = useState<AnswerModelDraft | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<ModelConnectionTestResponse | null>(null);
  const [visionResult, setVisionResult] = useState<ModelConnectionTestResponse | null>(null);
  const summary = modelQuery.data?.data ?? null;
  const currentDraft = draft ?? draftFromSummary(summary ?? {
    source: "none", provider: "openai_compatible", base_url: null, chat_model: null, embedding_model: null,
    has_api_key: false, api_key_masked: null, can_use_model: false, can_use_embedding_model: false
  });
  const preset = getChatProviderPreset(currentDraft.presetId);

  const saveMutation = useMutation({
    mutationFn: saveModelSettings,
    onSuccess: async () => {
      setFeedback(null);
      setDraft(null);
      setTestResult(null);
      setVisionResult(null);
      await queryClient.invalidateQueries({ queryKey: ["settings", "model"] });
    },
    onError: (error) => setFeedback(getApiErrorMessage(error, "回答模型保存失败，请检查地址、模型和密钥。"))
  });
  const testMutation = useMutation({
    mutationFn: () => testModelSettings("chat"),
    onSuccess: (response) => setTestResult(response.data),
    onError: (error) => setFeedback(getApiErrorMessage(error, "连接验证失败，请稍后重试。"))
  });
  const visionMutation = useMutation({
    mutationFn: () => testModelSettings("vision"),
    onSuccess: async (response) => {
      setVisionResult(response.data);
      await queryClient.invalidateQueries({ queryKey: ["settings", "model"] });
    },
    onError: (error) => setFeedback(getApiErrorMessage(error, "图片能力验证失败，可稍后重试。"))
  });
  const dirty = draft !== null;
  const testing = testMutation.isPending || visionMutation.isPending;
  const visionLabel = summary?.vision_status === "verified" ? "主模型图片验证通过，使用同一组凭证。"
    : summary?.vision_status === "unavailable" ? "图片验证未通过，可重试；不自动切换服务器模型。"
    : summary?.can_use_model ? "待验证主模型图片能力；验证前仅使用文本。" : "请先配置主模型。";

  const requiresKey = !preset.allowEmptyApiKey && !summary?.has_api_key;
  const canSave = Boolean(currentDraft.baseUrl.trim() && currentDraft.chatModel.trim() && (!requiresKey || currentDraft.apiKey.trim()));

  function applyPreset(presetId: string) {
    const next = getChatProviderPreset(presetId);
    setDraft({ presetId, baseUrl: next.id === "custom" ? currentDraft.baseUrl : next.baseUrl, apiKey: "", chatModel: next.id === "custom" ? currentDraft.chatModel : next.chatModel });
    setFeedback(null);
  }

  return (
    <section className="settings-panel personal-answer-model" role="region" aria-label="回答模型设置">
      <header className="settings-panel-heading">
        <div>
          <h2>回答模型</h2>
          <p>一组主模型配置用于回答与后台生成；通过图片验证后也用于看图。</p>
        </div>
      </header>

      <div className="personal-model-routing" aria-label="模型路由说明">
        <article><Robot size={19} weight="duotone" /><div><strong>日常回答</strong><span>{summary?.can_use_model ? `当前使用${summary.source === "user" ? "你的" : "服务器的"} ${summary.chat_model}` : "尚未配置可用主模型"}</span></div></article>
        <article><CheckCircle size={19} weight="duotone" /><div><strong>资源、路径、练习与报告</strong><span>{summary?.source === "user" ? "跟随你的回答模型" : "由部署者配置生成模型；未单独配置时跟随主模型"}</span></div></article>
        <article><Key size={19} weight="duotone" /><div><strong>图片理解与资料检索</strong><span>{visionLabel} 资料检索由服务器管理。</span></div></article>
      </div>

      {modelQuery.isPending ? <div className="settings-query-state" role="status">正在读取回答模型配置...</div> : null}
      {modelQuery.isError ? <div className="settings-query-state failed" role="alert"><WarningCircle size={18} weight="fill" />读取失败，请刷新后重试。</div> : null}

      {!modelQuery.isError ? <section className="personal-model-editor" aria-label="回答模型编辑器">
        <label><span>回答服务商</span><select aria-label="回答服务商" value={currentDraft.presetId} onChange={(event) => applyPreset(event.target.value)}>{TEXT_CHAT_MODEL_PROVIDER_PRESETS.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        <label><span>回答模型</span><input aria-label="回答模型" value={currentDraft.chatModel} onChange={(event) => setDraft({ ...currentDraft, chatModel: event.target.value })} /></label>
        <label className="personal-model-wide"><span>回答 Base URL</span><input aria-label="回答 Base URL" value={currentDraft.baseUrl} onChange={(event) => setDraft({ ...currentDraft, baseUrl: event.target.value })} /></label>
        <label className="personal-model-wide"><span>{preset.apiKeyLabel}</span><input aria-label="回答 API Key" type="password" autoComplete="off" value={currentDraft.apiKey} placeholder={summary?.has_api_key ? "留空保留已保存密钥" : preset.apiKeyPlaceholder} onChange={(event) => setDraft({ ...currentDraft, apiKey: event.target.value })} /></label>
        <div className="personal-model-provider"><strong>{preset.name}</strong><span>{preset.description}</span></div>
        <InlineFeedback message={feedback} tone="warning" className="settings-inline-feedback" />
        <footer className="settings-editor-actions">
          <span>{summary?.source === "user" ? `个人连接不会自动回退到服务器凭证 ${summary.api_key_masked ?? ""}` : "未设置个人模型时，是否可用取决于服务器配置"}</span>
          <button type="button" className="secondary-action" onClick={() => testMutation.mutate()} disabled={!summary?.can_use_model || testing || dirty || saveMutation.isPending}>{testMutation.isPending ? "验证中" : "验证回答连接"}</button>
          <button type="button" className="primary-action" onClick={() => saveMutation.mutate({ provider: "openai_compatible", base_url: currentDraft.baseUrl.trim(), chat_model: currentDraft.chatModel.trim(), ...(currentDraft.apiKey.trim() ? { api_key: currentDraft.apiKey.trim() } : {}) })} disabled={!canSave || saveMutation.isPending}><FloppyDisk size={16} weight="bold" />{saveMutation.isPending ? "保存中" : "保存回答模型"}</button>
        </footer>
        <ConnectionTestCard operation="chat" model={summary?.chat_model ?? null} result={dirty ? null : testResult} disabled={testing || dirty || saveMutation.isPending || !summary?.can_use_model} pending={testMutation.isPending} dirty={dirty} onTest={() => testMutation.mutate()} />
        <p>图片验证会向当前模型发送一张合成测试图片，可能产生少量模型费用。连接失败不等于模型不支持图片。</p>
        <ConnectionTestCard operation="vision" model={summary?.chat_model ?? null} result={dirty ? null : visionResult} disabled={testing || dirty || saveMutation.isPending || !summary?.can_use_model} pending={visionMutation.isPending} dirty={dirty} onTest={() => visionMutation.mutate()} />
      </section> : null}
    </section>
  );
}

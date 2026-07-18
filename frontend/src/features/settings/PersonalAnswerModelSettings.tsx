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
      await queryClient.invalidateQueries({ queryKey: ["settings", "model"] });
    },
    onError: (error) => setFeedback(getApiErrorMessage(error, "回答模型保存失败，请检查地址、模型和密钥。"))
  });
  const testMutation = useMutation({
    mutationFn: () => testModelSettings("chat"),
    onSuccess: (response) => setTestResult(response.data),
    onError: (error) => setFeedback(getApiErrorMessage(error, "连接验证失败，请稍后重试。"))
  });

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
          <p>个人设置只影响你的回答与后台生成任务。</p>
        </div>
      </header>

      <div className="personal-model-routing" aria-label="模型路由说明">
        <article><Robot size={19} weight="duotone" /><div><strong>日常回答</strong><span>{summary?.source === "user" ? `当前使用你的 ${summary.chat_model}` : "未配置个人模型时使用服务器 X2-Flash"}</span></div></article>
        <article><CheckCircle size={19} weight="duotone" /><div><strong>资源、路径、练习与报告</strong><span>{summary?.source === "user" ? "跟随你的回答模型" : "使用服务器千问"}</span></div></article>
        <article><Key size={19} weight="duotone" /><div><strong>图片理解与资料检索</strong><span>由服务器托管，不使用个人密钥。</span></div></article>
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
          <span>{summary?.source === "user" ? `已保存密钥 ${summary.api_key_masked ?? ""}` : "服务器默认始终可作为兜底"}</span>
          <button type="button" className="secondary-action" onClick={() => testMutation.mutate()} disabled={!summary?.can_use_model || testMutation.isPending}>{testMutation.isPending ? "验证中" : "验证回答连接"}</button>
          <button type="button" className="primary-action" onClick={() => saveMutation.mutate({ provider: "openai_compatible", base_url: currentDraft.baseUrl.trim(), chat_model: currentDraft.chatModel.trim(), ...(currentDraft.apiKey.trim() ? { api_key: currentDraft.apiKey.trim() } : {}) })} disabled={!canSave || saveMutation.isPending}><FloppyDisk size={16} weight="bold" />{saveMutation.isPending ? "保存中" : "保存回答模型"}</button>
        </footer>
        <ConnectionTestCard operation="chat" model={summary?.chat_model ?? null} result={testResult} disabled={testMutation.isPending} pending={testMutation.isPending} dirty={false} onTest={() => testMutation.mutate()} />
      </section> : null}
    </section>
  );
}

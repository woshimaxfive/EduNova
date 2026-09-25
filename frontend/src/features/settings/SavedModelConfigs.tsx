import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createModelConfig, listModelConfigs, setDefaultModelConfig } from "../../api/settings";
import { getApiErrorMessage } from "../../api/errors";
import { getChatProviderPreset, TEXT_CHAT_MODEL_PROVIDER_PRESETS } from "../../config/modelProviders";
import { ModelAddressHint } from "./ModelAddressHint";
import { ModelCatalogPicker } from "./ModelCatalogPicker";

export function SavedModelConfigs({ disabled, onSwitch, onBusyChange }: { disabled: boolean; onSwitch: () => void; onBusyChange?: (busy: boolean) => void }) {
  const client = useQueryClient();
  const query = useQuery({ queryKey: ["settings", "model-configs"], queryFn: listModelConfigs });
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState("");
  const [presetId, setPresetId] = useState("custom");
  const [baseUrl, setBaseUrl] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [model, setModel] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [confirmId, setConfirmId] = useState<number | null>(null);
  const preset = getChatProviderPreset(presetId);
  async function refresh() {
    await Promise.all([
      client.invalidateQueries({ queryKey: ["settings", "model-configs"] }),
      client.invalidateQueries({ queryKey: ["settings", "model"] })
    ]);
  }
  const save = useMutation({
    onMutate: () => onBusyChange?.(true),
    onSettled: () => onBusyChange?.(false),
    mutationFn: () => createModelConfig({ display_name: name.trim(), provider: "openai_compatible", preset_id: presetId, base_url: baseUrl.trim(), api_key: apiKey.trim() || undefined, chat_model: model.trim(), make_default: false, make_generation_default: false }),
    onSuccess: async () => { setEditing(false); setApiKey(""); setName(""); setModel(""); setBaseUrl(""); setMessage("配置已保存；已有个人配置时不会自动切换，首套个人配置将自动启用。"); await refresh(); },
    onError: (error) => setMessage(getApiErrorMessage(error, "保存失败，请检查配置名称、地址和密钥。"))
  });
  const activate = useMutation({
    onMutate: () => onBusyChange?.(true),
    onSettled: () => onBusyChange?.(false),
    mutationFn: setDefaultModelConfig,
    onSuccess: async () => { setConfirmId(null); onSwitch(); setMessage("已切换主模型，请在下方验证连接及图片能力。"); await refresh(); },
    onError: (error) => setMessage(getApiErrorMessage(error, "切换失败，当前配置未能更新，请重试。"))
  });
  const busy = disabled || save.isPending || activate.isPending;
  const configs = query.data?.data.configs.filter((config) => config.chat_model) ?? [];
  return <details className="saved-model-configs">
    <summary>管理多套配置（可选）</summary>
    <p>只配一个主模型即可使用。可额外保存日常、复杂任务或备用配置；不会自动切换服务商。启用后在下方编辑当前配置。</p>
    {query.isPending ? <p role="status">正在读取配置…</p> : null}
    {query.isError ? <p role="alert">配置读取失败。<button type="button" onClick={() => void query.refetch()}>重试</button></p> : null}
    {configs.map((config) => <article key={config.id}>
      <div><strong>{config.display_name}</strong><span>{config.chat_model} · {config.base_url}</span><small>{config.api_key_masked ?? "无密钥"}</small></div>
      {config.is_default ? <span>当前使用</span> : <button type="button" className="secondary-action" disabled={busy || editing} onClick={() => setConfirmId(config.id)}>启用 {config.display_name}</button>}
    </article>)}
    {confirmId !== null ? <div role="group" aria-label="确认切换主模型">
      <p>将切换到“{configs.find((config) => config.id === confirmId)?.display_name}”。后续模型调用将使用该配置，学习内容会发送至该服务商。请先等当前回答和后台生成任务结束，再确认切换。</p>
      <button type="button" className="primary-action" disabled={busy} onClick={() => activate.mutate(confirmId)}>确认切换主模型</button>
      <button type="button" className="secondary-action" disabled={activate.isPending} onClick={() => setConfirmId(null)}>取消切换</button>
    </div> : null}
    {message ? <p role="status">{message}</p> : null}
    {disabled ? <p>请先保存当前编辑内容或等待连接验证结束，再管理配置。</p> : null}
    {!editing ? <button type="button" className="secondary-action" disabled={busy || query.isPending || query.isError} onClick={() => { setEditing(true); setConfirmId(null); setMessage(null); }}>添加模型配置</button> : <fieldset disabled={busy} className="personal-model-editor">
      <legend>新增模型配置</legend>
      <label><span>配置名称</span><input aria-label="配置名称" maxLength={80} value={name} onChange={(e) => setName(e.target.value)} /></label>
      <label><span>服务商</span><select aria-label="新配置服务商" value={presetId} onChange={(e) => { const next = getChatProviderPreset(e.target.value); setPresetId(next.id); setBaseUrl(next.id === "custom" ? baseUrl : next.baseUrl); setModel(next.id === "custom" ? model : next.chatModel); setApiKey(""); }}>{TEXT_CHAT_MODEL_PROVIDER_PRESETS.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
      <label className="personal-model-wide"><span>Base URL</span><input aria-label="新配置 Base URL" value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} /></label>
      <ModelAddressHint value={baseUrl} example={preset.baseUrl} onChange={setBaseUrl} />
      <label><span>API Key</span><input aria-label="新配置 API Key" type="password" autoComplete="off" value={apiKey} onChange={(e) => setApiKey(e.target.value)} /></label>
      <label><span>模型名称</span><input aria-label="新配置模型名称" maxLength={120} value={model} onChange={(e) => setModel(e.target.value)} /></label>
      <ModelCatalogPicker key={JSON.stringify([baseUrl, apiKey])} baseUrl={baseUrl} apiKey={apiKey} canUseSavedKey={false} onSelect={setModel} />
      <p className="personal-model-wide">新配置需要单独填写 Key，不复制原配置密钥。首套个人配置保存后自动启用，其余配置仅保存。</p>
      <button type="button" className="primary-action" disabled={!name.trim() || !baseUrl.trim() || !model.trim() || (!preset.allowEmptyApiKey && !apiKey.trim())} onClick={() => save.mutate()}>{save.isPending ? "保存中…" : "保存新配置"}</button>
      <button type="button" className="secondary-action" onClick={() => { setEditing(false); setApiKey(""); }}>取消新增</button>
    </fieldset>}
  </details>;
}

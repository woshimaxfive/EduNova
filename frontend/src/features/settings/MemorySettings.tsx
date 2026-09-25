import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { getApiErrorMessage } from "../../api/errors";
import { clearConversationMemory, getPrivacySettings, updatePrivacySettings } from "../../api/settings";
import { clearMemoryIndexes, correctMemory, createMemory, deleteMemory, exportMemories, listMemories, rebuildMemoryIndexes,
  type MemoryFactInput, type MemoryItem, type MemoryLayer } from "../../api/memory";
import { ConfirmDialog } from "../../components/primitives/Dialog";
import { useAuthStore } from "../auth/authStore";
import "../../styles/settings-memory.css";

const categories = { goal: "学习目标", preference: "学习偏好", difficulty: "长期困难", habit: "复习习惯" };
type Action = { kind: "delete"; item: MemoryItem } | { kind: "clear" | "indexes" };

export function MemorySettings() {
  const userId = useAuthStore((state) => state.user?.id);
  return <MemoryPanel key={userId ?? "anonymous"} userId={userId} />;
}

function MemoryPanel({ userId }: { userId: number | undefined }) {
  const client = useQueryClient();
  const [layer, setLayer] = useState<MemoryLayer>("episode");
  const [page, setPage] = useState(1);
  const [category, setCategory] = useState<MemoryFactInput["category"]>("goal");
  const [content, setContent] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [editing, setEditing] = useState<MemoryItem | null>(null);
  const [editText, setEditText] = useState("");
  const [action, setAction] = useState<Action | null>(null);
  const [notice, setNotice] = useState("");
  const privacy = useQuery({ queryKey: ["settings", "privacy", userId], queryFn: getPrivacySettings });
  const memories = useQuery({ queryKey: ["settings", "memories", userId, layer, page], queryFn: () => listMemories(layer, page) });
  const state = privacy.data?.data;
  const operation = useMutation({
    mutationFn: async ({ work, message }: { work: () => Promise<unknown>; message: string }) => { await work(); return message; },
    onSuccess: async (message) => {
      setNotice(message);
      await Promise.all([
        client.invalidateQueries({ queryKey: ["settings", "memories", userId] }),
        client.invalidateQueries({ queryKey: ["settings", "privacy", userId] })
      ]);
    },
    onError: () => { setNotice(""); }
  });
  const busy = operation.isPending;
  function run(work: () => Promise<unknown>, message: string) { setNotice(""); operation.mutate({ work, message }); }
  async function download() {
    const data = await exportMemories();
    const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json;charset=utf-8" }));
    const anchor = document.createElement("a");
    anchor.href = url; anchor.download = "edunova-memory.json"; anchor.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  function confirmAction() {
    if (!action) return;
    if (action.kind === "delete") run(() => deleteMemory(action.item), "已永久删除这条记忆；旧索引任务不会恢复它，原始聊天仍保留。");
    else if (action.kind === "clear") run(async () => { await clearConversationMemory(); setPage(1); }, "全部记忆已清除，旧来源不会自动恢复；之后的新对话仍按记忆开关处理。");
    else run(clearMemoryIndexes, "派生索引已清除，摘要和长期信息仍保留。需要时可手动重建。");
    setAction(null);
  }

  return <section className="settings-memory" aria-label="记忆管理">
    <h3>记忆管理</h3>
    <p>当前会话保留近期对话；历史经历按相关性找回；长期信息仅保存你明确确认的内容。记忆不作为课程事实、评分或掌握度证据。</p>
    {privacy.isError ? <p role="alert">记忆设置读取失败，请刷新重试。</p> : null}
    <div className="memory-toolbar">
      <label className="memory-toggle"><input type="checkbox" aria-label="跨会话记忆" checked={state?.conversation_memory_enabled ?? false}
        disabled={busy || !state || privacy.isError} onChange={(event) => { const enabled = event.target.checked; run(() => updatePrivacySettings(enabled), enabled ? "已恢复记忆使用。" : "已暂停记忆使用和后台写入，已存记忆保留。"); }} />
        {state?.conversation_memory_enabled ? "使用跨会话记忆" : "已暂停跨会话记忆"}</label>
      <button type="button" className="secondary-action" disabled={busy} onClick={() => run(download, "记忆已导出，不含原始聊天、向量和密钥。")}>导出记忆</button>
      <button type="button" className="secondary-action" disabled={busy || !state} onClick={() => setAction({ kind: "indexes" })}>清除派生索引</button>
      <button type="button" className="secondary-action" disabled={busy || !state?.conversation_memory_enabled} onClick={() => run(rebuildMemoryIndexes, "已提交重建任务；仅处理保留的摘要。稍后刷新查看索引数量。")}>重建派生索引</button>
      <button type="button" className="secondary-action" disabled={busy || !state} onClick={() => setAction({ kind: "clear" })}>清除全部记忆</button>
    </div>
    {state ? <p>历史经历 {state.episode_count ?? 0} 条 · 已建索引 {state.indexed_memory_count} 条 · 长期信息 {state.confirmed_fact_count ?? 0} 条</p> : <p role="status">正在读取记忆设置…</p>}
    {operation.isError ? <p role="alert">{getApiErrorMessage(operation.error, "操作失败，请刷新后重试。")}</p> : null}
    {notice ? <p role="status">{notice}</p> : null}

    <form className="memory-create" onSubmit={(event) => {
      event.preventDefault();
      if (!confirmed || !content.trim() || busy) return;
      run(async () => { await createMemory({ category, content: content.trim(), confirmed: true }); setContent(""); setConfirmed(false); setLayer("fact"); setPage(1); }, "长期信息已保存，来源为你的明确确认。");
    }}>
      <h4>确认一条长期学习信息</h4>
      <label>信息类型<select value={category} onChange={(event) => setCategory(event.target.value as MemoryFactInput["category"])}>{Object.entries(categories).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
      <label>长期学习信息<textarea maxLength={500} required value={content} onChange={(event) => setContent(event.target.value)} placeholder="例如：我希望先看具体例子，再学习抽象定义。" /></label>
      <label className="memory-toggle"><input type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} />我确认这条信息，并希望在后续对话中使用</label>
      <button className="secondary-action" type="submit" disabled={busy || !confirmed || !content.trim()}>保存长期信息</button>
    </form>

    <div className="memory-toolbar"><label>查看记忆层<select value={layer} onChange={(event) => { setLayer(event.target.value as MemoryLayer); setPage(1); setEditing(null); }}>
      <option value="episode">L2 历史经历</option><option value="fact">L3 长期学习信息</option></select></label>
      <button type="button" className="secondary-action" disabled={memories.isFetching || busy} onClick={() => { void memories.refetch(); void privacy.refetch(); }}>刷新记忆</button></div>
    {memories.isPending ? <p role="status">正在读取记忆…</p> : null}
    {memories.isError ? <p role="alert">记忆列表读取失败，请刷新重试。</p> : null}
    {!memories.isError && memories.data?.items.length === 0 ? <p>暂无这一层的记忆。</p> : null}
    <ul className="memory-list">{!memories.isError && memories.data?.items.map((item) => <li key={`${item.layer}-${item.id}`}>
      <h4>{item.layer === "fact" ? categories[item.category as keyof typeof categories] : item.topic}</h4>
      <p className="memory-content">{item.content}</p>
      <small>来源：{item.source}{item.session_id ? ` · 会话 ${item.session_id} · 消息 ${item.user_message_id} / ${item.assistant_message_id}` : ""}</small>
      <small>创建：{new Date(item.created_at).toLocaleString()} · 更新：{new Date(item.updated_at).toLocaleString()}{item.layer === "episode" ? (item.indexed ? " · 已建索引" : " · 待手动重建索引") : ""}</small>
      {editing?.id === item.id && editing.layer === item.layer ? <form onSubmit={(event) => { event.preventDefault(); run(async () => { await correctMemory(editing, editText.trim()); setEditing(null); }, "纠正已保存；历史摘要纠正后需要重建派生索引。"); }}>
        <label>纠正内容<textarea required maxLength={item.layer === "fact" ? 500 : 1600} value={editText} onChange={(event) => setEditText(event.target.value)} /></label>
        <div className="memory-toolbar"><button className="secondary-action" disabled={busy || !editText.trim()} type="submit">确认保存纠正</button><button className="secondary-action" disabled={busy} type="button" onClick={() => setEditing(null)}>取消编辑</button></div>
      </form> : <div className="memory-toolbar">
        <button className="secondary-action" type="button" disabled={busy} onClick={() => { setEditing(item); setEditText(item.content); }}>纠正</button>
        <button className="secondary-action" type="button" disabled={busy} onClick={() => setAction({ kind: "delete", item })}>永久删除</button>
      </div>}
    </li>)}</ul>
    {memories.data ? <nav className="memory-toolbar" aria-label="记忆分页">
      <button className="secondary-action" type="button" disabled={busy || page <= 1} onClick={() => { setPage(page - 1); setEditing(null); }}>上一页</button>
      <span>第 {page} 页 · 共 {memories.data.total} 条</span>
      <button className="secondary-action" type="button" disabled={busy || page * memories.data.page_size >= memories.data.total} onClick={() => { setPage(page + 1); setEditing(null); }}>下一页</button>
    </nav> : null}
    <ConfirmDialog open={action !== null} onOpenChange={(open) => { if (!open) setAction(null); }}
      title={action?.kind === "indexes" ? "清除派生索引？" : action?.kind === "clear" ? "清除全部记忆？" : "永久删除这条记忆？"}
      description={action?.kind === "indexes" ? "保留摘要和长期信息，仅清除向量索引；不会自动重建。" : "删除记忆内容并阻止旧任务恢复。原始聊天记录仍然保留。"}
      confirmLabel="确认操作" onConfirm={confirmAction} />
  </section>;
}

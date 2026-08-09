import { ArrowSquareOut, Database, Key, ShieldCheck } from "@phosphor-icons/react";
import { Link } from "react-router-dom";

import { PATHS } from "../../app/routePaths";
import type { SettingsController } from "./useSettingsController";

type PrivacySettingsSectionProps = Pick<
  SettingsController,
  "clearMemoryMutation" | "privacyMutation" | "privacyQuery"
>;

export function PrivacySettingsSection({
  clearMemoryMutation,
  privacyMutation,
  privacyQuery
}: PrivacySettingsSectionProps) {
  const privacy = privacyQuery.data?.data;

  return (
    <section className="settings-panel settings-privacy-panel" role="region" aria-label="隐私与数据">
      <header className="settings-panel-heading">
        <div><h2>数据隐私</h2></div>
      </header>
      <div className="settings-privacy-list">
        <article>
          <Database size={21} weight="duotone" />
          <div>
            <strong>跨会话记忆</strong>
            <p>只保存当前账号的脱敏摘要与向量索引，用于在新对话中找回相关背景；不会复制原始聊天，也不会作为教材、画像或掌握度证据。</p>
            <small>当前派生记忆：{privacy?.indexed_memory_count ?? 0} 条</small>
          </div>
          <label className="settings-memory-toggle">
            <input
              type="checkbox"
              aria-label="跨会话记忆"
              checked={privacy?.conversation_memory_enabled ?? true}
              disabled={privacyQuery.isLoading || privacyMutation.isPending}
              onChange={(event) => privacyMutation.mutate(event.target.checked)}
            />
            <span>{(privacy?.conversation_memory_enabled ?? true) ? "已开启" : "已关闭"}</span>
          </label>
          <button
            type="button"
            className="secondary-action"
            disabled={clearMemoryMutation.isPending || !(privacy?.indexed_memory_count ?? 0)}
            onClick={() => clearMemoryMutation.mutate()}
          >
            {clearMemoryMutation.isPending ? "清除中" : "清除派生记忆"}
          </button>
        </article>
        <article><Key size={21} weight="duotone" /><div><strong>模型密钥</strong><p>个人 API Key 使用 Fernet 加密保存，页面和接口只返回脱敏摘要。</p></div><span>加密存储</span></article>
        <article><ShieldCheck size={21} weight="duotone" /><div><strong>Agent 协作轨迹</strong><p>只展示节点、耗时、引用数量和安全审核摘要，不保存原始提示词或完整模型输入。</p></div><span>安全摘要</span></article>
        <article><Database size={21} weight="duotone" /><div><strong>学习资料</strong><p>资料、课程和会话按账号隔离；检索只在当前用户明确选择的范围内执行。</p></div><span>用户隔离</span></article>
        <article><ArrowSquareOut size={21} weight="duotone" /><div><strong>学习档案</strong><p>报告页可以按课程导出 Markdown、PDF 或 DOCX，导出任务不会包含密钥和原始模型上下文。</p></div><Link to={PATHS.reports}>前往报告页</Link></article>
      </div>
    </section>
  );
}

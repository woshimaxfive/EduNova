import { CheckCircle, PlugsConnected, WarningCircle } from "@phosphor-icons/react";

import type {
  ModelConnectionOperation,
  ModelConnectionTestSnapshot
} from "../../api/settings";

type ConnectionTestCardProps = {
  operation: ModelConnectionOperation;
  model: string | null;
  result?: ModelConnectionTestSnapshot | null;
  disabled: boolean;
  pending: boolean;
  dirty: boolean;
  onTest: () => void;
};

function formatTestTime(value?: string | null) {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  }).format(date);
}

export function ConnectionTestCard({
  operation,
  model,
  result,
  disabled,
  pending,
  dirty,
  onTest
}: ConnectionTestCardProps) {
  const isEmbedding = operation === "embedding";
  const label = isEmbedding ? "向量模型" : "回答模型";
  const testedAt = formatTestTime(result?.tested_at);
  const status = !model
    ? "not-configured"
    : result?.ok === true
      ? "success"
      : result?.ok === false
        ? "failed"
        : "untested";

  return (
    <article className={`settings-connection-test ${status}`} aria-label={`${label}连接状态`}>
      <header>
        <span className="settings-connection-icon" aria-hidden="true">
          {status === "success"
            ? <CheckCircle size={20} weight="fill" />
            : status === "failed"
              ? <WarningCircle size={20} weight="fill" />
              : <PlugsConnected size={20} weight="duotone" />}
        </span>
        <div>
          <strong>{label}</strong>
          <span>{model || "未配置"}</span>
        </div>
      </header>
      <p>
        {!model
          ? isEmbedding ? "此配置未设置向量模型，运行时将使用服务器配置或关键词 fallback。" : "请先填写并保存回答模型。"
          : dirty
            ? "配置已有修改，保存后才能测试当前值。"
            : result?.message || "尚未执行连接测试。"}
      </p>
      <footer>
        <span>{testedAt ? `最近测试 ${testedAt}` : "暂无测试记录"}</span>
        <button type="button" onClick={onTest} disabled={disabled || !model || pending}>
          <PlugsConnected size={15} weight="bold" aria-hidden="true" />
          {pending ? "测试中" : `测试${label}`}
        </button>
      </footer>
    </article>
  );
}

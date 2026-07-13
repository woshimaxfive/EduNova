import { CheckCircle, PlugsConnected, WarningCircle } from "@phosphor-icons/react";

import type {
  ModelConnectionOperation,
  ModelConnectionTestSnapshot
} from "../../api/settings";

type ConnectionTestCardProps = {
  operation: ModelConnectionOperation;
  model: string | null;
  missingMessage?: string;
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
  missingMessage,
  result,
  disabled,
  pending,
  dirty,
  onTest
}: ConnectionTestCardProps) {
  const isEmbedding = operation === "embedding";
  const isRerank = operation === "rerank";
  const label = isEmbedding ? "向量服务" : isRerank ? "重排序服务" : "回答服务";
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
      <span className="settings-connection-icon" aria-hidden="true">
        {status === "success"
          ? <CheckCircle size={20} weight="fill" />
          : status === "failed"
            ? <WarningCircle size={20} weight="fill" />
            : <PlugsConnected size={20} weight="duotone" />}
      </span>
      <div className="settings-connection-name">
        <strong>{label}</strong>
        <span>{model ? `${model}${isEmbedding && result?.dimension ? ` · ${result.dimension} 维` : ""}` : "未配置"}</span>
      </div>
      <p>
        {!model
          ? missingMessage ?? (isEmbedding ? "此配置未设置向量模型。" : isRerank ? "此配置未设置重排序模型。" : "此配置未设置回答模型。")
          : dirty
            ? "保存修改后可验证当前连接。"
            : result?.message || "尚未验证连接。"}
      </p>
      <footer>
        <span>{testedAt ? `最近验证 ${testedAt}` : "暂无验证记录"}</span>
        <button
          type="button"
          aria-label={`验证${label}连接`}
          onClick={onTest}
          disabled={disabled || !model || pending}
        >
          <PlugsConnected size={15} weight="bold" aria-hidden="true" />
          {pending ? "验证中" : "验证连接"}
        </button>
      </footer>
    </article>
  );
}

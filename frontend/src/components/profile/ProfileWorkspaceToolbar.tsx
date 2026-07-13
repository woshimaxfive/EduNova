import { ChatCircleDots, ClockCounterClockwise, TrendUp } from "@phosphor-icons/react";

type ProfileWorkspaceToolbarProps = {
  confidence: number;
  version: number;
  appliedCount: number;
  candidateCount: number;
  updatedAt: string | null;
  onFocusComposer: () => void;
};

function formatUpdatedAt(value: string | null) {
  if (!value) return "等待首次更新";
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  }).format(new Date(value));
}

export function ProfileWorkspaceToolbar({
  confidence,
  version,
  appliedCount,
  candidateCount,
  updatedAt,
  onFocusComposer
}: ProfileWorkspaceToolbarProps) {
  return (
    <header className="profile-workspace-toolbar">
      <div className="profile-toolbar-identity">
        <TrendUp size={20} weight="duotone" aria-hidden="true" />
        <span>
          <h2>动态学习画像</h2>
          <small>综合可信度 <strong>{Math.round(confidence)}%</strong></small>
        </span>
      </div>
      <dl className="profile-toolbar-facts">
        <div><dt>画像版本</dt><dd>v{version}</dd></div>
        <div><dt>已应用证据</dt><dd>{appliedCount}</dd></div>
        <div><dt>候选证据</dt><dd>{candidateCount}</dd></div>
        <div><dt><ClockCounterClockwise size={14} aria-hidden="true" />最近更新</dt><dd>{formatUpdatedAt(updatedAt)}</dd></div>
      </dl>
      <button className="profile-toolbar-primary" type="button" onClick={onFocusComposer}>
        <ChatCircleDots size={18} weight="bold" aria-hidden="true" />
        完善画像
      </button>
    </header>
  );
}

import { ChartLineUp, GearSix } from "@phosphor-icons/react";

import { type PracticeSessionDetail } from "../../api/practice";
import { difficultyLabel } from "../../features/practice/practiceViewModel";

type PracticeToolbarProps = {
  courseTitle: string;
  pointTitle: string;
  session: PracticeSessionDetail | null;
  activeIndex: number;
  answeredCount: number;
  draftLabel: string | null;
  onOpenSettings: () => void;
  onOpenResults: () => void;
};

export function PracticeToolbar({
  courseTitle,
  pointTitle,
  session,
  activeIndex,
  answeredCount,
  draftLabel,
  onOpenSettings,
  onOpenResults
}: PracticeToolbarProps) {
  const total = session?.questions.length ?? 0;
  const completed = session?.status === "completed";

  return (
    <header className="practice-workspace-toolbar">
      <div className="practice-toolbar-context">
        <span>针对性练习 · {courseTitle || "选择课程"}</span>
        <strong>{pointTitle || "选择知识点开始练习"}</strong>
      </div>
      <div className="practice-toolbar-metrics" aria-label="练习进度">
        <span>{session ? difficultyLabel(session.effective_difficulty) : "智能适配"}</span>
        <strong>
          {completed
            ? `得分 ${session?.score ?? 0}`
            : total > 0
              ? `${Math.min(activeIndex + 1, total)} / ${total} · 已答 ${answeredCount}`
              : "尚未开始"}
        </strong>
        {draftLabel ? <small role="status">{draftLabel}</small> : null}
      </div>
      <div className="practice-toolbar-actions">
        {completed ? (
          <button type="button" onClick={onOpenResults}>
            <ChartLineUp size={17} weight="duotone" aria-hidden="true" />
            学习结果
          </button>
        ) : null}
        <button type="button" onClick={onOpenSettings}>
          <GearSix size={17} weight="duotone" aria-hidden="true" />
          练习设置
        </button>
      </div>
    </header>
  );
}

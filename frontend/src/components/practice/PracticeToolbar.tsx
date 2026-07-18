import * as Popover from "@radix-ui/react-popover";
import { ChartLineUp, GearSix, Info } from "@phosphor-icons/react";
import type { ReactNode } from "react";

import { type PracticeSessionDetail } from "../../api/practice";
import { difficultyLabel } from "../../features/practice/practiceViewModel";

type PracticeToolbarProps = {
  courseTitle: string;
  pointTitle: string;
  session: PracticeSessionDetail | null;
  activeIndex: number;
  answeredCount: number;
  draftLabel: string | null;
  returnLink?: ReactNode;
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
  returnLink,
  onOpenSettings,
  onOpenResults
}: PracticeToolbarProps) {
  const total = session?.questions.length ?? 0;
  const completed = session?.status === "completed";
  const adaptive = !session || session.requested_difficulty === "adaptive";

  return (
    <header className="practice-workspace-toolbar">
      <div className="practice-toolbar-identity">
        {returnLink ? <div className="course-toolbar-return">{returnLink}</div> : null}
        <div className="practice-toolbar-context">
          <span>针对性练习 · {courseTitle || "选择课程"}</span>
          <strong>{pointTitle || "选择知识点开始练习"}</strong>
        </div>
      </div>
      <div className="practice-toolbar-metrics" aria-label="练习进度">
        {adaptive ? (
          <Popover.Root>
            <Popover.Trigger asChild>
              <button className="practice-adaptive-trigger" type="button" aria-label="了解智能适配依据">
                智能适配
                <Info size={14} weight="duotone" aria-hidden="true" />
              </button>
            </Popover.Trigger>
            <Popover.Portal>
              <Popover.Content className="practice-adaptive-popover" sideOffset={8} collisionPadding={12}>
                <strong>难度如何确定</strong>
                <p>根据当前掌握度、已确认薄弱点和最近练习结果调整。</p>
                <Popover.Arrow className="practice-adaptive-popover-arrow" />
              </Popover.Content>
            </Popover.Portal>
          </Popover.Root>
        ) : <span>{difficultyLabel(session.effective_difficulty)}</span>}
        <strong>
          {completed
            ? session?.score === null
              ? "暂未评分"
              : `得分 ${session.score}`
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
      {total > 0 && !completed ? (
        <progress
          className="practice-answer-progress"
          max={total}
          value={answeredCount}
          aria-label={`已回答 ${answeredCount} 题，共 ${total} 题`}
        >
          {answeredCount}/{total}
        </progress>
      ) : null}
    </header>
  );
}

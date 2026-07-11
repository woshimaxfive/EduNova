import { ArrowLeft, BookOpenText, ChartDonut, ChatCircleText } from "@phosphor-icons/react";
import { Link } from "react-router-dom";

import { PATHS } from "../../app/routePaths";

export type CourseWorkspaceMode = "chat" | "study";

type CourseWorkspaceHeaderProps = {
  title: string;
  progressPercent: number;
  materialCount: number;
  knowledgePointCount: number;
  weaknessCount: number;
  mode: CourseWorkspaceMode;
  onModeChange: (mode: CourseWorkspaceMode) => void;
  onOpenProgress: () => void;
};

export function CourseWorkspaceHeader({
  title,
  progressPercent,
  materialCount,
  knowledgePointCount,
  weaknessCount,
  mode,
  onModeChange,
  onOpenProgress
}: CourseWorkspaceHeaderProps) {
  return (
    <header className="course-workspace-header" aria-label="课程工作区标题栏">
      <div className="course-workspace-header-main">
        <Link className="course-workspace-back" to={PATHS.app} aria-label="回到学习主页">
          <ArrowLeft size={18} weight="bold" aria-hidden="true" />
        </Link>
        <div className="course-workspace-title">
          <h1>{title}</h1>
          <span aria-label="课程状态">{materialCount} 份资料 · {knowledgePointCount} 个知识点 · 掌握度 {progressPercent}%</span>
        </div>
      </div>

      <div className="course-workspace-controls">
        <div className="course-mode-control" aria-label="课程空间模式">
          <button
            className={mode === "chat" ? "active" : ""}
            type="button"
            aria-pressed={mode === "chat"}
            onClick={() => onModeChange("chat")}
          >
            <ChatCircleText size={17} weight="duotone" aria-hidden="true" />
            <span>问答</span>
          </button>
          <button
            className={mode === "study" ? "active" : ""}
            type="button"
            aria-pressed={mode === "study"}
            onClick={() => onModeChange("study")}
          >
            <BookOpenText size={17} weight="duotone" aria-hidden="true" />
            <span>课程内容</span>
          </button>
        </div>
        <button className="course-progress-trigger" type="button" onClick={onOpenProgress}>
          <ChartDonut size={18} weight="duotone" aria-hidden="true" />
          <span>学习进度</span>
          <em>{weaknessCount > 0 ? weaknessCount : `${progressPercent}%`}</em>
        </button>
      </div>
    </header>
  );
}

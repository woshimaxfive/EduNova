import { DownloadSimple, FileText, Info } from "@phosphor-icons/react";
import type { ReactNode } from "react";

import type { ApiCourseSummary } from "../../api/courses";
import type { ReportFreshness } from "../../features/reports/reportViewModel";

type ReportWorkspaceToolbarProps = {
  courses: ApiCourseSummary[];
  courseId: string;
  freshness: ReportFreshness;
  createdAt: string | null | undefined;
  isGenerating: boolean;
  isRefreshing: boolean;
  returnLink: ReactNode;
  onCourseChange: (courseId: string) => void;
  courseLocked?: boolean;
  onGenerate: () => void;
  onRetryRead: () => void;
  onOpenDetails: () => void;
  onOpenExport: () => void;
};

function formatDateTime(value: string | null | undefined) {
  if (!value) return "尚未生成";
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  }).format(new Date(value));
}

export function ReportWorkspaceToolbar({
  courses,
  courseId,
  freshness,
  createdAt,
  isGenerating,
  isRefreshing,
  returnLink,
  onCourseChange,
  courseLocked = false,
  onGenerate,
  onRetryRead,
  onOpenDetails,
  onOpenExport
}: ReportWorkspaceToolbarProps) {
  const statusLabel = freshness === "empty"
    ? "等待学习证据"
    : freshness === "stale"
      ? "建议更新"
      : freshness === "unavailable"
        ? "报告暂不可用"
        : freshness === "unknown"
          ? "状态待确认"
          : "报告已同步";
  const generateLabel = freshness === "stale" ? "更新报告" : freshness === "empty" ? "生成报告" : "重新生成";
  const statusDetail = freshness === "stale"
    ? "已有新的练习结果"
    : freshness === "unavailable"
      ? "未能读取报告快照"
      : freshness === "unknown"
        ? `快照 ${formatDateTime(createdAt)} · 练习状态未同步`
        : `快照 ${formatDateTime(createdAt)}`;

  return (
    <header className="report-workspace-toolbar">
      <div className="report-toolbar-identity">
        {returnLink ? <div className="course-toolbar-return">{returnLink}</div> : null}
        {courseLocked ? (
          <div className="report-course-select" aria-label={`学习报告，当前课程 ${courses.find((course) => course.id === courseId)?.title ?? "未选择课程"}`}>
            <span>学习报告 · 当前课程</span>
            <strong>{courses.find((course) => course.id === courseId)?.title ?? "未选择课程"}</strong>
          </div>
        ) : (
          <label className="report-course-select">
            <span>学习报告 · 当前课程</span>
            <select aria-label="选择课程" value={courseId} onChange={(event) => onCourseChange(event.target.value)}>
              {courses.map((course) => <option key={course.id} value={course.id}>{course.title}{course.learning_status === "archived" ? "（已完成）" : course.is_current ? "（当前学习）" : ""}</option>)}
            </select>
          </label>
        )}
      </div>

      <div className="report-toolbar-status" aria-live="polite">
        <span data-status={freshness}>{statusLabel}</span>
        <strong>{statusDetail}</strong>
      </div>

      <div className="report-toolbar-actions">
        <button type="button" onClick={onOpenDetails}>
          <Info size={17} weight="bold" aria-hidden="true" />
          <span>报告详情</span>
        </button>
        <button type="button" aria-label="导出学习档案" onClick={onOpenExport}>
          <DownloadSimple size={17} weight="bold" aria-hidden="true" />
          <span>导出档案</span>
        </button>
        <button className="primary" type="button" disabled={!courseId || isGenerating || isRefreshing} onClick={freshness === "unavailable" ? onRetryRead : onGenerate}>
          <FileText size={17} weight="bold" aria-hidden="true" />
          <span>{isRefreshing ? "正在重新读取" : isGenerating ? "正在生成" : freshness === "unavailable" ? "重新读取报告" : generateLabel === "生成报告" ? "生成学习报告" : generateLabel === "重新生成" ? "重新生成学习报告" : "更新学习报告"}</span>
        </button>
      </div>
    </header>
  );
}

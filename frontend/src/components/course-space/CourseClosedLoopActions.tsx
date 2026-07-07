import { ArrowSquareOut, FileText, Graph, ListChecks, Sparkle, Target } from "@phosphor-icons/react";
import { Link } from "react-router-dom";

import { PATHS } from "../../app/routePaths";

type CourseClosedLoopActionsProps = {
  courseId: number;
  citationCount: number;
  resourceCount: number;
  hasActivePath: boolean;
  hasTrace: boolean;
  onOpenCitations: () => void;
  onOpenResources: () => void;
  onOpenPath: () => void;
  onOpenTrace: () => void;
};

export function CourseClosedLoopActions({
  courseId,
  citationCount,
  resourceCount,
  hasActivePath,
  hasTrace,
  onOpenCitations,
  onOpenResources,
  onOpenPath,
  onOpenTrace
}: CourseClosedLoopActionsProps) {
  return (
    <section className="course-closed-loop-actions" aria-label="课程闭环行动">
      <button type="button" aria-label="来源" onClick={onOpenCitations}>
        <FileText size={17} weight="duotone" aria-hidden="true" />
        <span>来源</span>
        <em>{citationCount} 条</em>
      </button>
      <button type="button" aria-label="生成资源" onClick={onOpenResources}>
        <Sparkle size={17} weight="duotone" aria-hidden="true" />
        <span>生成资源</span>
        <em>{resourceCount} 个</em>
      </button>
      <button type="button" aria-label="学习路径" onClick={onOpenPath}>
        <Target size={17} weight="duotone" aria-hidden="true" />
        <span>学习路径</span>
        <em>{hasActivePath ? "已生成" : "可生成"}</em>
      </button>
      <Link to={`${PATHS.practice}?course_id=${courseId}`}>
        <ListChecks size={17} weight="duotone" aria-hidden="true" />
        <span>进入练习</span>
        <ArrowSquareOut size={15} weight="bold" aria-hidden="true" />
      </Link>
      <Link to={`${PATHS.reports}?course_id=${courseId}`}>
        <FileText size={17} weight="duotone" aria-hidden="true" />
        <span>学习报告</span>
        <ArrowSquareOut size={15} weight="bold" aria-hidden="true" />
      </Link>
      <button type="button" aria-label="课堂协作轨迹" onClick={onOpenTrace}>
        <Graph size={17} weight="duotone" aria-hidden="true" />
        <span>课堂协作轨迹</span>
        <em>{hasTrace ? "真实 trace" : "暂无"}</em>
      </button>
    </section>
  );
}

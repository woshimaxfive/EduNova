import { ArrowSquareOut, FileText, Graph, ListChecks, SpeakerHigh, SpeakerSlash, Sparkle, Target } from "@phosphor-icons/react";
import { Link } from "react-router-dom";

import { PATHS } from "../../app/routePaths";

export type CourseAnswerPanelKind = "citations" | "resources" | "path" | "thinking";

type CourseClosedLoopActionsProps = {
  courseId: number;
  citationCount: number;
  resourceCount: number;
  hasActivePath: boolean;
  hasTrace: boolean;
  activePanel: CourseAnswerPanelKind | null;
  isSpeaking: boolean;
  onRead: () => void;
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
  activePanel,
  isSpeaking,
  onRead,
  onOpenCitations,
  onOpenResources,
  onOpenPath,
  onOpenTrace
}: CourseClosedLoopActionsProps) {
  return (
    <section className="course-closed-loop-actions" aria-label="课程闭环行动">
      <button type="button" aria-label={isSpeaking ? "停止朗读" : "朗读"} aria-pressed={isSpeaking} onClick={onRead}>
        {isSpeaking ? <SpeakerSlash size={17} weight="duotone" aria-hidden="true" /> : <SpeakerHigh size={17} weight="duotone" aria-hidden="true" />}
        <span>{isSpeaking ? "停止" : "朗读"}</span>
      </button>
      <button type="button" aria-label="来源" aria-pressed={activePanel === "citations"} onClick={onOpenCitations}>
        <FileText size={17} weight="duotone" aria-hidden="true" />
        <span>来源</span>
        <em>{citationCount} 条</em>
      </button>
      <button type="button" aria-label="生成资源" aria-pressed={activePanel === "resources"} onClick={onOpenResources}>
        <Sparkle size={17} weight="duotone" aria-hidden="true" />
        <span>生成资源</span>
        <em>{resourceCount} 个</em>
      </button>
      <button type="button" aria-label="学习路径" aria-pressed={activePanel === "path"} onClick={onOpenPath}>
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
      <button type="button" aria-label="课堂协作轨迹" aria-pressed={activePanel === "thinking"} onClick={onOpenTrace}>
        <Graph size={17} weight="duotone" aria-hidden="true" />
        <span>课堂协作轨迹</span>
        <em>{hasTrace ? "真实 trace" : "暂无"}</em>
      </button>
    </section>
  );
}

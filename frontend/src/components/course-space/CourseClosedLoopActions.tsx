import {
  FileText,
  Lightning,
  ListChecks,
  MapTrifold,
  SpeakerHigh,
  SpeakerSlash,
  Sparkle,
} from "@phosphor-icons/react";
import { Link } from "react-router-dom";

import { type LearningNextAction } from "../../api/learning";

export type CourseAnswerPanelKind = "citations" | "resources" | "path" | "why" | "thinking";

type CourseClosedLoopActionsProps = {
  recommendation: LearningNextAction | null;
  citationCount: number;
  resourceCount: number;
  activePanel: CourseAnswerPanelKind | null;
  isSpeaking: boolean;
  pathHref: string;
  practiceHref: string;
  reportHref: string;
  onRecommendedAction: () => void;
  onRead: () => void;
  onOpenCitations: () => void;
  onOpenResources: () => void;
  onOpenWhy: () => void;
};

export function CourseClosedLoopActions({
  recommendation,
  citationCount,
  resourceCount,
  activePanel,
  isSpeaking,
  pathHref,
  practiceHref,
  reportHref,
  onRecommendedAction,
  onRead,
  onOpenCitations,
  onOpenResources,
  onOpenWhy
}: CourseClosedLoopActionsProps) {
  return (
    <section className="course-closed-loop-actions" aria-label="课程闭环行动">
      {recommendation ? (
        <button className="course-recommended-action" type="button" title={recommendation.description} onClick={onRecommendedAction}>
          <Lightning size={17} weight="fill" aria-hidden="true" />
          <span>{recommendation.label}</span>
        </button>
      ) : null}
      <div className="course-secondary-actions">
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
        <Link to={pathHref}>
          <MapTrifold size={17} weight="duotone" aria-hidden="true" />
          <span>学习路径</span>
        </Link>
        <Link to={practiceHref}>
          <ListChecks size={17} weight="duotone" aria-hidden="true" />
          <span>进入练习</span>
        </Link>
        <Link to={reportHref}>
          <FileText size={17} weight="duotone" aria-hidden="true" />
          <span>学习报告</span>
        </Link>
        <button type="button" aria-label="为什么这样回答" aria-pressed={activePanel === "why"} onClick={onOpenWhy}>
          <Sparkle size={17} weight="duotone" aria-hidden="true" />
          <span>为什么这样回答</span>
        </button>
      </div>
    </section>
  );
}

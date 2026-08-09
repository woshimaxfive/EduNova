import { Link } from "react-router-dom";

import { PATHS } from "../../app/routePaths";
import { type CoursePathSummary } from "../../api/courses";
import { type RagSearchResultItem } from "../../api/rag";
import { type TutorCitation } from "../../api/tutor";
import { type AgentTraceEvent } from "../../types/api";
import { AgentTimeline } from "../evidence/AgentTimeline";
import { InlineFeedback } from "../feedback/InlineFeedback";
import { type CourseAnswerPanelKind } from "./CourseClosedLoopActions";

type AgentTraceSummary = {
  duration_ms?: number;
  personalization_factors?: string[];
  course_source_count?: number;
  web_source_count?: number;
  history_source_count?: number;
};

type CourseAnswerDetailPanelProps = {
  activePanel: CourseAnswerPanelKind;
  courseId: number | null;
  citations: RagSearchResultItem[];
  supplementalSources: TutorCitation[];
  hasRealCourse: boolean;
  hasSearched: boolean;
  pathSummary: CoursePathSummary | null;
  pathHref: string;
  agentTraceId: string | null;
  agentTraceEvents: AgentTraceEvent[];
  agentTraceSummary: AgentTraceSummary | null;
  isAgentTraceLoading: boolean;
  isAgentTraceError: boolean;
  onOpenCitation: (citation: RagSearchResultItem) => void;
};

function retrievalSourceLabel(source?: string | null) {
  if (source === "hybrid") return "混合检索";
  if (source === "vector") return "向量检索";
  return "关键词检索";
}

function embeddingStatusLabel(status?: string | null) {
  if (status === "local_fallback") return "基础关键词检索";
  if (status === "completed") return "真实向量";
  return "关键词检索";
}

function supplementalSourceLabel(citation: TutorCitation) {
  if (citation.source_type === "history") return "历史对话，仅用于上下文";
  if (citation.access_scope === "external_fallback") return "境外补充，不作为课程证据";
  if (citation.access_scope === "mainland_preferred") return "国内优先来源，不作为课程证据";
  return "外部补充，不作为课程证据";
}

export function CourseAnswerDetailPanel({
  activePanel,
  courseId,
  citations,
  supplementalSources,
  hasRealCourse,
  hasSearched,
  pathSummary,
  pathHref,
  agentTraceId,
  agentTraceEvents,
  agentTraceSummary,
  isAgentTraceLoading,
  isAgentTraceError,
  onOpenCitation
}: CourseAnswerDetailPanelProps) {
  if (activePanel === "why") {
    const factorCount = agentTraceSummary?.personalization_factors?.length ?? 0;
    return (
      <section className="answer-detail-panel" role="region" aria-label="为什么这样回答">
        <strong>为什么这样回答</strong>
        <p>
          {factorCount > 0
            ? `系统使用 ${factorCount} 项可信学习因素调整讲解深度、案例和下一步，同时保持课程事实、引用和评分边界不变。`
            : "系统主要依据当前问题、会话上下文和课程证据组织回答，没有让候选或低可信画像改变事实。"}
        </p>
      </section>
    );
  }

  if (activePanel === "resources") {
    const studioHref = courseId !== null ? `${PATHS.studio}?course_id=${courseId}` : PATHS.studio;
    return (
      <section className="answer-detail-panel" role="region" aria-label="回答展开详情">
        <strong>生成资源</strong>
        <p>资源工坊会基于当前课程和知识点生成讲解、练习、思维导图、代码实操、PPT 和动画图解。</p>
        <Link to={studioHref}>进入资源工坊</Link>
      </section>
    );
  }

  if (activePanel === "path") {
    return (
      <section className="answer-detail-panel" role="region" aria-label="回答展开详情">
        <strong>学习路径</strong>
        <p>{pathSummary?.message ?? "学习路径尚未生成。"}</p>
        {pathSummary?.current_task_title ? (
          <div className="answer-detail-meta">
            <span>当前任务</span>
            <em>{pathSummary.current_task_title}</em>
          </div>
        ) : null}
        {pathSummary ? <small>{pathSummary.completed_task_count}/{pathSummary.task_count} 已完成</small> : null}
        <Link to={pathHref}>查看完整路径</Link>
      </section>
    );
  }

  if (activePanel === "thinking") {
    if (isAgentTraceError) {
      return (
        <section className="answer-detail-panel" role="region" aria-label="回答展开详情">
          <strong>课堂协作轨迹</strong>
          <InlineFeedback message="Agent 轨迹读取失败，请稍后重试。" tone="warning" className="course-inline-feedback" />
        </section>
      );
    }

    if (isAgentTraceLoading) {
      return (
        <section className="answer-detail-panel" role="region" aria-label="回答展开详情">
          <strong>课堂协作轨迹</strong>
          <p>正在读取课堂协作轨迹。</p>
        </section>
      );
    }

    if (agentTraceId && agentTraceEvents.length > 0) {
      return (
        <section className="answer-detail-panel" role="region" aria-label="回答展开详情">
          <strong>课堂协作轨迹</strong>
          <AgentTimeline events={agentTraceEvents} summary={agentTraceSummary ?? undefined} />
        </section>
      );
    }

    const emptyTraceMessage = agentTraceId
      ? "当前 Agent trace 暂无可展示步骤。"
      : hasSearched
        ? `Profile、Retriever、Tutor、Weakness、Review、NextAction 已围绕本次回答协作，命中 ${citations.length} 条引用。`
        : "发送课程问题后，会按 Profile、Retriever、Tutor、Weakness、Review、NextAction 记录课堂协作轨迹。";

    return (
      <section className="answer-detail-panel" role="region" aria-label="回答展开详情">
        <strong>课堂协作轨迹</strong>
        <p>{emptyTraceMessage}</p>
      </section>
    );
  }

  if (!hasRealCourse) {
    return (
      <section className="answer-detail-panel" role="region" aria-label="回答展开详情">
        <strong>来源</strong>
        <p>请从课程列表进入真实课程后再查看引用来源。</p>
      </section>
    );
  }

  if (!hasSearched) {
    return (
      <section className="answer-detail-panel" role="region" aria-label="回答展开详情">
        <strong>来源</strong>
        <p>发送课程问题后，会先从本课程知识切片中检索真实引用。</p>
      </section>
    );
  }

  if (citations.length === 0 && supplementalSources.length === 0) {
    return (
      <section className="answer-detail-panel" role="region" aria-label="回答展开详情">
        <strong>来源</strong>
        <p>当前课程资料里没有找到足够依据。</p>
      </section>
    );
  }

  return (
    <section className="answer-detail-panel" role="region" aria-label="回答展开详情">
      <strong>来源</strong>
      <div className="citation-list">
        {citations.map((citation) => (
          <button
            key={citation.chunk_id}
            className="citation-item citation-item-button"
            type="button"
            onClick={() => onOpenCitation(citation)}
          >
            <strong>{citation.source_title}</strong>
            <span>{citation.section_title ?? "课程切片"}</span>
            <small className="citation-meta">
              {citation.page_number ? <span>教材第 {citation.page_number} 页</span> : null}
              <span>匹配度 {citation.score.toFixed(1)}</span>
              <span>{retrievalSourceLabel(citation.retrieval_source)}</span>
              <span>{embeddingStatusLabel(citation.embedding_status)}</span>
            </small>
            <span className="citation-content">{citation.content}</span>
          </button>
        ))}
        {supplementalSources.map((citation, index) => (
          <article className="citation-item" key={`${citation.source_type ?? "source"}-${citation.url ?? citation.title ?? index}`}>
            <strong>{citation.title ?? (citation.source_type === "history" ? "历史对话" : "外部补充")}</strong>
            <span>{supplementalSourceLabel(citation)}</span>
            <span className="citation-content">{citation.snippet ?? citation.content ?? "来源已记录"}</span>
            {citation.url ? <a href={citation.url} target="_blank" rel="noreferrer">打开来源</a> : null}
          </article>
        ))}
      </div>
    </section>
  );
}

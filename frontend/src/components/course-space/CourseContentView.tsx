import { BookOpenText, Graph, List } from "@phosphor-icons/react";
import { type KeyboardEvent, useCallback, useEffect, useMemo, useRef } from "react";
import { Link } from "react-router-dom";

import { type ApiCourseKnowledgePoint, type CourseKnowledgePointContent, type CourseMasteryPoint, type CourseWeaknessReviewItem } from "../../api/courses";
import type { LearningNextAction } from "../../api/learning";
import type { GraphScope } from "../../features/course-space/courseWorkspaceState";
import { type RagSearchResultItem } from "../../api/rag";
import { PATHS } from "../../app/routePaths";
import { CourseKnowledgeGraph } from "./CourseKnowledgeGraph";
import { InlineFeedback } from "../feedback/InlineFeedback";
import { CourseMentorDock } from "./CourseMentorDock";

export type CourseContentMode = "overview" | "graph";

type CourseContentMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
};

type CourseContentViewProps = {
  courseId: number;
  courseTitle: string;
  courseSessionId: string | null;
  points: ApiCourseKnowledgePoint[];
  masteryPoints: CourseMasteryPoint[];
  selectedPoint: ApiCourseKnowledgePoint | null;
  content: CourseKnowledgePointContent | null;
  contentPending: boolean;
  contentError: boolean;
  selectedCitation: RagSearchResultItem | null;
  guided: boolean;
  view: CourseContentMode;
  graphScope: GraphScope;
  graphChapter: string;
  graphDetailOpen: boolean;
  weaknesses: CourseWeaknessReviewItem[];
  recommendation: LearningNextAction | null;
  currentTaskPointId: string | null;
  assistantOpen: boolean;
  messages: CourseContentMessage[];
  prompt: string;
  isSending: boolean;
  feedback: string | null;
  isListening: boolean;
  isTranscribing: boolean;
  isSpeaking: boolean;
  isSpeechPaused: boolean;
  onViewChange: (view: CourseContentMode) => void;
  onGraphScopeChange: (scope: GraphScope) => void;
  onGraphChapterChange: (chapter: string) => void;
  onGraphDetailClose: () => void;
  onSelectPoint: (pointId: string, view?: CourseContentMode) => void;
  onSelectPrevious: () => void;
  onSelectNext: () => void;
  onAssistantOpenChange: (open: boolean) => void;
  onPromptChange: (value: string) => void;
  onPromptKeyDown: (event: KeyboardEvent<HTMLTextAreaElement>) => void;
  onSend: () => void;
  onToggleListening: () => void;
  onReadLatest: () => void;
  onPauseOrResumeSpeaking: () => void;
  onStopSpeaking: () => void;
};

export function CourseContentView({
  courseId,
  courseTitle,
  courseSessionId,
  points,
  masteryPoints,
  selectedPoint,
  content,
  contentPending,
  contentError,
  selectedCitation,
  guided,
  view,
  graphScope,
  graphChapter,
  graphDetailOpen,
  weaknesses,
  recommendation,
  currentTaskPointId,
  assistantOpen,
  messages,
  prompt,
  isSending,
  feedback,
  isListening,
  isTranscribing,
  isSpeaking,
  isSpeechPaused,
  onViewChange,
  onGraphScopeChange,
  onGraphChapterChange,
  onGraphDetailClose,
  onSelectPoint,
  onSelectPrevious,
  onSelectNext,
  onAssistantOpenChange,
  onPromptChange,
  onPromptKeyDown,
  onSend,
  onToggleListening,
  onReadLatest,
  onPauseOrResumeSpeaking,
  onStopSpeaking
}: CourseContentViewProps) {
  const workspaceRef = useRef<HTMLElement>(null);
  const chapters = useMemo(() => groupByChapter(points), [points]);
  const contentSections = content?.sections ?? [];
  const relatedResources = content?.related_resources ?? [];
  const scrollWorkspaceToTop = useCallback(() => {
    const scrollContainer = workspaceRef.current?.closest<HTMLElement>(".course-route-surface");
    if (!scrollContainer) return;
    scrollContainer.scrollTop = 0;
  }, []);

  useEffect(() => {
    scrollWorkspaceToTop();
  }, [scrollWorkspaceToTop, selectedPoint?.id, view]);

  return (
    <section ref={workspaceRef} className="course-content-workspace" role="region" aria-label="课程内容模式">
      <aside className="course-content-outline" aria-label="课程目录">
        <div className="course-content-outline-heading">
          <List size={18} weight="duotone" aria-hidden="true" />
          <div>
            <strong>课程目录</strong>
            <span>{points.length} 个知识点</span>
          </div>
        </div>
        <nav>
          {chapters.map((chapter) => (
            <section key={chapter.title}>
              <h2>{chapter.title}</h2>
              {chapter.points.map((point) => (
                <button
                  className={selectedPoint?.id === point.id && !selectedCitation ? "active" : ""}
                  type="button"
                  aria-pressed={selectedPoint?.id === point.id && !selectedCitation}
                  key={point.id}
                  onClick={() => {
                    scrollWorkspaceToTop();
                    onSelectPoint(point.id);
                  }}
                >
                  <span>{point.title}</span>
                  <small>{point.difficulty ?? "未标注"}</small>
                </button>
              ))}
            </section>
          ))}
        </nav>
      </aside>

      <main className="course-content-main">
        <div className="course-content-toolbar">
          <div className="course-content-view-control" aria-label="课程内容视图">
            <button className={view === "overview" ? "active" : ""} type="button" aria-pressed={view === "overview"} onClick={() => onViewChange("overview")}>
              <BookOpenText size={17} weight="duotone" aria-hidden="true" />
              <span>知识点概览</span>
            </button>
            <button className={view === "graph" ? "active" : ""} type="button" aria-pressed={view === "graph"} onClick={() => onViewChange("graph")}>
              <Graph size={17} weight="duotone" aria-hidden="true" />
              <span>知识图谱</span>
            </button>
          </div>
        </div>

        {view === "graph" ? (
          <div className="course-content-graph-view">
            <CourseKnowledgeGraph
              courseId={courseId}
              points={masteryPoints}
              selectedId={selectedPoint?.id}
              scope={graphScope}
              chapter={graphChapter}
              detailOpen={graphDetailOpen}
              weaknesses={weaknesses}
              recommendation={recommendation}
              currentTaskPointId={currentTaskPointId}
              onSelect={(pointId) => onSelectPoint(pointId, "graph")}
              onScopeChange={onGraphScopeChange}
              onChapterChange={onGraphChapterChange}
              onDetailClose={onGraphDetailClose}
              onContinue={(pointId) => onSelectPoint(pointId, "overview")}
              resourceHref={(pointId) => studioKnowledgePointHref(courseId, pointId, assistantOpen, courseSessionId)}
            />
          </div>
        ) : (
          <article className="course-content-reader" aria-label="学习内容">
            {selectedPoint ? (
              <>
                {guided ? (
                  <section className="guided-learning-task" aria-label="本次学习任务">
                    <div>
                      <strong>本次学习任务</strong>
                      <h2>理解“{selectedPoint.title}”并形成练习证据</h2>
                      <p>{recommendation?.description ?? "这是当前课程尚未形成可靠掌握度证据的知识点。"}</p>
                    </div>
                    <ol>
                      <li><b>1</b><span>阅读下方课程核心内容或已就绪资源</span></li>
                      <li><b>2</b><span>需要时让课程助教换一个例子讲解</span></li>
                      <li><b>3</b><span>完成 3 题检查，提交后才形成掌握度证据</span></li>
                    </ol>
                    <div className="guided-learning-actions">
                      <button type="button" onClick={() => onAssistantOpenChange(true)}>让助教换个例子</button>
                      <Link to={`${PATHS.courses}/${courseId}/practice?course_id=${courseId}&knowledge_point_id=${selectedPoint.id}&question_count=3&new=1`}>我已阅读，开始 3 题检查</Link>
                    </div>
                  </section>
                ) : null}
                <span className="course-content-kicker">{selectedPoint.chapter ?? "课程知识点"}</span>
                <h2>{selectedPoint.title}</h2>
                <p className="course-content-objective">{selectedPoint.summary ?? "这条知识点暂时没有课程摘要，可以打开 AI 辅导继续追问。"}</p>
                <dl aria-label="知识点信息">
                  <div><dt>章节</dt><dd>{selectedPoint.chapter ?? "课程知识点"}</dd></div>
                  <div><dt>难度</dt><dd>{selectedPoint.difficulty ?? "未标注"}</dd></div>
                  <div><dt>先修知识</dt><dd>{(selectedPoint.prerequisite_ids ?? []).length} 个</dd></div>
                </dl>
                {selectedCitation ? (
                  <aside className="course-content-citation-focus" aria-label="本次回答引用">
                    <strong>从回答来源进入</strong>
                    <p>{selectedCitation.content}</p>
                    <span>{selectedCitation.source_title} · {selectedCitation.section_title ?? "课程切片"} · {retrievalSourceLabel(selectedCitation.retrieval_source)} · {embeddingStatusLabel(selectedCitation.embedding_status)}</span>
                  </aside>
                ) : null}
                {contentPending ? <p className="course-content-loading">正在读取真实课程内容。</p> : null}
                <InlineFeedback
                  message={contentError ? "课程正文读取失败，请稍后重试。" : null}
                  tone="warning"
                  className="course-inline-feedback"
                />
                {!contentPending && !contentError && content && contentSections.length === 0 ? (
                  <div className="course-content-empty-section">
                    <strong>暂无关联课程切片</strong>
                    <p>可以围绕这个知识点继续提问，系统不会生成虚假正文。</p>
                  </div>
                ) : null}
                {contentSections.map((section) => (
                  <section className="course-content-section" key={section.chunk_id}>
                    <h3>{section.title}</h3>
                    <p>{section.content}</p>
                    <small>{section.source_title}{section.page_number ? ` · 第 ${section.page_number} 页` : ""}</small>
                  </section>
                ))}
                {relatedResources.length ? (
                  <section className="course-content-resources" aria-label="相关学习资源">
                    <h3>相关学习资源</h3>
                    {relatedResources.map((resource) => (
                      <Link key={resource.id} to={studioResourceHref(courseId, resource.id, assistantOpen, courseSessionId)}>
                        {resource.title}
                      </Link>
                    ))}
                  </section>
                ) : null}
                <nav className="course-content-pager" aria-label="知识点导航">
                  <button type="button" disabled={!content?.previous_knowledge_point_id} onClick={onSelectPrevious}>上一个知识点</button>
                  <button type="button" disabled={!content?.next_knowledge_point_id} onClick={onSelectNext}>下一个知识点</button>
                </nav>
              </>
            ) : (
              <div className="course-content-empty">
                <BookOpenText size={28} weight="duotone" aria-hidden="true" />
                <h2>还没有可学习的知识点</h2>
                <p>课程资料完成解析和建课后，知识点会出现在这里。</p>
              </div>
            )}
          </article>
        )}
      </main>

      <CourseMentorDock
        open={assistantOpen}
        courseTitle={courseTitle}
        pointTitle={selectedPoint?.title ?? "当前课程"}
        masteryScore={masteryPoints.find((point) => point.id === selectedPoint?.id)?.score ?? null}
        weaknessCount={weaknesses.filter((item) => item.knowledge_point_id === selectedPoint?.id && ["pending", "confirmed", "reviewing"].includes(item.status)).length}
        recommendation={recommendation}
        messages={messages}
        prompt={prompt}
        isSending={isSending}
        feedback={feedback}
        isListening={isListening}
        isTranscribing={isTranscribing}
        isSpeaking={isSpeaking}
        isSpeechPaused={isSpeechPaused}
        onOpenChange={onAssistantOpenChange}
        onPromptChange={onPromptChange}
        onPromptKeyDown={onPromptKeyDown}
        onSend={onSend}
        onToggleListening={onToggleListening}
        onReadLatest={onReadLatest}
        onPauseOrResume={onPauseOrResumeSpeaking}
        onStopSpeaking={onStopSpeaking}
      />
    </section>
  );
}

function studioResourceHref(courseId: number, resourceId: string, assistantOpen: boolean, courseSessionId: string | null) {
  const params = new URLSearchParams({ course_id: String(courseId), resource_id: resourceId });
  if (assistantOpen) params.set("mentor", "open");
  if (assistantOpen && courseSessionId) params.set("course_session_id", courseSessionId);
  return `${PATHS.studio}?${params.toString()}`;
}

function studioKnowledgePointHref(courseId: number, pointId: string, assistantOpen: boolean, courseSessionId: string | null) {
  const params = new URLSearchParams({ course_id: String(courseId), knowledge_point_id: pointId });
  if (assistantOpen) params.set("mentor", "open");
  if (assistantOpen && courseSessionId) params.set("course_session_id", courseSessionId);
  return `${PATHS.studio}?${params.toString()}`;
}

function groupByChapter(points: ApiCourseKnowledgePoint[]) {
  const groups = new Map<string, ApiCourseKnowledgePoint[]>();
  for (const point of points) {
    const chapter = point.chapter?.trim() || "课程知识点";
    groups.set(chapter, [...(groups.get(chapter) ?? []), point]);
  }
  return [...groups.entries()].map(([title, chapterPoints]) => ({
    title,
    points: [...chapterPoints].sort((a, b) => a.order_index - b.order_index)
  }));
}

function retrievalSourceLabel(source?: string | null) {
  if (source === "hybrid") return "混合检索";
  if (source === "vector") return "向量检索";
  return "关键词检索";
}

function embeddingStatusLabel(status?: string | null) {
  if (status === "local_fallback") return "基础检索";
  if (status === "completed") return "真实向量";
  if (status === "provider_failed") return "关键词检索";
  return "关键词检索";
}

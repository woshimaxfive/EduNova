import { BookOpenText, ChatCircleText, Graph, List, X } from "@phosphor-icons/react";
import { type KeyboardEvent, useMemo } from "react";

import { type ApiCourseKnowledgePoint, type CourseMasteryPoint } from "../../api/courses";
import { type RagSearchResultItem } from "../../api/rag";
import { CourseKnowledgeGraph } from "./CourseKnowledgeGraph";
import { InlineFeedback } from "../feedback/InlineFeedback";
import { MarkdownMessage } from "../feedback/MarkdownMessage";

export type CourseContentMode = "overview" | "graph";

type CourseContentMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
};

type CourseContentViewProps = {
  points: ApiCourseKnowledgePoint[];
  masteryPoints: CourseMasteryPoint[];
  selectedPoint: ApiCourseKnowledgePoint | null;
  selectedCitation: RagSearchResultItem | null;
  view: CourseContentMode;
  assistantOpen: boolean;
  messages: CourseContentMessage[];
  prompt: string;
  isSending: boolean;
  feedback: string | null;
  onViewChange: (view: CourseContentMode) => void;
  onSelectPoint: (pointId: string) => void;
  onOpenAssistant: () => void;
  onCloseAssistant: () => void;
  onPromptChange: (value: string) => void;
  onPromptKeyDown: (event: KeyboardEvent<HTMLTextAreaElement>) => void;
  onSend: () => void;
};

export function CourseContentView({
  points,
  masteryPoints,
  selectedPoint,
  selectedCitation,
  view,
  assistantOpen,
  messages,
  prompt,
  isSending,
  feedback,
  onViewChange,
  onSelectPoint,
  onOpenAssistant,
  onCloseAssistant,
  onPromptChange,
  onPromptKeyDown,
  onSend
}: CourseContentViewProps) {
  const chapters = useMemo(() => groupByChapter(points), [points]);

  return (
    <section className="course-content-workspace" role="region" aria-label="课程内容模式">
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
                  onClick={() => onSelectPoint(point.id)}
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
          <button className="course-content-assistant-trigger" type="button" onClick={onOpenAssistant}>
            <ChatCircleText size={18} weight="duotone" aria-hidden="true" />
            <span>围绕这里提问</span>
          </button>
        </div>

        {view === "graph" ? (
          <div className="course-content-graph-view">
            <CourseKnowledgeGraph points={masteryPoints} selectedId={selectedPoint?.id} onSelect={onSelectPoint} />
          </div>
        ) : (
          <article className="course-content-reader" aria-label="学习内容">
            {selectedCitation ? (
              <>
                <span className="course-content-kicker">资料来源</span>
                <h2>{selectedCitation.section_title ?? selectedCitation.source_title}</h2>
                <p>{selectedCitation.content}</p>
                <dl aria-label="引用信息">
                  <div><dt>资料</dt><dd>{selectedCitation.source_title}</dd></div>
                  <div><dt>检索方式</dt><dd>{retrievalSourceLabel(selectedCitation.retrieval_source)}</dd></div>
                  <div><dt>向量状态</dt><dd>{embeddingStatusLabel(selectedCitation.embedding_status)}</dd></div>
                </dl>
              </>
            ) : selectedPoint ? (
              <>
                <span className="course-content-kicker">{selectedPoint.chapter ?? "课程知识点"}</span>
                <h2>{selectedPoint.title}</h2>
                <p>{selectedPoint.summary ?? "这条知识点暂时没有课程摘要，可以打开 AI 辅导继续追问。"}</p>
                <dl aria-label="知识点信息">
                  <div><dt>章节</dt><dd>{selectedPoint.chapter ?? "课程知识点"}</dd></div>
                  <div><dt>难度</dt><dd>{selectedPoint.difficulty ?? "未标注"}</dd></div>
                  <div><dt>先修知识</dt><dd>{(selectedPoint.prerequisite_ids ?? []).length} 个</dd></div>
                </dl>
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

      {assistantOpen ? (
        <div className="course-content-assistant-layer" role="presentation" onMouseDown={(event) => {
          if (event.target === event.currentTarget) onCloseAssistant();
        }}>
          <aside className="course-content-assistant" role="dialog" aria-modal="true" aria-labelledby="course-content-assistant-title">
            <header>
              <div>
                <span>当前课程上下文</span>
                <h2 id="course-content-assistant-title">AI 辅导</h2>
              </div>
              <button type="button" aria-label="关闭 AI 辅导" onClick={onCloseAssistant}>
                <X size={19} weight="bold" aria-hidden="true" />
              </button>
            </header>
            <div className="course-content-mini-thread">
              {messages.slice(-2).map((message) => (
                <article className={`course-message ${message.role}`} key={message.id}>
                  {message.role === "assistant" ? <MarkdownMessage content={message.content} /> : <p>{message.content}</p>}
                </article>
              ))}
              {messages.length === 0 ? <p className="course-content-assistant-empty">围绕当前知识点提问，回答会继续保存在这门课程的会话中。</p> : null}
            </div>
            <div className="course-content-composer">
              <label htmlFor="course-content-question-input">课程问题输入</label>
              <textarea
                id="course-content-question-input"
                rows={4}
                value={prompt}
                onChange={(event) => onPromptChange(event.target.value)}
                onKeyDown={onPromptKeyDown}
                placeholder="问这里为什么，换个例子，或让它出一道练习"
              />
              <button type="button" disabled={isSending} onClick={onSend}>{isSending ? "发送中" : "发送"}</button>
              <InlineFeedback message={feedback} tone="warning" className="course-inline-feedback" />
            </div>
          </aside>
        </div>
      ) : null}
    </section>
  );
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
  if (status === "local_fallback") return "本地 fallback";
  if (status === "completed") return "真实向量";
  if (status === "provider_failed") return "关键词兜底";
  return "关键词检索";
}

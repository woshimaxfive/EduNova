import {
  ArrowLeft,
  ArrowRight,
  ChartLineUp,
  ChatCircleText,
  CheckCircle,
  Compass,
  FileText,
  ListChecks,
  Sparkle,
  Target
} from "@phosphor-icons/react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { type KeyboardEvent, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { PATHS } from "../app/routePaths";
import { getCourse, getCourseOverview, getKnowledgePoints, type ApiCourseKnowledgePoint } from "../api/courses";
import { type RagSearchResultItem } from "../api/rag";
import {
  createTutorSession,
  getTutorSession,
  listTutorSessions,
  sendTutorMessage,
  type TutorMessage,
  type TutorSessionSummary
} from "../api/tutor";
import { LearningCanvas } from "../components/canvas/LearningCanvas";
import { EvidenceLayer } from "../components/evidence/EvidenceLayer";
import { ActionNotice } from "../components/feedback/ActionNotice";
import { useActionNotice } from "../components/feedback/useActionNotice";
import { AppSidebar } from "../components/layout/AppSidebar";
import { LearningSpaceShell } from "../components/layout/LearningSpaceShell";
import { StudioDock } from "../components/studio/StudioDock";
import { demoLearningSpace } from "../data/demoLearningSpace";
import { type AgentTraceEvent, type CitationRef } from "../types/api";

const courseThreads = [
  "监督学习这一章怎么安排复习？",
  "把神经网络薄弱点整理成练习",
  "解释泛化能力和过拟合的区别"
];

const courseActionLinks = [
  { label: "查看学习路径", to: PATHS.path, icon: Compass },
  { label: "进入 AI 辅导", to: PATHS.tutor, icon: ChatCircleText },
  { label: "开始练习", to: PATHS.practice, icon: ListChecks },
  { label: "查看学习报告", to: PATHS.reports, icon: ChartLineUp }
];

function mapKnowledgePointsToNodes(points: ApiCourseKnowledgePoint[]) {
  return points.map((point, index) => {
    const column = index % 4;
    const row = Math.floor(index / 4);

    return {
      id: point.id,
      title: point.title,
      chapter: point.chapter,
      status: index === 0 ? ("focus" as const) : ("ready" as const),
      x: 14 + column * 22,
      y: 24 + row * 26
    };
  });
}

function materialTypeFromTitle(title: string) {
  const extension = title.split(".").pop()?.toLowerCase();

  if (extension === "md" || extension === "markdown") {
    return "markdown" as const;
  }
  if (extension === "txt") {
    return "txt" as const;
  }
  if (extension === "pdf") {
    return "pdf" as const;
  }
  if (extension === "pptx") {
    return "pptx" as const;
  }
  if (extension === "docx") {
    return "docx" as const;
  }
  return "txt" as const;
}

function confidenceFromScore(score: number): CitationRef["confidence"] {
  if (score >= 6) {
    return "high";
  }
  if (score >= 3) {
    return "medium";
  }
  return "low";
}

function mapRagResultsToCitations(results: RagSearchResultItem[]): CitationRef[] {
  return results.map((result) => ({
    id: `chunk-${result.chunk_id}`,
    sourceTitle: result.source_title,
    sectionTitle: result.section_title ?? "课程切片",
    pageNumber: result.page_number ?? undefined,
    confidence: confidenceFromScore(result.score)
  }));
}

function buildCourseMaterials(titles: string[], knowledgePointCount: number) {
  return titles.map((title, index) => ({
    id: index + 1,
    title,
    type: materialTypeFromTitle(title),
    parseStatus: "completed" as const,
    coverageLabel: `${knowledgePointCount} 个知识点`
  }));
}

type AnswerPanelKind = "citations" | "path" | "agent";
type CourseMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: RagSearchResultItem[];
};

function courseQuestionTitle(question: string) {
  const normalized = question.trim();
  return normalized.length > 30 ? `${normalized.slice(0, 30)}...` : normalized;
}

function mapTutorMessagesToCourseMessages(messages: TutorMessage[]): CourseMessage[] {
  return messages.map((message) => ({
    id: message.id,
    role: message.role,
    content: message.content,
    citations: message.role === "assistant" ? message.citation_json : undefined
  }));
}

function mapCourseSessionsToConversations(sessions: TutorSessionSummary[]) {
  return sessions.map((session) => ({
    id: session.id,
    title: session.title,
    meta: "课程内"
  }));
}

export function CourseSpacePage() {
  const { courseId } = useParams();
  const numericCourseId = courseId ? Number.parseInt(courseId, 10) : Number.NaN;
  const hasRealCourseId = Number.isFinite(numericCourseId);
  const queryClient = useQueryClient();
  const courseQuery = useQuery({
    queryKey: ["courses", "detail", numericCourseId],
    queryFn: () => getCourse(numericCourseId),
    enabled: hasRealCourseId,
    staleTime: 30_000
  });
  const knowledgePointsQuery = useQuery({
    queryKey: ["courses", "knowledge-points", numericCourseId],
    queryFn: () => getKnowledgePoints(numericCourseId),
    enabled: hasRealCourseId,
    staleTime: 30_000
  });
  const courseOverviewQuery = useQuery({
    queryKey: ["courses", "overview", numericCourseId],
    queryFn: () => getCourseOverview(numericCourseId),
    enabled: hasRealCourseId,
    staleTime: 30_000
  });
  const courseSessionsQuery = useQuery({
    queryKey: ["tutor", "sessions", "course", numericCourseId],
    queryFn: () => listTutorSessions("course", numericCourseId),
    enabled: hasRealCourseId,
    staleTime: 10_000
  });
  const [threads, setThreads] = useState(courseThreads);
  const [activeThread, setActiveThread] = useState(courseThreads[0]);
  const [activeCourseSessionId, setActiveCourseSessionId] = useState<string | null>(null);
  const [activeAnswerPanel, setActiveAnswerPanel] = useState<AnswerPanelKind>("citations");
  const [isHistoryCollapsed, setIsHistoryCollapsed] = useState(false);
  const [coursePrompt, setCoursePrompt] = useState("");
  const [courseMessages, setCourseMessages] = useState<CourseMessage[]>([]);
  const [isSearchingCourse, setIsSearchingCourse] = useState(false);
  const { notice, showNotice } = useActionNotice();
  const snapshot = demoLearningSpace;
  const apiCourse = courseQuery.data?.data;
  const apiKnowledgePoints = useMemo(
    () => knowledgePointsQuery.data?.data ?? [],
    [knowledgePointsQuery.data?.data]
  );
  const overviewMaterials = courseOverviewQuery.data?.data.materials ?? [];
  const courseSessions = Array.isArray(courseSessionsQuery.data?.data) ? courseSessionsQuery.data.data : [];
  const latestCourseSessionId = courseSessions[0]?.id ?? null;
  const selectedCourseSessionId = hasRealCourseId ? (activeCourseSessionId ?? latestCourseSessionId) : null;
  const activeCourseSessionQuery = useQuery({
    queryKey: ["tutor", "session", selectedCourseSessionId],
    queryFn: () => getTutorSession(selectedCourseSessionId ?? ""),
    enabled: hasRealCourseId && Boolean(selectedCourseSessionId),
    staleTime: 5_000
  });
  const sidebarConversations = hasRealCourseId
    ? mapCourseSessionsToConversations(courseSessions)
    : threads.map((title, index) => ({ id: `course-thread-${index}`, title, meta: "课程内" }));
  const activeCourseSessionDetail = activeCourseSessionQuery.data?.data;
  const activeCourseSessionDetailId = activeCourseSessionDetail?.session?.id ?? null;
  const persistedCourseMessages = useMemo(() => {
    if (!hasRealCourseId || activeCourseSessionDetailId !== selectedCourseSessionId) {
      return [];
    }

    return mapTutorMessagesToCourseMessages(activeCourseSessionDetail?.messages ?? []);
  }, [activeCourseSessionDetail?.messages, activeCourseSessionDetailId, hasRealCourseId, selectedCourseSessionId]);
  const displayedCourseMessages =
    hasRealCourseId && selectedCourseSessionId && activeCourseSessionDetailId === selectedCourseSessionId
      ? persistedCourseMessages
      : courseMessages;
  const courseSummary = apiCourse
    ? {
        id: Number.parseInt(apiCourse.id, 10),
        title: apiCourse.title,
        description: apiCourse.description,
        subject: apiCourse.subject,
        sourceType: apiCourse.source_type,
        progressPercent: apiCourse.progress_percent
      }
    : snapshot.currentCourse;
  const knowledgeNodes = apiKnowledgePoints.length > 0 ? mapKnowledgePointsToNodes(apiKnowledgePoints) : snapshot.knowledgeNodes;
  const sourceMaterials =
    overviewMaterials.length > 0
      ? buildCourseMaterials(overviewMaterials, apiCourse?.knowledge_point_count ?? apiKnowledgePoints.length)
      : apiCourse && apiCourse.material_count > 0
        ? Array.from({ length: apiCourse.material_count }, (_, index) => ({
            id: index + 1,
            title: `课程资料 ${index + 1}`,
            type: "txt" as const,
            parseStatus: "completed" as const,
            coverageLabel: `${apiCourse.knowledge_point_count} 个知识点`
          }))
        : snapshot.materials;
  const latestAssistantWithRetrieval = [...displayedCourseMessages].reverse().find((message) => message.role === "assistant" && message.citations !== undefined);
  const latestRagResults = latestAssistantWithRetrieval?.citations ?? [];
  const hasRetrievalResult = Boolean(latestAssistantWithRetrieval);
  const evidenceCitations = apiCourse ? mapRagResultsToCitations(latestRagResults) : snapshot.citations;
  const retrieverStatus: AgentTraceEvent["status"] = !hasRetrievalResult
    ? "pending"
    : latestRagResults.length === 0
      ? "warning"
      : "completed";
  const canvasSnapshot = {
    ...snapshot,
    currentCourse: {
      ...courseSummary,
      title: `${courseSummary.title}知识画布`
    },
    materials: sourceMaterials,
    knowledgeNodes
  };
  const evidenceSnapshot = {
    ...canvasSnapshot,
    citations: evidenceCitations,
    agentTrace: apiCourse
      ? [
          {
            id: "rag-retriever",
            agentName: "RetrieverAgent",
            summary: hasRetrievalResult ? `检索到 ${latestRagResults.length} 条课程切片引用` : "等待课程问题触发检索",
            status: retrieverStatus,
            durationMs: hasRetrievalResult ? 120 : undefined
          }
        ]
      : snapshot.agentTrace
  };
  const materialCount = apiCourse?.material_count ?? snapshot.materials.length;
  const knowledgePointCount = apiCourse?.knowledge_point_count ?? snapshot.knowledgeNodes.length;

  function selectCourseConversation(sessionId: string) {
    if (!hasRealCourseId) {
      return;
    }

    setActiveCourseSessionId(sessionId);
    setCourseMessages([]);
  }

  function appendDemoCourseMessages(question: string, assistantAnswer: string, citations?: RagSearchResultItem[]) {
    const timestamp = Date.now();
    setCourseMessages((current) => [
      ...current,
      { id: `course-user-${timestamp}`, role: "user", content: question },
      { id: `course-assistant-${timestamp}`, role: "assistant", content: assistantAnswer, citations }
    ]);
    setThreads((current) => (current.includes(question) ? current : [question, ...current]));
    setActiveThread(question);
  }

  async function sendCourseQuestion() {
    const question = coursePrompt.trim();

    if (!question) {
      showNotice("先输入课程问题。", "warning");
      return;
    }

    if (isSearchingCourse) {
      return;
    }

    if (!hasRealCourseId) {
      appendDemoCourseMessages(question, "我会按课程资料回答：先定位相关知识点，再给出复习顺序、引用来源和下一步练习。");
      setCoursePrompt("");
      showNotice("已生成课程回答。", "success");
      return;
    }

    setIsSearchingCourse(true);

    try {
      let sessionId = activeCourseSessionId ?? latestCourseSessionId;

      if (!sessionId) {
        const createdSession = await createTutorSession({
          scope: "course",
          course_id: numericCourseId,
          mode: "chat",
          title: courseQuestionTitle(question)
        });
        sessionId = createdSession.data.id;
        setActiveCourseSessionId(sessionId);
      }

      const detail = await sendTutorMessage(sessionId, { message: question });
      const messages = mapTutorMessagesToCourseMessages(detail.data.messages);
      const latestAssistant = [...messages].reverse().find((message) => message.role === "assistant");
      const citationCount = latestAssistant?.citations?.length ?? 0;

      setActiveCourseSessionId(detail.data.session.id);
      setCourseMessages(messages);
      setCoursePrompt("");
      queryClient.setQueryData(["tutor", "session", detail.data.session.id], detail);
      void queryClient.invalidateQueries({ queryKey: ["tutor", "sessions", "course", numericCourseId] });
      showNotice(citationCount > 0 ? "已保存课程回答和引用。" : "课程资料依据不足。", citationCount > 0 ? "success" : "warning");
    } catch {
      showNotice("课程会话保存失败，请稍后重试。", "warning");
    } finally {
      setIsSearchingCourse(false);
    }
  }

  function handleCourseComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void sendCourseQuestion();
    }
  }

  return (
    <LearningSpaceShell hideTopNavigation>
      <section className={isHistoryCollapsed ? "app-workspace-layout history-collapsed" : "app-workspace-layout"}>
        <div className="learning-signal" aria-hidden="true">
          <span />
          <span />
          <span />
        </div>
        <AppSidebar
          isCollapsed={isHistoryCollapsed}
          conversations={sidebarConversations}
          activeConversationId={hasRealCourseId ? selectedCourseSessionId : sidebarConversations.find((conversation) => conversation.title === activeThread)?.id}
          onToggleCollapsed={() => setIsHistoryCollapsed((collapsed) => !collapsed)}
          onSelectConversation={(conversation) =>
            hasRealCourseId ? void selectCourseConversation(conversation.id) : setActiveThread(conversation.title)
          }
        />
        <section className="route-main-surface course-route-surface">
          <div className="course-space">
            <header className="course-space-hero">
              <Link className="course-back-link" to={PATHS.app}>
                <ArrowLeft size={17} weight="bold" aria-hidden="true" />
                <span>回到学习主页</span>
              </Link>
              <div className="course-space-title">
                <h1>{courseSummary.title}</h1>
                <p>{courseSummary.description} 课程对话、资料、路径和引用都在这里。</p>
              </div>
              <dl className="course-space-metrics" aria-label="课程状态">
                <div>
                  <dt>进度</dt>
                  <dd>{courseSummary.progressPercent}%</dd>
                </div>
                <div>
                  <dt>资料</dt>
                  <dd>{materialCount}</dd>
                </div>
                <div>
                  <dt>知识点</dt>
                  <dd>{knowledgePointCount}</dd>
                </div>
              </dl>
            </header>

            <section className="course-space-grid">
              <section className="course-chat-panel" role="region" aria-label="课程对话空间">
                <div className="course-panel-heading">
                  <span className="course-panel-icon" aria-hidden="true">
                    <ChatCircleText size={20} weight="duotone" />
                  </span>
                  <div>
                    <h2>继续问</h2>
                  </div>
                </div>

                <div className="course-thread-list" aria-label="课程内历史对话">
                  {hasRealCourseId ? (
                    courseSessions.length > 0 ? (
                      courseSessions.map((session) => (
                        <button
                          className={selectedCourseSessionId === session.id ? "active" : ""}
                          type="button"
                          key={session.id}
                          aria-pressed={selectedCourseSessionId === session.id}
                          onClick={() => void selectCourseConversation(session.id)}
                        >
                          {session.title}
                        </button>
                      ))
                    ) : (
                      <p className="course-thread-empty">还没有课程对话</p>
                    )
                  ) : (
                    threads.map((thread) => (
                      <button
                        className={activeThread === thread ? "active" : ""}
                        type="button"
                        key={thread}
                        aria-pressed={activeThread === thread}
                        onClick={() => setActiveThread(thread)}
                      >
                        {thread}
                      </button>
                    ))
                  )}
                </div>

                <article className="course-answer">
                  <p className="course-answer-label">AI 辅导回答</p>
                  <h2>监督学习先抓住“数据、目标、泛化”三件事</h2>
                  <p>先区分训练集和测试集，再把过拟合、泛化误差和正则化连起来。</p>
                  <div className="answer-action-row" aria-label="回答展开入口">
                    <button
                      className={activeAnswerPanel === "citations" ? "active" : ""}
                      type="button"
                      aria-pressed={activeAnswerPanel === "citations"}
                      onClick={() => setActiveAnswerPanel("citations")}
                    >
                      <FileText size={17} weight="duotone" aria-hidden="true" />
                      <span>引用来源</span>
                    </button>
                    <button
                      className={activeAnswerPanel === "path" ? "active" : ""}
                      type="button"
                      aria-pressed={activeAnswerPanel === "path"}
                      onClick={() => setActiveAnswerPanel("path")}
                    >
                      <Target size={17} weight="duotone" aria-hidden="true" />
                      <span>学习路径</span>
                    </button>
                    <button
                      className={activeAnswerPanel === "agent" ? "active" : ""}
                      type="button"
                      aria-pressed={activeAnswerPanel === "agent"}
                      onClick={() => setActiveAnswerPanel("agent")}
                    >
                      <Sparkle size={17} weight="duotone" aria-hidden="true" />
                      <span>Agent 过程</span>
                    </button>
                  </div>
                  <AnswerDetailPanel
                    activePanel={activeAnswerPanel}
                    citations={latestRagResults}
                    hasRealCourse={Boolean(apiCourse)}
                    hasSearched={hasRetrievalResult}
                  />
                  <div className="answer-citation-strip" aria-label="回答引用预览">
                    {apiCourse
                      ? latestRagResults.map((citation) => <span key={citation.chunk_id}>{citation.source_title}</span>)
                      : snapshot.citations.map((citation) => <span key={citation.id}>{citation.sourceTitle}</span>)}
                  </div>
                </article>

                {displayedCourseMessages.length > 0 ? (
                  <section className="course-message-stack" aria-label="课程即时对话">
                    {displayedCourseMessages.map((message) => (
                      <article className={`course-message ${message.role}`} key={message.id}>
                        <p>{message.content}</p>
                        {message.role === "assistant" && message.citations !== undefined ? (
                          <CourseMessageCitations citations={message.citations} />
                        ) : null}
                      </article>
                    ))}
                  </section>
                ) : null}

                <div className="course-composer">
                  <label htmlFor="course-question-input">课程问题输入</label>
                  <textarea
                    id="course-question-input"
                    rows={3}
                    value={coursePrompt}
                    onChange={(event) => setCoursePrompt(event.target.value)}
                    onKeyDown={handleCourseComposerKeyDown}
                    placeholder="继续问这门课，例如：给我生成监督学习 10 分钟复习路线"
                  />
                  <button className="course-send-button" type="button" disabled={isSearchingCourse} onClick={() => void sendCourseQuestion()}>
                    <ArrowRight size={17} weight="bold" aria-hidden="true" />
                    <span>{isSearchingCourse ? "保存中" : "发送"}</span>
                  </button>
                </div>
                <ActionNotice notice={notice} />
              </section>

              <aside className="course-context-panel" aria-label="课程学习上下文">
                <div className="course-panel-heading">
                  <span className="course-panel-icon" aria-hidden="true">
                    <CheckCircle size={20} weight="duotone" />
                  </span>
                  <div>
                    <h2>下一步</h2>
                  </div>
                </div>
                <ol className="course-task-list" aria-label="课程任务">
                  {snapshot.todayTasks.map((task) => (
                    <li key={task.id} className={task.status}>
                      <strong>{task.title}</strong>
                      <span>{task.type}</span>
                    </li>
                  ))}
                </ol>
                <nav className="course-action-links" aria-label="课程行动入口">
                  {courseActionLinks.map((action) => {
                    const Icon = action.icon;

                    return (
                      <Link key={action.to} to={action.to}>
                        <Icon size={17} weight="duotone" aria-hidden="true" />
                        <span>{action.label}</span>
                      </Link>
                    );
                  })}
                </nav>
              </aside>
            </section>

            <LearningCanvas snapshot={canvasSnapshot} />

            <div className="course-space-secondary">
              <StudioDock outputs={snapshot.studioOutputs} />
              <EvidenceLayer snapshot={evidenceSnapshot} />
            </div>
          </div>
        </section>
      </section>
    </LearningSpaceShell>
  );
}

type AnswerDetailPanelProps = {
  activePanel: AnswerPanelKind;
  citations: RagSearchResultItem[];
  hasRealCourse: boolean;
  hasSearched: boolean;
};

function CourseMessageCitations({ citations }: { citations: RagSearchResultItem[] }) {
  if (citations.length === 0) {
    return (
      <section className="answer-detail-panel course-message-citations" role="region" aria-label="课程回答引用">
        <strong>引用来源</strong>
        <p>当前课程资料里没有找到足够依据。</p>
      </section>
    );
  }

  return (
    <section className="answer-detail-panel course-message-citations" role="region" aria-label="课程回答引用">
      <strong>引用来源</strong>
      <div className="citation-list">
        {citations.map((citation) => (
          <article key={citation.chunk_id} className="citation-item">
            <strong>{citation.source_title}</strong>
            <span>{citation.section_title ?? "课程切片"}</span>
            <small>匹配度 {citation.score.toFixed(1)}</small>
            <p>{citation.content}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

function AnswerDetailPanel({ activePanel, citations, hasRealCourse, hasSearched }: AnswerDetailPanelProps) {
  if (activePanel === "path") {
    return (
      <section className="answer-detail-panel" role="region" aria-label="回答展开详情">
        <strong>建议路径</strong>
        <p>先复习训练集、测试集和目标函数，再进入过拟合、正则化和泛化误差，最后用 10 分钟练习巩固。</p>
      </section>
    );
  }

  if (activePanel === "agent") {
    return (
      <section className="answer-detail-panel" role="region" aria-label="回答展开详情">
        <strong>Agent 过程</strong>
        <p>RetrieverAgent 先检索课程资料，PathAgent 生成复习顺序，TutorAgent 再把结论写成可追问回答。</p>
      </section>
    );
  }

  if (hasRealCourse) {
    if (!hasSearched) {
      return (
        <section className="answer-detail-panel" role="region" aria-label="回答展开详情">
          <strong>引用来源</strong>
          <p>发送课程问题后，会先从本课程知识切片中检索真实引用。</p>
        </section>
      );
    }

    if (citations.length === 0) {
      return (
        <section className="answer-detail-panel" role="region" aria-label="回答展开详情">
          <strong>引用来源</strong>
          <p>当前课程资料里没有找到足够依据。</p>
        </section>
      );
    }

    return (
      <section className="answer-detail-panel" role="region" aria-label="回答展开详情">
        <strong>引用来源</strong>
        <div className="citation-list">
          {citations.map((citation) => (
            <article key={citation.chunk_id} className="citation-item">
              <strong>{citation.source_title}</strong>
              <span>{citation.section_title ?? "课程切片"}</span>
              <small>匹配度 {citation.score.toFixed(1)}</small>
            </article>
          ))}
        </div>
      </section>
    );
  }

  return (
    <section className="answer-detail-panel" role="region" aria-label="回答展开详情">
      <strong>引用来源</strong>
      <p>AI 导论内置讲义和期末复习题样例会作为回答依据。</p>
    </section>
  );
}

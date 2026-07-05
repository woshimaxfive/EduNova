import {
  ArrowLeft,
  ArrowRight,
  ChartLineUp,
  ChatCircleText,
  Compass,
  FileText,
  ListChecks,
  Sparkle,
  Target
} from "@phosphor-icons/react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { type KeyboardEvent, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { PATHS } from "../app/routePaths";
import { getAgentTrace, mapAgentTraceStepToEvent } from "../api/agents";
import {
  getCourse,
  getCourseLearningState,
  getCourseOverview,
  getKnowledgePoints,
  updateCourseWeaknessReviewItem,
  type CourseWeaknessReviewAction,
  type CourseWeaknessReviewItem
} from "../api/courses";
import { type RagSearchResultItem } from "../api/rag";
import {
  createTutorSession,
  getTutorSession,
  listTutorSessions,
  streamTutorMessage,
  type TutorMessage,
  type TutorSessionSummary
} from "../api/tutor";
import { AgentTimeline } from "../components/evidence/AgentTimeline";
import { InlineFeedback } from "../components/feedback/InlineFeedback";
import { AppSidebar } from "../components/layout/AppSidebar";
import { LearningSpaceShell } from "../components/layout/LearningSpaceShell";
import { type AgentTraceEvent } from "../types/api";

const courseStarterQuestions = [
  "这门课最适合先复习哪些知识点？",
  "把当前资料里的重点整理成期末复习顺序",
  "根据引用帮我找一个薄弱点练习方向"
];

const courseActionLinks = [
  { label: "查看学习路径", to: PATHS.path, icon: Compass },
  { label: "进入 AI 辅导", to: PATHS.tutor, icon: ChatCircleText },
  { label: "开始练习", to: PATHS.practice, icon: ListChecks },
  { label: "查看学习报告", to: PATHS.reports, icon: ChartLineUp }
];

function retrievalSourceLabel(source?: string | null) {
  if (source === "hybrid") {
    return "混合检索";
  }
  if (source === "vector") {
    return "向量检索";
  }
  return "关键词检索";
}

function embeddingStatusLabel(status?: string | null) {
  if (status === "local_fallback") {
    return "本地 fallback (local-hash-1536)";
  }
  if (status === "completed") {
    return "真实向量";
  }
  if (status === "provider_failed") {
    return "关键词兜底";
  }
  return "关键词检索";
}

function weaknessStatusLabel(status: string) {
  if (status === "confirmed") {
    return "待复习";
  }
  if (status === "reviewing") {
    return "复习中";
  }
  if (status === "completed") {
    return "已完成";
  }
  if (status === "dismissed") {
    return "已忽略";
  }
  return "待确认";
}

function weaknessActionsForItem(item: CourseWeaknessReviewItem): Array<{ action: CourseWeaknessReviewAction; label: string; icon: typeof ListChecks }> {
  if (item.status === "pending") {
    return [
      { action: "confirm", label: "确认", icon: ListChecks },
      { action: "start", label: "开始", icon: ArrowRight },
      { action: "dismiss", label: "忽略", icon: ArrowLeft }
    ];
  }
  if (item.status === "confirmed") {
    return [
      { action: "start", label: "开始", icon: ArrowRight },
      { action: "complete", label: "完成", icon: Target },
      { action: "dismiss", label: "忽略", icon: ArrowLeft }
    ];
  }
  if (item.status === "reviewing") {
    return [
      { action: "complete", label: "完成", icon: Target },
      { action: "dismiss", label: "忽略", icon: ArrowLeft }
    ];
  }
  if (item.status === "completed") {
    return [{ action: "dismiss", label: "移除", icon: ArrowLeft }];
  }
  return [];
}

type AnswerPanelKind = "citations" | "resources" | "path" | "thinking";
type CourseMode = "chat" | "study";
type StudyTarget =
  | {
      type: "knowledge";
      id: string;
    }
  | {
      type: "citation";
      chunkId: number;
    };
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
  const learningStateQuery = useQuery({
    queryKey: ["courses", "learning-state", numericCourseId],
    queryFn: () => getCourseLearningState(numericCourseId),
    enabled: hasRealCourseId,
    staleTime: 10_000
  });
  const courseSessionsQuery = useQuery({
    queryKey: ["tutor", "sessions", "course", numericCourseId],
    queryFn: () => listTutorSessions("course", numericCourseId),
    enabled: hasRealCourseId,
    staleTime: 10_000
  });
  const [activeCourseSessionId, setActiveCourseSessionId] = useState<string | null>(null);
  const [activeAnswerPanel, setActiveAnswerPanel] = useState<AnswerPanelKind>("citations");
  const [courseMode, setCourseMode] = useState<CourseMode>("chat");
  const [studyTarget, setStudyTarget] = useState<StudyTarget | null>(null);
  const [isHistoryCollapsed, setIsHistoryCollapsed] = useState(false);
  const [coursePrompt, setCoursePrompt] = useState("");
  const [courseMessages, setCourseMessages] = useState<CourseMessage[]>([]);
  const [streamingSessionId, setStreamingSessionId] = useState<string | null>(null);
  const [isSearchingCourse, setIsSearchingCourse] = useState(false);
  const [courseFeedback, setCourseFeedback] = useState<string | null>(null);
  const [weaknessFeedback, setWeaknessFeedback] = useState<string | null>(null);
  const [updatingWeaknessItemId, setUpdatingWeaknessItemId] = useState<string | null>(null);
  const optimisticMessageSequence = useRef(0);
  const apiCourse = courseQuery.data?.data;
  const apiKnowledgePoints = useMemo(
    () => knowledgePointsQuery.data?.data ?? [],
    [knowledgePointsQuery.data?.data]
  );
  const overviewMaterials = courseOverviewQuery.data?.data.materials ?? [];
  const learningState = learningStateQuery.data?.data;
  const weaknessSummary = learningState?.weakness_summary;
  const weaknessItems = (learningState?.weakness_review_queue ?? []).filter((item) => item.status !== "dismissed");
  const latestAgentTraceId = learningState?.evidence_summary?.latest_trace_id ?? null;
  const agentTraceQuery = useQuery({
    queryKey: ["agents", "trace", latestAgentTraceId],
    queryFn: () => getAgentTrace(latestAgentTraceId ?? ""),
    enabled: Boolean(latestAgentTraceId) && activeAnswerPanel === "thinking",
    staleTime: 10_000
  });
  const agentTraceEvents = useMemo(
    () => agentTraceQuery.data?.data.steps.map(mapAgentTraceStepToEvent) ?? [],
    [agentTraceQuery.data?.data.steps]
  );
  const courseSessions = Array.isArray(courseSessionsQuery.data?.data) ? courseSessionsQuery.data.data : [];
  const latestCourseSessionId = courseSessions[0]?.id ?? null;
  const selectedCourseSessionId = hasRealCourseId ? (activeCourseSessionId ?? latestCourseSessionId) : null;
  const activeCourseSessionQuery = useQuery({
    queryKey: ["tutor", "session", selectedCourseSessionId],
    queryFn: () => getTutorSession(selectedCourseSessionId ?? ""),
    enabled: hasRealCourseId && Boolean(selectedCourseSessionId),
    staleTime: 5_000
  });
  const sidebarConversations = hasRealCourseId ? mapCourseSessionsToConversations(courseSessions) : [];
  const activeCourseSessionDetail = activeCourseSessionQuery.data?.data;
  const activeCourseSessionDetailId = activeCourseSessionDetail?.session?.id ?? null;
  const persistedCourseMessages =
    hasRealCourseId && activeCourseSessionDetailId === selectedCourseSessionId
      ? mapTutorMessagesToCourseMessages(activeCourseSessionDetail?.messages ?? [])
      : [];
  const displayedCourseMessages =
    streamingSessionId !== null
      ? courseMessages
      : hasRealCourseId && selectedCourseSessionId && activeCourseSessionDetailId === selectedCourseSessionId
        ? persistedCourseMessages
        : courseMessages;
  const hasDisplayedCourseMessages = displayedCourseMessages.length > 0;
  const isCourseLoading = hasRealCourseId && courseQuery.isPending && !apiCourse;
  const courseSummary = apiCourse
    ? {
        id: Number.parseInt(apiCourse.id, 10),
        title: apiCourse.title,
        description: apiCourse.description,
        subject: apiCourse.subject,
        sourceType: apiCourse.source_type,
        progressPercent: apiCourse.progress_percent
      }
    : {
        id: Number.isFinite(numericCourseId) ? numericCourseId : 0,
        title: isCourseLoading ? "课程加载中" : "课程暂不可用",
        description: isCourseLoading ? "正在读取这门课的资料、知识点和历史对话。" : "请从学习主页或课程列表重新进入。",
        subject: "课程空间",
        sourceType: "uploaded" as const,
        progressPercent: 0
      };
  const latestAssistantWithRetrieval = [...displayedCourseMessages].reverse().find((message) => message.role === "assistant" && message.citations !== undefined);
  const latestRagResults = latestAssistantWithRetrieval?.citations ?? [];
  const hasRetrievalResult = Boolean(latestAssistantWithRetrieval);
  const selectedKnowledgePoint =
    studyTarget?.type === "knowledge" ? apiKnowledgePoints.find((point) => point.id === studyTarget.id) ?? null : null;
  const selectedCitation =
    studyTarget?.type === "citation"
      ? latestRagResults.find((citation) => citation.chunk_id === studyTarget.chunkId) ?? null
      : null;
  const materialCount = apiCourse?.material_count ?? overviewMaterials.length;
  const knowledgePointCount = apiCourse?.knowledge_point_count ?? apiKnowledgePoints.length;

  function selectCourseConversation(sessionId: string) {
    if (!hasRealCourseId) {
      return;
    }

    setActiveCourseSessionId(sessionId);
    setStreamingSessionId(null);
    setCourseMessages([]);
    setCourseMode("chat");
    setStudyTarget(null);
  }

  function openKnowledgeStudy(pointId: string) {
    setCourseMode("study");
    setStudyTarget({ type: "knowledge", id: pointId });
  }

  function openCitationStudy(citation: RagSearchResultItem) {
    setCourseMode("study");
    setStudyTarget({ type: "citation", chunkId: citation.chunk_id });
  }

  async function updateWeaknessReviewItem(item: CourseWeaknessReviewItem, action: CourseWeaknessReviewAction) {
    if (!hasRealCourseId || updatingWeaknessItemId !== null) {
      return;
    }

    setUpdatingWeaknessItemId(item.id);
    setWeaknessFeedback(null);

    try {
      await updateCourseWeaknessReviewItem(numericCourseId, item.id, action);
      void queryClient.invalidateQueries({ queryKey: ["courses", "learning-state", numericCourseId] });
    } catch {
      setWeaknessFeedback("弱点状态更新失败，请稍后重试。");
    } finally {
      setUpdatingWeaknessItemId(null);
    }
  }

  async function sendCourseQuestion() {
    const question = coursePrompt.trim();

    if (!question) {
      setCourseFeedback("先输入课程问题。");
      return;
    }

    if (isSearchingCourse) {
      return;
    }

    if (!hasRealCourseId) {
      setCourseFeedback("课程地址无效，请从课程列表重新进入。");
      return;
    }

    setIsSearchingCourse(true);
    setCourseFeedback(null);
    const previousMessages = displayedCourseMessages;

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
      }

      setActiveCourseSessionId(sessionId);
      setStreamingSessionId(sessionId);
      optimisticMessageSequence.current += 1;
      const optimisticId = optimisticMessageSequence.current;
      const assistantMessageId = `course-assistant-stream-${optimisticId}`;
      const optimisticMessages: CourseMessage[] = [
        ...previousMessages,
        { id: `course-user-stream-${optimisticId}`, role: "user", content: question },
        { id: assistantMessageId, role: "assistant", content: "", citations: [] }
      ];
      setCourseMessages(optimisticMessages);

      const detail = await streamTutorMessage(sessionId, { message: question }, {
        onToken: (content) => {
          setCourseMessages((current) =>
            current.map((message) =>
              message.id === assistantMessageId ? { ...message, content: `${message.content}${content}` } : message
            )
          );
        }
      });
      const messages = mapTutorMessagesToCourseMessages(detail.messages);

      setActiveCourseSessionId(detail.session.id);
      setCourseMessages(messages);
      setStreamingSessionId(null);
      setCoursePrompt("");
      queryClient.setQueryData(["tutor", "session", detail.session.id], { data: detail, trace_id: null });
      void queryClient.invalidateQueries({ queryKey: ["tutor", "sessions", "course", numericCourseId] });
      void queryClient.invalidateQueries({ queryKey: ["courses", "learning-state", numericCourseId] });
    } catch {
      setCourseMessages(previousMessages);
      setStreamingSessionId(null);
      setCourseFeedback("模型暂不可用，请检查设置或稍后重试。");
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
          activeConversationId={hasRealCourseId ? selectedCourseSessionId : null}
          onToggleCollapsed={() => setIsHistoryCollapsed((collapsed) => !collapsed)}
          onSelectConversation={(conversation) =>
            hasRealCourseId ? void selectCourseConversation(conversation.id) : undefined
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

            <div className="course-mode-tabs" aria-label="课程空间模式">
              <button
                className={courseMode === "chat" ? "active" : ""}
                type="button"
                aria-pressed={courseMode === "chat"}
                onClick={() => setCourseMode("chat")}
              >
                问答模式
              </button>
              <button
                className={courseMode === "study" ? "active" : ""}
                type="button"
                aria-pressed={courseMode === "study"}
                onClick={() => setCourseMode("study")}
              >
                学习模式
              </button>
            </div>

            {courseMode === "chat" ? (
              <section className="course-chat-panel course-chat-mode" role="region" aria-label="课程对话空间">
                <div className="course-panel-heading">
                  <span className="course-panel-icon" aria-hidden="true">
                    <ChatCircleText size={20} weight="duotone" />
                  </span>
                  <div>
                    <h2>问这门课</h2>
                  </div>
                </div>

                <div className="course-context-toolbar" aria-label="课程上下文入口">
                  <button type="button" onClick={() => setCourseMode("study")}>
                    <FileText size={17} weight="duotone" aria-hidden="true" />
                    <span>{knowledgePointCount > 0 ? `${knowledgePointCount} 个知识点` : "查看知识点"}</span>
                  </button>
                  <button type="button" onClick={() => setCoursePrompt(courseStarterQuestions[0])}>
                    <Compass size={17} weight="duotone" aria-hidden="true" />
                    <span>让 AI 规划复习</span>
                  </button>
                </div>

                <aside className="course-weakness-panel" role="region" aria-label="待复习弱点">
                  <div className="course-weakness-header">
                    <div>
                      <p className="course-answer-label">待复习弱点</p>
                      <h2>待复习弱点</h2>
                    </div>
                    <dl className="course-weakness-counts" aria-label="弱点统计">
                      <div>
                        <dt>待确认</dt>
                        <dd>{weaknessSummary?.pending_count ?? 0}</dd>
                      </div>
                      <div>
                        <dt>待复习</dt>
                        <dd>{weaknessSummary?.confirmed_count ?? 0}</dd>
                      </div>
                      <div>
                        <dt>复习中</dt>
                        <dd>{weaknessSummary?.reviewing_count ?? 0}</dd>
                      </div>
                      <div>
                        <dt>已完成</dt>
                        <dd>{weaknessSummary?.completed_count ?? 0}</dd>
                      </div>
                      <div>
                        <dt>候选证据</dt>
                        <dd>{weaknessSummary?.candidate_event_count ?? 0}</dd>
                      </div>
                    </dl>
                  </div>
                  <InlineFeedback
                    message={learningStateQuery.isError ? "课程学习状态读取失败，请稍后重试。" : null}
                    tone="warning"
                    className="course-inline-feedback"
                  />
                  <InlineFeedback
                    message={weaknessFeedback}
                    tone="warning"
                    className="course-inline-feedback"
                  />
                  {weaknessItems.length > 0 ? (
                    <ul className="course-weakness-list">
                      {weaknessItems.map((item) => (
                        <li key={item.id}>
                          <div className="course-weakness-main">
                            <span>{item.title}</span>
                            <em>{weaknessStatusLabel(item.status)}</em>
                          </div>
                          <div className="course-weakness-actions" aria-label={`${item.title} 操作`}>
                            {weaknessActionsForItem(item).map((action) => {
                              const Icon = action.icon;
                              const isUpdating = updatingWeaknessItemId === item.id;

                              return (
                                <button
                                  key={action.action}
                                  type="button"
                                  aria-label={`${action.label} ${item.title}`}
                                  disabled={updatingWeaknessItemId !== null}
                                  onClick={() => void updateWeaknessReviewItem(item, action.action)}
                                >
                                  <Icon size={14} weight="bold" aria-hidden="true" />
                                  <span>{isUpdating ? "更新中" : action.label}</span>
                                </button>
                              );
                            })}
                          </div>
                        </li>
                      ))}
                    </ul>
                  ) : learningStateQuery.isError ? null : (
                    <p className="course-weakness-empty">还没有待确认弱点</p>
                  )}
                </aside>

                {hasDisplayedCourseMessages ? (
                  <>
                    <section className="course-message-stack" aria-label="课程即时对话">
                      {displayedCourseMessages.map((message) => (
                        <article className={`course-message ${message.role}`} key={message.id}>
                          <p>{message.content}</p>
                        </article>
                      ))}
                    </section>
                    <article className="course-answer course-evidence-panel" aria-label="课程回答详情">
                      <div className="answer-action-row" aria-label="回答展开入口">
                        <button
                          className={activeAnswerPanel === "citations" ? "active" : ""}
                          type="button"
                          aria-pressed={activeAnswerPanel === "citations"}
                          onClick={() => setActiveAnswerPanel("citations")}
                        >
                          <FileText size={17} weight="duotone" aria-hidden="true" />
                          <span>来源</span>
                        </button>
                        <button
                          className={activeAnswerPanel === "resources" ? "active" : ""}
                          type="button"
                          aria-pressed={activeAnswerPanel === "resources"}
                          onClick={() => setActiveAnswerPanel("resources")}
                        >
                          <Sparkle size={17} weight="duotone" aria-hidden="true" />
                          <span>生成资源</span>
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
                          className={activeAnswerPanel === "thinking" ? "active" : ""}
                          type="button"
                          aria-pressed={activeAnswerPanel === "thinking"}
                          onClick={() => setActiveAnswerPanel("thinking")}
                        >
                          <Compass size={17} weight="duotone" aria-hidden="true" />
                          <span>思考过程</span>
                        </button>
                      </div>
                      <AnswerDetailPanel
                        activePanel={activeAnswerPanel}
                        courseId={hasRealCourseId ? numericCourseId : null}
                        citations={latestRagResults}
                        hasRealCourse={Boolean(apiCourse)}
                        hasSearched={hasRetrievalResult}
                        agentTraceId={latestAgentTraceId}
                        agentTraceEvents={agentTraceEvents}
                        isAgentTraceLoading={agentTraceQuery.isPending && agentTraceQuery.fetchStatus !== "idle"}
                        isAgentTraceError={agentTraceQuery.isError}
                        onOpenCitation={openCitationStudy}
                      />
                    </article>
                  </>
                ) : (
                  <article className="course-answer course-start-panel" role="region" aria-label="课程提问引导">
                    <p className="course-answer-label">开始提问</p>
                    <h2>问这门课</h2>
                    <p>我会先检索这门课的知识切片，再把回答、引用来源和下一步学习建议保存在课程历史里。</p>
                    <div className="course-question-suggestions" aria-label="推荐问题">
                      <span>推荐问题</span>
                      {courseStarterQuestions.map((question) => (
                        <button type="button" key={question} onClick={() => setCoursePrompt(question)}>
                          {question}
                        </button>
                      ))}
                    </div>
                  </article>
                )}

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

                <div className="course-composer" role="region" aria-label="课程输入区">
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
                  <InlineFeedback message={courseFeedback} tone="warning" className="course-inline-feedback" />
                </div>
              </section>
            ) : (
              <section className="course-study-layout" role="region" aria-label="课程学习模式">
                <article className="course-study-main" aria-label="学习内容">
                  <button className="course-back-link" type="button" onClick={() => setCourseMode("chat")}>
                    <ArrowLeft size={17} weight="bold" aria-hidden="true" />
                    <span>回到问答模式</span>
                  </button>
                  {selectedKnowledgePoint ? (
                    <>
                      <p className="course-answer-label">知识点</p>
                      <h2>{selectedKnowledgePoint.title}</h2>
                      <p>{selectedKnowledgePoint.summary ?? "这条知识点还没有摘要，可以在右侧直接追问。"}</p>
                      <dl className="course-study-meta" aria-label="知识点信息">
                        <div>
                          <dt>章节</dt>
                          <dd>{selectedKnowledgePoint.chapter ?? "课程知识点"}</dd>
                        </div>
                        <div>
                          <dt>难度</dt>
                          <dd>{selectedKnowledgePoint.difficulty ?? "未标注"}</dd>
                        </div>
                      </dl>
                    </>
                  ) : selectedCitation ? (
                    <>
                      <p className="course-answer-label">资料来源</p>
                      <h2>{selectedCitation.section_title ?? selectedCitation.source_title}</h2>
                      <p>{selectedCitation.content}</p>
                      <dl className="course-study-meta" aria-label="引用信息">
                        <div>
                          <dt>资料</dt>
                          <dd>{selectedCitation.source_title}</dd>
                        </div>
                        <div>
                          <dt>检索</dt>
                          <dd>
                            {retrievalSourceLabel(selectedCitation.retrieval_source)} · {embeddingStatusLabel(selectedCitation.embedding_status)}
                          </dd>
                        </div>
                      </dl>
                    </>
                  ) : (
                    <>
                      <p className="course-answer-label">学习模式</p>
                      <h2>选择知识点开始学习</h2>
                      <p>先选一个课程知识点，中间看内容，右侧继续追问。回答里的来源也可以带你进入同一个学习模式。</p>
                    </>
                  )}
                  {apiKnowledgePoints.length > 0 ? (
                    <div className="course-study-picker" aria-label="课程知识点">
                      <span>知识点</span>
                      {apiKnowledgePoints.map((point) => (
                        <button
                          className={selectedKnowledgePoint?.id === point.id ? "active" : ""}
                          type="button"
                          key={point.id}
                          aria-pressed={selectedKnowledgePoint?.id === point.id}
                          onClick={() => openKnowledgeStudy(point.id)}
                        >
                          {point.title}
                        </button>
                      ))}
                    </div>
                  ) : null}
                </article>

                <aside className="course-study-assistant" aria-label="AI 辅导">
                  <div className="course-panel-heading">
                    <span className="course-panel-icon" aria-hidden="true">
                      <ChatCircleText size={20} weight="duotone" />
                    </span>
                    <div>
                      <h2>AI 辅导</h2>
                      <p>围绕当前内容继续追问。</p>
                    </div>
                  </div>
                  <section className="course-study-mini-thread" aria-label="当前课程对话摘要">
                    {displayedCourseMessages.slice(-2).map((message) => (
                      <article className={`course-message ${message.role}`} key={message.id}>
                        <p>{message.content}</p>
                      </article>
                    ))}
                  </section>
                  <div className="course-composer compact" role="region" aria-label="课程输入区">
                    <label htmlFor="course-study-question-input">课程问题输入</label>
                    <textarea
                      id="course-study-question-input"
                      rows={3}
                      value={coursePrompt}
                      onChange={(event) => setCoursePrompt(event.target.value)}
                      onKeyDown={handleCourseComposerKeyDown}
                      placeholder="问这里为什么、换个例子，或让它出一道练习"
                    />
                    <button className="course-send-button" type="button" disabled={isSearchingCourse} onClick={() => void sendCourseQuestion()}>
                      <ArrowRight size={17} weight="bold" aria-hidden="true" />
                      <span>{isSearchingCourse ? "保存中" : "发送"}</span>
                    </button>
                    <InlineFeedback message={courseFeedback} tone="warning" className="course-inline-feedback" />
                  </div>
                </aside>
              </section>
            )}
          </div>
        </section>
      </section>
    </LearningSpaceShell>
  );
}

type AnswerDetailPanelProps = {
  activePanel: AnswerPanelKind;
  courseId: number | null;
  citations: RagSearchResultItem[];
  hasRealCourse: boolean;
  hasSearched: boolean;
  agentTraceId: string | null;
  agentTraceEvents: AgentTraceEvent[];
  isAgentTraceLoading: boolean;
  isAgentTraceError: boolean;
  onOpenCitation: (citation: RagSearchResultItem) => void;
};

function AnswerDetailPanel({
  activePanel,
  courseId,
  citations,
  hasRealCourse,
  hasSearched,
  agentTraceId,
  agentTraceEvents,
  isAgentTraceLoading,
  isAgentTraceError,
  onOpenCitation
}: AnswerDetailPanelProps) {
  if (activePanel === "resources") {
    const studioHref = courseId !== null ? `${PATHS.studio}?course_id=${courseId}` : PATHS.studio;

    return (
      <section className="answer-detail-panel" role="region" aria-label="回答展开详情">
        <strong>生成资源</strong>
        <p>资源工坊会基于当前课程和知识点生成讲解、练习、思维导图、代码实操和 PPT 大纲。</p>
        <Link to={studioHref}>进入资源工坊</Link>
      </section>
    );
  }

  if (activePanel === "path") {
    return (
      <section className="answer-detail-panel" role="region" aria-label="回答展开详情">
        <strong>建议路径</strong>
        <p>先围绕本次命中的来源复习核心概念，再追问一个例题，最后把仍不确定的知识点加入后续练习。</p>
      </section>
    );
  }

  if (activePanel === "thinking") {
    if (isAgentTraceError) {
      return (
        <section className="answer-detail-panel" role="region" aria-label="回答展开详情">
          <strong>思考过程</strong>
          <InlineFeedback message="Agent 轨迹读取失败，请稍后重试。" tone="warning" className="course-inline-feedback" />
        </section>
      );
    }

    if (isAgentTraceLoading) {
      return (
        <section className="answer-detail-panel" role="region" aria-label="回答展开详情">
          <strong>思考过程</strong>
          <p>正在读取 Agent 执行轨迹。</p>
        </section>
      );
    }

    if (agentTraceId && agentTraceEvents.length > 0) {
      return (
        <section className="answer-detail-panel" role="region" aria-label="回答展开详情">
          <strong>思考过程</strong>
          <AgentTimeline events={agentTraceEvents} />
        </section>
      );
    }

    return (
      <section className="answer-detail-panel" role="region" aria-label="回答展开详情">
        <strong>思考过程</strong>
        <p>
          {agentTraceId
            ? "当前 Agent trace 暂无可展示步骤。"
            : hasSearched
              ? `已完成课程资料检索，命中 ${citations.length} 条引用。暂未记录完整 Agent 轨迹。`
              : "发送课程问题后，会先检索当前课程资料，再决定是否调用模型回答。"}
        </p>
      </section>
    );
  }

  if (hasRealCourse) {
    if (!hasSearched) {
      return (
        <section className="answer-detail-panel" role="region" aria-label="回答展开详情">
          <strong>来源</strong>
          <p>发送课程问题后，会先从本课程知识切片中检索真实引用。</p>
        </section>
      );
    }

    if (citations.length === 0) {
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
                <span>匹配度 {citation.score.toFixed(1)}</span>
                <span>{retrievalSourceLabel(citation.retrieval_source)}</span>
                <span>{embeddingStatusLabel(citation.embedding_status)}</span>
              </small>
              <span className="citation-content">{citation.content}</span>
            </button>
          ))}
        </div>
      </section>
    );
  }

  return (
    <section className="answer-detail-panel" role="region" aria-label="回答展开详情">
      <strong>来源</strong>
      <p>请从课程列表进入真实课程后再查看引用来源。</p>
    </section>
  );
}

import {
  ArrowRight,
  BookOpen,
  ChatCircleText,
  CheckCircle,
  FileArrowUp,
  LinkSimple,
  MagnifyingGlass,
  Microphone,
  SpeakerHigh,
  Sparkle,
  X
} from "@phosphor-icons/react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { type ChangeEvent, type KeyboardEvent, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { PATHS, buildCoursePath } from "../app/routePaths";
import { getAgentTrace, mapAgentTraceStepToEvent } from "../api/agents";
import { createCourseFromMaterials } from "../api/courses";
import { getDashboardSummary, type DashboardMaterial } from "../api/dashboard";
import { getApiErrorMessage } from "../api/errors";
import { uploadMaterial } from "../api/materials";
import {
  createTutorSession,
  getTutorSession,
  sendTutorMessage,
  type TutorCitation,
  type TutorMessage,
  type TutorSessionSummary
} from "../api/tutor";
import { InlineFeedback, type FeedbackTone } from "../components/feedback/InlineFeedback";
import { AppSidebar } from "../components/layout/AppSidebar";
import { LearningSpaceShell } from "../components/layout/LearningSpaceShell";
import { useAuthStore } from "../features/auth/authStore";

type LibraryMaterial = DashboardMaterial;

type HomeMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  citation_json: TutorCitation[];
  trace_id: string | null;
};

type HomeAnswerPanel = "sources" | "path" | "thinking";

type SpeechRecognitionEventLike = {
  results: ArrayLike<ArrayLike<{ transcript: string }>>;
};

type SpeechRecognitionErrorEventLike = {
  error?: string;
};

type BrowserSpeechRecognition = {
  lang: string;
  interimResults: boolean;
  maxAlternatives: number;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onerror: ((event: SpeechRecognitionErrorEventLike) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
};

type BrowserSpeechRecognitionConstructor = new () => BrowserSpeechRecognition;

type SpeechWindow = Window &
  typeof globalThis & {
    SpeechRecognition?: BrowserSpeechRecognitionConstructor;
    webkitSpeechRecognition?: BrowserSpeechRecognitionConstructor;
  };

const fallbackSuggestedPrompts = ["帮我制定 7 天期末复习计划", "把反向传播讲到我能做题", "根据资料生成一门冲刺课"];

export function LearningSpacePage() {
  const token = useAuthStore((state) => state.token);
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const uploadInputRef = useRef<HTMLInputElement | null>(null);
  const homeChatStageRef = useRef<HTMLElement | null>(null);
  const recognitionRef = useRef<BrowserSpeechRecognition | null>(null);
  const [prompt, setPrompt] = useState("");
  const [messages, setMessages] = useState<HomeMessage[]>([]);
  const [localHomeThreads, setLocalHomeThreads] = useState<DashboardSummaryThread[]>([]);
  const [activeHomeThreadId, setActiveHomeThreadId] = useState<string | null>(null);
  const [isSendingQuestion, setIsSendingQuestion] = useState(false);
  const [isUploadingMaterial, setIsUploadingMaterial] = useState(false);
  const [selectedMaterialIds, setSelectedMaterialIds] = useState<string[]>([]);
  const [isHistoryCollapsed, setIsHistoryCollapsed] = useState(false);
  const [isCourseDialogOpen, setIsCourseDialogOpen] = useState(false);
  const [isCreatingCourse, setIsCreatingCourse] = useState(false);
  const [isLibraryOpen, setIsLibraryOpen] = useState(false);
  const [isDeepThinkingEnabled, setIsDeepThinkingEnabled] = useState(false);
  const [isWebSearchEnabled, setIsWebSearchEnabled] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [activeAnswerPanel, setActiveAnswerPanel] = useState<HomeAnswerPanel>("sources");
  const [expandedAnswerId, setExpandedAnswerId] = useState<string | null>(null);
  const [composerFeedback, setComposerFeedback] = useState<{ message: string; tone: FeedbackTone } | null>(null);
  const [courseDialogFeedback, setCourseDialogFeedback] = useState<{ message: string; tone: FeedbackTone } | null>(null);
  const hasHomeThread = messages.length > 0;
  const dashboardQuery = useQuery({
    queryKey: ["dashboard", "summary"],
    queryFn: getDashboardSummary,
    enabled: Boolean(token),
    staleTime: 30_000
  });
  const dashboardSummary = dashboardQuery.data?.data;
  const recentCourses = dashboardSummary?.recent_courses ?? [];
  const suggestedPrompts = dashboardSummary?.command_suggestions?.length ? dashboardSummary.command_suggestions : fallbackSuggestedPrompts;
  const emptyState = dashboardSummary?.empty_state;
  const summaryHomeThreads = useMemo(
    () => dashboardSummary?.recent_conversations.map(({ id, title, meta }) => ({ id, title, meta })) ?? [],
    [dashboardSummary?.recent_conversations]
  );
  const homeThreads = useMemo(() => {
    const localIds = new Set(localHomeThreads.map((thread) => thread.id));

    return [...localHomeThreads, ...summaryHomeThreads.filter((thread) => !localIds.has(thread.id))];
  }, [localHomeThreads, summaryHomeThreads]);
  const materials = useMemo(() => dashboardSummary?.recent_materials ?? [], [dashboardSummary?.recent_materials]);
  const effectiveSelectedMaterialIds = useMemo(
    () => selectedMaterialIds.filter((materialId) => materials.some((material) => material.id === materialId)),
    [materials, selectedMaterialIds]
  );

  useEffect(() => {
    if (!hasHomeThread) {
      return;
    }

    window.requestAnimationFrame(() => {
      const stage = homeChatStageRef.current;

      if (stage) {
        stage.scrollTop = stage.scrollHeight;
      }
    });
  }, [hasHomeThread, messages.length]);

  useEffect(() => {
    return () => {
      recognitionRef.current?.stop();
    };
  }, []);

  function openLibrary() {
    setIsLibraryOpen(true);
  }

  function openCourseGeneration() {
    setIsLibraryOpen(false);
    setIsCourseDialogOpen(true);
  }

  async function handleUploadFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];

    if (!file) {
      return;
    }

    setIsUploadingMaterial(true);

    try {
      await uploadMaterial({ file });
      await queryClient.invalidateQueries({ queryKey: ["dashboard", "summary"] });
      setComposerFeedback(null);
      event.target.value = "";
    } catch (error) {
      void error;
      setComposerFeedback({ message: "资料上传失败，请稍后再试。", tone: "warning" });
    } finally {
      setIsUploadingMaterial(false);
    }
  }

  function toggleMaterialSelection(materialId: string) {
    setSelectedMaterialIds((current) => {
      const next = current.includes(materialId) ? current.filter((id) => id !== materialId) : [...current, materialId];

      return next;
    });
  }

  function buildHomeSessionTitle(question: string) {
    return Array.from(question).slice(0, 30).join("");
  }

  function mapTutorMessages(apiMessages: TutorMessage[]) {
    return apiMessages.map((message) => ({
      id: message.id,
      role: message.role,
      content: message.content,
      citation_json: message.citation_json ?? [],
      trace_id: message.trace_id ?? null
    }));
  }

  function toHomeThread(session: TutorSessionSummary): DashboardSummaryThread {
    return {
      id: session.id,
      title: session.title,
      meta: "刚刚"
    };
  }

  function upsertHomeThread(session: TutorSessionSummary) {
    setLocalHomeThreads((current) => {
      const nextThread = toHomeThread(session);

      return [nextThread, ...current.filter((thread) => thread.id !== nextThread.id)];
    });
  }

  async function handleSendQuestion() {
    const question = prompt.trim();

    if (!question) {
      setComposerFeedback({ message: "先输入一个学习问题。", tone: "warning" });
      return;
    }

    if (isSendingQuestion) {
      return;
    }

    setIsSendingQuestion(true);
    setComposerFeedback(null);

    try {
      let sessionId = activeHomeThreadId;

      if (!sessionId) {
        const created = await createTutorSession({
          scope: "home",
          course_id: null,
          mode: "chat",
          title: buildHomeSessionTitle(question)
        });
        sessionId = created.data.id;
        setActiveHomeThreadId(sessionId);
      }

      const selectedMaterialIdsAsNumbers = effectiveSelectedMaterialIds
        .map((materialId) => Number.parseInt(materialId, 10))
        .filter((materialId) => Number.isFinite(materialId));
      const detail = await sendTutorMessage(sessionId, {
        message: question,
        use_web_search: isWebSearchEnabled,
        deep_thinking: isDeepThinkingEnabled,
        selected_material_ids: selectedMaterialIdsAsNumbers
      });

      setMessages(mapTutorMessages(detail.data.messages));
      setActiveHomeThreadId(detail.data.session.id);
      upsertHomeThread(detail.data.session);
      setPrompt("");
      void queryClient.invalidateQueries({ queryKey: ["dashboard", "summary"] });
    } catch (error) {
      void error;
      setComposerFeedback({ message: "消息发送失败，请稍后再试。", tone: "warning" });
    } finally {
      setIsSendingQuestion(false);
    }
  }

  function handleComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void handleSendQuestion();
    }
  }

  function getSpeechRecognitionConstructor() {
    if (typeof window === "undefined") {
      return null;
    }

    const speechWindow = window as SpeechWindow;
    return speechWindow.SpeechRecognition ?? speechWindow.webkitSpeechRecognition ?? null;
  }

  function handleVoiceInput() {
    if (isListening) {
      recognitionRef.current?.stop();
      setIsListening(false);
      return;
    }

    const SpeechRecognitionConstructor = getSpeechRecognitionConstructor();
    if (!SpeechRecognitionConstructor) {
      setComposerFeedback({ message: "当前浏览器不支持语音输入。", tone: "warning" });
      return;
    }

    const recognition = new SpeechRecognitionConstructor();
    recognition.lang = "zh-CN";
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;
    recognition.onresult = (event) => {
      const transcript = Array.from(event.results)
        .map((result) => result[0]?.transcript ?? "")
        .join("")
        .trim();

      if (transcript) {
        setPrompt((current) => (current.trim() ? `${current.trim()} ${transcript}` : transcript));
        setComposerFeedback({ message: "已识别语音输入。", tone: "success" });
      }
    };
    recognition.onerror = () => {
      setComposerFeedback({ message: "语音输入暂时不可用，请改用键盘输入。", tone: "warning" });
      setIsListening(false);
    };
    recognition.onend = () => {
      setIsListening(false);
    };
    recognitionRef.current = recognition;
    setComposerFeedback({ message: "正在聆听，请说出你的学习问题。", tone: "info" });
    setIsListening(true);
    recognition.start();
  }

  function handleSpeakMessage(content: string) {
    if (typeof window === "undefined" || !("speechSynthesis" in window) || typeof SpeechSynthesisUtterance === "undefined") {
      setComposerFeedback({ message: "当前浏览器不支持朗读回答。", tone: "warning" });
      return;
    }

    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(content);
    utterance.lang = "zh-CN";
    window.speechSynthesis.speak(utterance);
    setComposerFeedback({ message: "正在朗读回答。", tone: "info" });
  }

  async function selectHomeConversation(conversation: DashboardSummaryThread) {
    setActiveHomeThreadId(conversation.id);

    try {
      const detail = await getTutorSession(conversation.id);

      setMessages(mapTutorMessages(detail.data.messages));
      upsertHomeThread(detail.data.session);
    } catch (error) {
      void error;
      setComposerFeedback({ message: "历史对话读取失败，请稍后再试。", tone: "warning" });
    }
  }

  async function createCourseFromSelectedMaterials(courseTitle: string) {
    const selectedMaterialIdsAsNumbers = effectiveSelectedMaterialIds
      .map((materialId) => Number.parseInt(materialId, 10))
      .filter((materialId) => Number.isFinite(materialId));

    if (selectedMaterialIdsAsNumbers.length === 0) {
      setCourseDialogFeedback({ message: "请先选择至少一份资料。", tone: "warning" });
      return;
    }

    if (isCreatingCourse) {
      return;
    }

    setIsCreatingCourse(true);
    setCourseDialogFeedback(null);

    try {
      const created = await createCourseFromMaterials({
        material_ids: selectedMaterialIdsAsNumbers,
        course_title: courseTitle.trim()
      });

      await queryClient.invalidateQueries({ queryKey: ["dashboard", "summary"] });
      setIsCourseDialogOpen(false);
      setIsLibraryOpen(false);
      navigate(buildCoursePath(created.data.course.id));
    } catch (error) {
      setCourseDialogFeedback({
        message: getApiErrorMessage(error, "课程生成失败，请确认选择的是已解析资料。"),
        tone: "warning"
      });
    } finally {
      setIsCreatingCourse(false);
    }
  }

  return (
    <LearningSpaceShell hideTopNavigation>
      <div className={["learning-home", isHistoryCollapsed ? "history-collapsed" : "", hasHomeThread ? "chat-active" : ""].filter(Boolean).join(" ")}>
        <div className="learning-signal" aria-hidden="true">
          <span />
          <span />
          <span />
        </div>
        <AppSidebar
          isCollapsed={isHistoryCollapsed}
          conversations={homeThreads}
          activeConversationId={activeHomeThreadId}
          onToggleCollapsed={() => setIsHistoryCollapsed((collapsed) => !collapsed)}
          onNewChat={() => {
            setPrompt("");
            setMessages([]);
            setActiveHomeThreadId(null);
          }}
          onSelectConversation={(conversation) => void selectHomeConversation(conversation)}
        />

        <section
          ref={homeChatStageRef}
          className={hasHomeThread ? "home-chat-stage chat-active" : "home-chat-stage"}
          aria-label="AI 学习入口"
        >
          {hasHomeThread ? (
            <section className="home-thread-stage" aria-label="主页对话">
              {messages.map((message) => (
                <article className={`home-message ${message.role}`} key={message.id}>
                  {message.role === "assistant" ? <span className="message-thinking">已思考若干秒</span> : null}
                  <p>{message.content}</p>
                  {message.role === "assistant" ? (
                    <button className="message-speak-button" type="button" aria-label="朗读回答" onClick={() => handleSpeakMessage(message.content)}>
                      <SpeakerHigh size={15} weight="duotone" aria-hidden="true" />
                      <span>朗读</span>
                    </button>
                  ) : null}
                  {message.role === "assistant" ? (
                    <HomeAnswerInsights
                      message={message}
                      activePanel={activeAnswerPanel}
                      expandedAnswerId={expandedAnswerId}
                      selectedMaterialCount={effectiveSelectedMaterialIds.length}
                      isWebSearchEnabled={isWebSearchEnabled}
                      onChangePanel={setActiveAnswerPanel}
                      onSetExpandedAnswer={setExpandedAnswerId}
                    />
                  ) : null}
                </article>
              ))}
            </section>
          ) : (
            <div className="home-hero-copy">
              <p className="home-kicker">EduNova</p>
              <h1>
                <span>嗨，同学，</span>
                <span>准备好一起学习了吗？</span>
              </h1>
            </div>
          )}

          <section className={hasHomeThread ? "composer-frame docked" : "composer-frame"} aria-label={hasHomeThread ? "底部学习输入" : "学习输入区"}>
            <div className="conversation-composer">
              <textarea
                aria-label="学习问题输入"
                value={prompt}
                rows={2}
                onChange={(event) => setPrompt(event.target.value)}
                onKeyDown={handleComposerKeyDown}
                placeholder="问学习问题，或用资料生成课程"
              />
              <div className="composer-actions">
                <div className="composer-toolbar" aria-label="输入工具">
                  <input
                    ref={uploadInputRef}
                    className="visually-hidden"
                    type="file"
                    aria-label="上传资料文件"
                    accept=".pdf,.doc,.docx,.ppt,.pptx,.txt,.md,.png,.jpg,.jpeg"
                    onChange={(event) => void handleUploadFile(event)}
                  />
                  <button
                    type="button"
                    aria-label="上传资料"
                    disabled={isUploadingMaterial}
                    onClick={() => uploadInputRef.current?.click()}
                  >
                    <FileArrowUp size={18} weight="duotone" aria-hidden="true" />
                    <span>上传</span>
                  </button>
                  <button type="button" aria-label="打开资料库" onClick={() => openLibrary()}>
                    <BookOpen size={18} weight="duotone" aria-hidden="true" />
                    <span>资料库</span>
                  </button>
                  <button type="button" onClick={openCourseGeneration}>
                    <Sparkle size={18} weight="duotone" aria-hidden="true" />
                    <span>生成课程</span>
                  </button>
                  <button
                    className={isWebSearchEnabled ? "active" : ""}
                    type="button"
                    aria-label="联网搜索"
                    aria-pressed={isWebSearchEnabled}
                    onClick={() => {
                      setIsWebSearchEnabled((enabled) => !enabled);
                    }}
                  >
                    <MagnifyingGlass size={18} weight="duotone" aria-hidden="true" />
                    <span>搜索</span>
                  </button>
                  <button
                    className={isDeepThinkingEnabled ? "active" : ""}
                    type="button"
                    aria-label="深度思考"
                    aria-pressed={isDeepThinkingEnabled}
                    onClick={() => {
                      setIsDeepThinkingEnabled((enabled) => !enabled);
                    }}
                  >
                    <ChatCircleText size={18} weight="duotone" aria-hidden="true" />
                    <span>思考</span>
                  </button>
                </div>
                <div className="composer-submit-row">
                  <button
                    className={isListening ? "voice-button active" : "voice-button"}
                    type="button"
                    aria-label="语音输入"
                    aria-pressed={isListening}
                    onClick={handleVoiceInput}
                  >
                    <Microphone size={18} weight="duotone" aria-hidden="true" />
                  </button>
                  <button className="ask-button" type="button" disabled={isSendingQuestion} onClick={() => void handleSendQuestion()}>
                    <ArrowRight size={18} weight="bold" aria-hidden="true" />
                    <span>发送</span>
                  </button>
                </div>
              </div>
            </div>
            {effectiveSelectedMaterialIds.length > 0 ? (
              <div className="selected-materials-note">
                <LinkSimple size={16} weight="duotone" aria-hidden="true" />
                <span>{`已选择 ${effectiveSelectedMaterialIds.length} 份资料。`}</span>
              </div>
            ) : null}
            <InlineFeedback message={composerFeedback?.message ?? null} tone={composerFeedback?.tone} className="composer-inline-feedback" />
          </section>

          {!hasHomeThread ? (
            <div className="home-prompt-row" aria-label="快捷学习建议">
              {suggestedPrompts.map((suggestion) => (
                <button key={suggestion} type="button" onClick={() => setPrompt(suggestion)}>
                  {suggestion}
                </button>
              ))}
            </div>
          ) : null}

          {!hasHomeThread && dashboardQuery.isLoading ? (
            <section className="recent-course-strip empty" aria-label="最近学习">
              <strong>正在读取学习空间</strong>
              <p>我们正在加载你的课程、资料和主页历史。</p>
            </section>
          ) : null}
          {!hasHomeThread && !dashboardQuery.isLoading && dashboardQuery.isError ? (
            <section className="recent-course-strip empty" aria-label="最近学习">
              <strong>学习空间暂时没有读取成功</strong>
              <p>稍后刷新页面，或重新登录后再试。</p>
            </section>
          ) : null}
          {!hasHomeThread && !dashboardQuery.isLoading && !dashboardQuery.isError && recentCourses.length > 0 ? (
            <section className="recent-course-strip" aria-label="最近学习">
              <div className="recent-course-heading">
                <span>最近学习</span>
                <Link className="home-sprint-link" to={`${PATHS.path}?course_id=${recentCourses[0].id}`}>
                  <Sparkle size={15} weight="duotone" aria-hidden="true" />
                  <span>期末冲刺</span>
                </Link>
              </div>
              <ul className="recent-course-list" aria-label="最近学习列表">
                {recentCourses.map((course) => (
                  <li key={course.id}>
                    <Link className="recent-course" to={buildCoursePath(course.id)}>
                      <BookOpen size={18} weight="duotone" aria-hidden="true" />
                      <span>
                        <strong>{course.title}</strong>
                        <small>{course.focus}</small>
                      </span>
                      <em>{course.progress_label}</em>
                      <span className="course-next">{course.next}</span>
                    </Link>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}
          {!hasHomeThread && !dashboardQuery.isLoading && !dashboardQuery.isError && recentCourses.length === 0 ? (
            <section className="recent-course-strip empty" aria-label="最近学习">
              <strong>{emptyState?.title ?? "还没有课程"}</strong>
              <p>{emptyState?.description ?? "上传资料后可直接问，也可生成课程。"}</p>
            </section>
          ) : null}
        </section>
      </div>

      {isLibraryOpen ? (
        <MaterialLibraryDrawer
          materials={materials}
          selectedMaterialIds={effectiveSelectedMaterialIds}
          onToggleMaterial={toggleMaterialSelection}
          onOpenCourseGeneration={openCourseGeneration}
          onClose={() => setIsLibraryOpen(false)}
        />
      ) : null}
      {isCourseDialogOpen ? (
        <CourseGenerationDialog
          materials={materials}
          selectedMaterialIds={effectiveSelectedMaterialIds}
          onToggleMaterial={toggleMaterialSelection}
          onClose={() => setIsCourseDialogOpen(false)}
          onCreate={(courseTitle) => void createCourseFromSelectedMaterials(courseTitle)}
          isCreatingCourse={isCreatingCourse}
          feedback={courseDialogFeedback}
        />
      ) : null}
    </LearningSpaceShell>
  );
}

type DashboardSummaryThread = {
  id: string;
  title: string;
  meta: string;
};

type HomeAnswerInsightsProps = {
  message: HomeMessage;
  activePanel: HomeAnswerPanel;
  expandedAnswerId: string | null;
  selectedMaterialCount: number;
  isWebSearchEnabled: boolean;
  onChangePanel: (panel: HomeAnswerPanel) => void;
  onSetExpandedAnswer: (messageId: string | null) => void;
};

function HomeAnswerInsights({
  message,
  activePanel,
  expandedAnswerId,
  selectedMaterialCount,
  isWebSearchEnabled,
  onChangePanel,
  onSetExpandedAnswer
}: HomeAnswerInsightsProps) {
  const messageId = message.id;
  const isExpanded = expandedAnswerId === messageId;
  const traceQuery = useQuery({
    queryKey: ["agents", "trace", message.trace_id],
    queryFn: () => getAgentTrace(message.trace_id ?? ""),
    enabled: Boolean(message.trace_id) && isExpanded && activePanel === "thinking",
    staleTime: 10_000
  });
  const traceEvents = useMemo(
    () => traceQuery.data?.data.steps.map(mapAgentTraceStepToEvent) ?? [],
    [traceQuery.data?.data.steps]
  );
  const handleInsightClick = (panel: HomeAnswerPanel) => {
    const shouldCollapse = isExpanded && activePanel === panel;

    onChangePanel(panel);
    onSetExpandedAnswer(shouldCollapse ? null : messageId);
  };
  const citations = message.citation_json ?? [];
  const hasCitations = citations.length > 0;
  const sourceText =
    hasCitations
      ? `本次回答返回 ${citations.length} 条真实来源。`
      : selectedMaterialCount > 0
        ? `本次回答请求了 ${selectedMaterialCount} 份已选资料${isWebSearchEnabled ? "和联网搜索" : ""}，但没有返回可展示来源。`
        : isWebSearchEnabled
          ? "联网搜索已请求，但没有返回可展示网页来源。"
          : "本次回答没有绑定资料或网页来源。";

  return (
    <section className="home-answer-insights" aria-label="回答附加信息">
      <div className="answer-insight-tabs" aria-label="回答展开入口">
        <button
          className={isExpanded && activePanel === "sources" ? "active" : ""}
          type="button"
          aria-expanded={isExpanded && activePanel === "sources"}
          aria-pressed={isExpanded && activePanel === "sources"}
          onClick={() => handleInsightClick("sources")}
        >
          <LinkSimple size={16} weight="duotone" aria-hidden="true" />
          <span>来源</span>
        </button>
        <button
          className={isExpanded && activePanel === "path" ? "active" : ""}
          type="button"
          aria-expanded={isExpanded && activePanel === "path"}
          aria-pressed={isExpanded && activePanel === "path"}
          onClick={() => handleInsightClick("path")}
        >
          <BookOpen size={16} weight="duotone" aria-hidden="true" />
          <span>学习路径</span>
        </button>
        <button
          className={isExpanded && activePanel === "thinking" ? "active" : ""}
          type="button"
          aria-expanded={isExpanded && activePanel === "thinking"}
          aria-pressed={isExpanded && activePanel === "thinking"}
          onClick={() => handleInsightClick("thinking")}
        >
          <Sparkle size={16} weight="duotone" aria-hidden="true" />
          <span>思考过程</span>
        </button>
      </div>

      {isExpanded ? (
        <div className="answer-insight-panel" role="region" aria-label="回答展开详情">
          {activePanel === "sources" ? (
            <>
              <span className="insight-mark">
                <CheckCircle size={16} weight="fill" aria-hidden="true" />
                来源
              </span>
              <p>{sourceText}</p>
              {hasCitations ? (
                <ul className="insight-source-list">
                  {citations.map((citation, index) => (
                    <li key={`${citation.source_type ?? "source"}-${citation.url ?? citation.source_title ?? citation.title ?? index}`}>
                      <div>
                        <strong>{citation.title ?? citation.source_title ?? `来源 ${index + 1}`}</strong>
                        <span>{sourceTypeLabel(citation.source_type)}</span>
                      </div>
                      {citation.snippet || citation.content ? <p>{citation.snippet ?? citation.content}</p> : null}
                      {citation.url ? (
                        <a href={citation.url} target="_blank" rel="noreferrer">
                          {citation.url}
                        </a>
                      ) : null}
                    </li>
                  ))}
                </ul>
              ) : null}
            </>
          ) : null}
          {activePanel === "path" ? (
            <>
              <span className="insight-mark">
                <BookOpen size={16} weight="fill" aria-hidden="true" />
                下一步
              </span>
              <p>先用 10 分钟补概念，再做 3 道同类题，最后把错因写回画像和复习队列。</p>
            </>
          ) : null}
          {activePanel === "thinking" ? (
            <>
              <span className="insight-mark">
                <Sparkle size={16} weight="fill" aria-hidden="true" />
                课堂协作轨迹
              </span>
              {message.trace_id ? <p>{`Trace ${message.trace_id}`}</p> : <p>当前回答没有返回可追踪 Agent 记录。</p>}
              {traceQuery.isLoading ? <p>正在读取协作轨迹。</p> : null}
              {traceQuery.isError ? <p>Agent 轨迹读取失败，请稍后重试。</p> : null}
              {traceEvents.length > 0 ? (
                <ol className="insight-trace-list">
                  {traceEvents.map((event) => (
                    <li key={event.id}>
                      <strong>{event.agentName}</strong>
                      <span>{event.summary}</span>
                    </li>
                  ))}
                </ol>
              ) : null}
            </>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

function sourceTypeLabel(sourceType: TutorCitation["source_type"]) {
  if (sourceType === "web") {
    return "网页";
  }
  if (sourceType === "material") {
    return "资料";
  }
  if (sourceType === "course") {
    return "课程";
  }
  return "来源";
}

type CourseGenerationDialogProps = {
  onClose: () => void;
};

type CourseGenerationDialogWithNoticeProps = CourseGenerationDialogProps & {
  materials: LibraryMaterial[];
  selectedMaterialIds: string[];
  onToggleMaterial: (materialId: string) => void;
  onCreate: (courseTitle: string) => void;
  isCreatingCourse: boolean;
  feedback: { message: string; tone: FeedbackTone } | null;
};

function CourseGenerationDialog({
  materials,
  selectedMaterialIds,
  onToggleMaterial,
  onClose,
  onCreate,
  isCreatingCourse,
  feedback
}: CourseGenerationDialogWithNoticeProps) {
  const selectedCount = selectedMaterialIds.length;
  const [courseTitle, setCourseTitle] = useState("人工智能导论期末复习");

  return (
    <div className="course-dialog-backdrop">
      <section className="course-dialog" role="dialog" aria-modal="true" aria-labelledby="course-dialog-title">
        <button className="course-dialog-close" type="button" aria-label="关闭生成课程" onClick={onClose}>
          <X size={18} aria-hidden="true" />
        </button>
        <div className="dialog-copy">
          <h2 id="course-dialog-title">从资料生成课程</h2>
        </div>
        <label className="dialog-field">
          <span>课程名称</span>
          <input aria-label="课程名称" value={courseTitle} onChange={(event) => setCourseTitle(event.target.value)} />
        </label>
        <MaterialFileList materials={materials} selectedMaterialIds={selectedMaterialIds} onToggleMaterial={onToggleMaterial} />
        <div className="dialog-selection-summary">
          <strong>{selectedCount > 0 ? `已选择 ${selectedCount} 份资料` : "先选择要生成课程的资料"}</strong>
          <small>只建立关联，不移动原文件。</small>
        </div>
        <InlineFeedback message={feedback?.message ?? null} tone={feedback?.tone} className="dialog-inline-feedback" />
        <button
          className={selectedCount > 0 ? "dialog-primary-button" : "dialog-primary-button disabled"}
          type="button"
          disabled={selectedCount === 0 || isCreatingCourse}
          onClick={() => onCreate(courseTitle)}
        >
          {isCreatingCourse ? "生成中" : "生成课程"}
        </button>
      </section>
    </div>
  );
}

type MaterialLibraryDrawerProps = CourseGenerationDialogProps & {
  materials: LibraryMaterial[];
  selectedMaterialIds: string[];
  onToggleMaterial: (materialId: string) => void;
  onOpenCourseGeneration: () => void;
};

function MaterialLibraryDrawer({ materials, selectedMaterialIds, onToggleMaterial, onOpenCourseGeneration, onClose }: MaterialLibraryDrawerProps) {
  const selectedCount = selectedMaterialIds.length;
  const [searchTerm, setSearchTerm] = useState("");
  const visibleMaterials = useMemo(() => {
    const normalizedSearch = searchTerm.trim().toLowerCase();

    if (!normalizedSearch) {
      return materials;
    }

    return materials.filter((material) =>
      `${material.title} ${material.type} ${material.detail}`.toLowerCase().includes(normalizedSearch)
    );
  }, [materials, searchTerm]);

  return (
    <div className="course-dialog-backdrop">
      <section className="material-drawer" role="dialog" aria-modal="true" aria-labelledby="library-dialog-title">
        <button className="course-dialog-close" type="button" aria-label="关闭资料库" onClick={onClose}>
          <X size={18} aria-hidden="true" />
        </button>
        <div className="dialog-copy">
          <h2 id="library-dialog-title">资料库</h2>
        </div>
        <div className="file-library-toolbar">
          <label className="file-search-field">
            <MagnifyingGlass size={17} weight="duotone" aria-hidden="true" />
            <input aria-label="搜索资料" placeholder="搜索资料" value={searchTerm} onChange={(event) => setSearchTerm(event.target.value)} />
          </label>
          <button type="button" onClick={onOpenCourseGeneration}>
            <Sparkle size={17} weight="duotone" aria-hidden="true" />
            <span>生成课程</span>
          </button>
        </div>
        <MaterialFileList
          materials={visibleMaterials}
          selectedMaterialIds={selectedMaterialIds}
          onToggleMaterial={onToggleMaterial}
          emptyText={materials.length === 0 ? undefined : "没有匹配的资料。"}
        />
        <div className="library-dialog-footer">
          <span>{selectedCount > 0 ? `已选择 ${selectedCount} 份资料` : "当前未选择资料"}</span>
          <button
            className={selectedCount > 0 ? "dialog-primary-button" : "dialog-primary-button secondary disabled"}
            type="button"
            disabled={selectedCount === 0}
            onClick={onClose}
          >
            作为本次对话参考
          </button>
        </div>
      </section>
    </div>
  );
}

type MaterialFileListProps = {
  materials: LibraryMaterial[];
  selectedMaterialIds: string[];
  onToggleMaterial: (materialId: string) => void;
  emptyText?: string;
};

function MaterialFileList({ materials, selectedMaterialIds, onToggleMaterial, emptyText = "资料库还是空的，先上传一份课件或试卷。" }: MaterialFileListProps) {
  return (
    <div className="material-file-list" role="list" aria-label="资料库文件列表">
      <div className="material-file-header" aria-hidden="true">
        <span>名称</span>
        <span>修改时间</span>
        <span>大小</span>
      </div>
      {materials.length === 0 ? <p className="material-file-empty">{emptyText}</p> : null}
      {materials.map((material) => {
        const isSelected = selectedMaterialIds.includes(material.id);

        return (
          <button
            className={isSelected ? "material-file-row selected" : "material-file-row"}
            key={material.id}
            type="button"
            aria-pressed={isSelected}
            onClick={() => onToggleMaterial(material.id)}
          >
            <span className="material-file-type">{material.type}</span>
            <span className="material-file-main">
              <strong>{material.title}</strong>
              <small>{material.detail}</small>
            </span>
            <span className="material-file-meta">{material.modified}</span>
            <span className="material-file-meta">{material.size}</span>
            {isSelected ? <CheckCircle size={18} weight="duotone" aria-hidden="true" /> : null}
          </button>
        );
      })}
    </div>
  );
}

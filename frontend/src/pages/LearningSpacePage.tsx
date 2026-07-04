import {
  ArrowRight,
  BookOpen,
  ChatCircleText,
  CheckCircle,
  FileArrowUp,
  LinkSimple,
  MagnifyingGlass,
  Microphone,
  Sparkle,
  X
} from "@phosphor-icons/react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { type ChangeEvent, type KeyboardEvent, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { buildCoursePath } from "../app/routePaths";
import { createCourseFromMaterials } from "../api/courses";
import { getDashboardSummary, type DashboardMaterial } from "../api/dashboard";
import { getApiErrorMessage } from "../api/errors";
import { uploadMaterial } from "../api/materials";
import {
  createTutorSession,
  getTutorSession,
  sendTutorMessage,
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
};

type HomeAnswerPanel = "sources" | "path" | "thinking";

const fallbackSuggestedPrompts = ["帮我制定 7 天期末复习计划", "把反向传播讲到我能做题", "根据资料生成一门冲刺课"];

export function LearningSpacePage() {
  const token = useAuthStore((state) => state.token);
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const uploadInputRef = useRef<HTMLInputElement | null>(null);
  const homeChatStageRef = useRef<HTMLElement | null>(null);
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
      content: message.content
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

      const detail = await sendTutorMessage(sessionId, { message: question });

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
        message: getApiErrorMessage(error, "课程生成失败，请确认选择的是已解析的 TXT 或 Markdown 资料。"),
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
                    <HomeAnswerInsights
                      messageId={message.id}
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
                  <button className="voice-button" type="button" aria-label="语音输入">
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
                <button type="button">
                  查看全部
                </button>
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
  messageId: string;
  activePanel: HomeAnswerPanel;
  expandedAnswerId: string | null;
  selectedMaterialCount: number;
  isWebSearchEnabled: boolean;
  onChangePanel: (panel: HomeAnswerPanel) => void;
  onSetExpandedAnswer: (messageId: string | null) => void;
};

function HomeAnswerInsights({
  messageId,
  activePanel,
  expandedAnswerId,
  selectedMaterialCount,
  isWebSearchEnabled,
  onChangePanel,
  onSetExpandedAnswer
}: HomeAnswerInsightsProps) {
  const isExpanded = expandedAnswerId === messageId;
  const handleInsightClick = (panel: HomeAnswerPanel) => {
    const shouldCollapse = isExpanded && activePanel === panel;

    onChangePanel(panel);
    onSetExpandedAnswer(shouldCollapse ? null : messageId);
  };
  const sourceText =
    selectedMaterialCount > 0
      ? `本次回答参考了 ${selectedMaterialCount} 份已选资料${isWebSearchEnabled ? "，并补充联网搜索线索" : ""}。`
      : isWebSearchEnabled
        ? "本次回答会优先显示联网来源，资料库内容未被选入。"
        : "未选择资料时，回答先使用通用学习策略；选择资料后会显示更具体的引用。";

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
                处理摘要
              </span>
              <p>已按“目标识别、资料线索、复习动作”整理，真实 Agent 接入后会替换为可追踪执行记录。</p>
            </>
          ) : null}
        </div>
      ) : null}
    </section>
  );
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

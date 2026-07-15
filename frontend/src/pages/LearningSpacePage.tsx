import {
  ArrowRight,
  BookOpen,
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
import { type ChangeEvent, type KeyboardEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { buildCoursePath, PATHS } from "../app/routePaths";
import { getAgentTrace, mapAgentTraceStepToEvent } from "../api/agents";
import { createCourseBuilderJob, createIdempotencyKey, getAiJob, type AiJob } from "../api/aiJobs";
import { getDashboardSummary } from "../api/dashboard";
import { getApiErrorMessage } from "../api/errors";
import { listMaterials, uploadMaterial } from "../api/materials";
import {
  createTutorSession,
  deleteTutorSession,
  getTutorSession,
  renameTutorSession,
  streamTutorMessage,
  type TutorCitation,
  type TutorMessage,
  type TutorSessionSummary
} from "../api/tutor";
import { InlineFeedback, type FeedbackTone } from "../components/feedback/InlineFeedback";
import { AiJobProgress } from "../components/feedback/AiJobProgress";
import { ModalFrame } from "../components/primitives/Dialog";
import { MarkdownMessage } from "../components/feedback/MarkdownMessage";
import { HomeCourseDrawer } from "../components/home/HomeCourseDrawer";
import { AppSidebar } from "../components/layout/AppSidebar";
import { LearningSpaceShell } from "../components/layout/LearningSpaceShell";
import { isCompactWorkspaceViewport, useResponsiveSidebarState } from "../components/layout/useResponsiveSidebarState";
import { useAuthStore } from "../features/auth/authStore";
import { useAiJobs } from "../features/aiJobs/AiJobProvider";
import { useHomeConversationHistory } from "../features/home/useHomeConversationHistory";

type LibraryMaterial = {
  id: string;
  title: string;
  type: string;
  detail: string;
  modified: string;
  size: string;
  ingestion_status?: "legacy" | "pending" | "running" | "awaiting_confirmation" | "confirmed" | "failed";
};

type HomeMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  citation_json: TutorCitation[];
  trace_id: string | null;
  streaming?: boolean;
};

type LearningSpaceNavigationState = {
  selectedHomeThreadId?: string;
  selectedMaterialIds?: string[];
};

type DashboardSummaryResponse = Awaited<ReturnType<typeof getDashboardSummary>>;

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

function mapTutorMessages(apiMessages: TutorMessage[]) {
  return apiMessages.map((message) => ({
    id: message.id,
    role: message.role,
    content: message.role === "assistant" ? sanitizeHomeAnswerContent(message.content) : message.content,
    citation_json: message.citation_json ?? [],
    trace_id: message.trace_id ?? null
  }));
}

function sanitizeHomeAnswerContent(content: string) {
  const normalized = content.trim();
  const internalMarkers = ["学生问题：", "工具状态：", "可用来源摘要：", "工具提示："];
  if (!internalMarkers.some((marker) => normalized.includes(marker))) {
    return normalized;
  }

  const finalBoundary = normalized.match(/(?:最终回答|给学生的回答|以下是针对学生[^：:]*的[^：:]*回答)[：:]\s*([\s\S]+)/);
  if (finalBoundary?.[1]?.trim()) {
    return finalBoundary[1].trim();
  }

  return "这条历史回答包含旧版内部处理信息，已停止展示。请重新提问以获得正常回答。";
}

export function LearningSpacePage() {
  const token = useAuthStore((state) => state.token);
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const location = useLocation();
  const navigationState = location.state as LearningSpaceNavigationState | null;
  const selectedHomeThreadIdFromNavigation = typeof navigationState?.selectedHomeThreadId === "string"
    ? navigationState.selectedHomeThreadId
    : new URLSearchParams(location.search).get("session_id");
  const selectedMaterialIdsFromNavigation = Array.isArray(navigationState?.selectedMaterialIds)
    ? navigationState.selectedMaterialIds.filter((materialId): materialId is string => typeof materialId === "string")
    : [];
  const uploadInputRef = useRef<HTMLInputElement | null>(null);
  const homeChatStageRef = useRef<HTMLElement | null>(null);
  const recognitionRef = useRef<BrowserSpeechRecognition | null>(null);
  const isResettingHomeRef = useRef(false);
  const [prompt, setPrompt] = useState("");
  const [messages, setMessages] = useState<HomeMessage[]>([]);
  const [localHomeThreads, setLocalHomeThreads] = useState<DashboardSummaryThread[]>([]);
  const [historySearch, setHistorySearch] = useState("");
  const [activeHomeThreadId, setActiveHomeThreadId] = useState<string | null>(() => selectedHomeThreadIdFromNavigation);
  const [isSendingQuestion, setIsSendingQuestion] = useState(false);
  const [isUploadingMaterial, setIsUploadingMaterial] = useState(false);
  const [conversationMaterialIds, setConversationMaterialIds] = useState<string[]>([]);
  const [materialDraftIds, setMaterialDraftIds] = useState<string[]>(() => selectedMaterialIdsFromNavigation);
  const [courseMaterialIds, setCourseMaterialIds] = useState<string[]>([]);
  const [isHistoryCollapsed, setIsHistoryCollapsed] = useResponsiveSidebarState();
  const [isCourseDialogOpen, setIsCourseDialogOpen] = useState(false);
  const [courseJobId, setCourseJobId] = useState<string | null>(null);
  const [isLibraryOpen, setIsLibraryOpen] = useState(() => selectedMaterialIdsFromNavigation.length > 0);
  const [isListening, setIsListening] = useState(false);
  const [activeAnswerPanel, setActiveAnswerPanel] = useState<HomeAnswerPanel>("sources");
  const [expandedAnswerId, setExpandedAnswerId] = useState<string | null>(null);
  const [streamingAnswerId, setStreamingAnswerId] = useState<string | null>(null);
  const [graphStatus, setGraphStatus] = useState<string | null>(null);
  const [answerWarnings, setAnswerWarnings] = useState<Record<string, string[]>>({});
  const [composerFeedback, setComposerFeedback] = useState<{ message: string; tone: FeedbackTone } | null>(null);
  const [courseDialogFeedback, setCourseDialogFeedback] = useState<{ message: string; tone: FeedbackTone } | null>(null);
  const [materialDialogFeedback, setMaterialDialogFeedback] = useState<{ message: string; tone: FeedbackTone } | null>(null);
  const [isCourseDrawerOpen, setIsCourseDrawerOpen] = useState(false);
  const { jobs, trackJob, getJob, cancelJob, retryJob } = useAiJobs();
  const courseJob = getJob(courseJobId);
  const isCreatingCourse = Boolean(courseJob && ["queued", "running", "cancelling"].includes(courseJob.status));
  const hasHomeThread = messages.length > 0;
  const dashboardQuery = useQuery({
    queryKey: ["dashboard", "summary"],
    queryFn: getDashboardSummary,
    enabled: Boolean(token),
    staleTime: 30_000
  });
  const dashboardSummary = dashboardQuery.data?.data;
  const historyQuery = useHomeConversationHistory("", Boolean(token));
  const historySearchQuery = useHomeConversationHistory(historySearch, Boolean(token && historySearch));
  const allMaterialsQuery = useQuery({
    queryKey: ["materials", "list"],
    queryFn: () => listMaterials(),
    enabled: Boolean(token),
    staleTime: 30_000
  });
  const recentCourses = dashboardSummary?.recent_courses ?? [];
  const emptyState = dashboardSummary?.empty_state;
  const learnerName = dashboardSummary?.profile_summary.display_name.trim() || "同学";
  const historyHomeThreads = useMemo(
    () => (historyQuery.data?.pages ?? []).flatMap((page) => (page.data?.items ?? []).map(({ id, title, updated_at }) => ({ id, title, meta: updated_at.slice(0, 10) }))),
    [historyQuery.data?.pages]
  );
  const fallbackHomeThreads = useMemo(
    () => dashboardSummary?.recent_conversations.map(({ id, title, meta }) => ({ id, title, meta })) ?? [],
    [dashboardSummary?.recent_conversations]
  );
  const homeThreads = useMemo(() => {
    const localIds = new Set(localHomeThreads.map((thread) => thread.id));
    const serverThreads = historyHomeThreads.length > 0 ? historyHomeThreads : fallbackHomeThreads;

    return [...localHomeThreads, ...serverThreads.filter((thread) => !localIds.has(thread.id))];
  }, [fallbackHomeThreads, historyHomeThreads, localHomeThreads]);
  const historySearchThreads = useMemo(
    () => (historySearchQuery.data?.pages ?? []).flatMap((page) => (page.data?.items ?? []).map(({ id, title, match_snippet }) => ({ id, title, meta: match_snippet || "历史会话" }))),
    [historySearchQuery.data?.pages]
  );
  const materials = useMemo<LibraryMaterial[]>(() => {
    const allMaterials = allMaterialsQuery.data?.data;
    if (allMaterialsQuery.isSuccess && Array.isArray(allMaterials)) {
      return allMaterials;
    }
    return dashboardSummary?.recent_materials ?? [];
  }, [allMaterialsQuery.data?.data, allMaterialsQuery.isSuccess, dashboardSummary?.recent_materials]);
  const effectiveConversationMaterialIds = useMemo(
    () => conversationMaterialIds.filter((materialId) => materials.some((material) => material.id === materialId)),
    [conversationMaterialIds, materials]
  );

  useEffect(() => {
    if (courseJobId) return;
    const restored = jobs.find((job) => job.workflow === "course_builder" && ["queued", "running", "cancelling", "failed"].includes(job.status));
    if (!restored) return;
    const materialIds = Array.isArray(restored.request.material_ids) ? restored.request.material_ids.map(String) : [];
    // Restore durable server state after navigation or refresh.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setCourseMaterialIds(materialIds);
    setCourseJobId(restored.job_id);
    setIsLibraryOpen(false);
    setIsCourseDialogOpen(true);
  }, [courseJobId, jobs]);

  useEffect(() => {
    if (!courseJob) return;
    if (courseJob.status === "failed") {
      // Surface the terminal state delivered by the external job runtime.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setCourseDialogFeedback({ message: courseJob.error_message ?? "课程生成失败，请稍后重试。", tone: "warning" });
      return;
    }
    const courseId = courseJob.result.course_id;
    if (courseJob.status === "completed" && (typeof courseId === "string" || typeof courseId === "number")) {
      setCourseJobId(null);
      setIsCourseDialogOpen(false);
      setIsLibraryOpen(false);
      void queryClient.invalidateQueries({ queryKey: ["dashboard", "summary"] });
      navigate(buildCoursePath(String(courseId)));
    }
  }, [courseJob, navigate, queryClient]);

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
    setMaterialDraftIds(effectiveConversationMaterialIds);
    setMaterialDialogFeedback(null);
    setIsLibraryOpen(true);
  }

  function openCourseGeneration() {
    setCourseMaterialIds(effectiveConversationMaterialIds);
    setIsLibraryOpen(false);
    setIsCourseDialogOpen(true);
  }

  function openCourseGenerationFromLibrary() {
    setCourseMaterialIds(materialDraftIds);
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
      const response = await uploadMaterial({ file });
      if (response.data.ingestion_job_id) {
        trackJob(await getAiJob(response.data.ingestion_job_id));
      }
      await queryClient.invalidateQueries({ queryKey: ["dashboard", "summary"] });
      setComposerFeedback({ message: "资料已上传，正在后台识别目录和正文切片。完成后可到资料库检查并确认。", tone: "success" });
      event.target.value = "";
    } catch (error) {
      void error;
      setComposerFeedback({ message: "资料上传失败，请稍后再试。", tone: "warning" });
    } finally {
      setIsUploadingMaterial(false);
    }
  }

  function toggleMaterialDraft(materialId: string) {
    setMaterialDraftIds((current) => {
      if (!current.includes(materialId) && current.length >= 10) {
        setMaterialDialogFeedback({ message: "单个会话最多选择 10 份参考资料。", tone: "warning" });
        return current;
      }
      const next = current.includes(materialId) ? current.filter((id) => id !== materialId) : [...current, materialId];
      setMaterialDialogFeedback(null);
      return next;
    });
  }

  function toggleCourseMaterial(materialId: string) {
    setCourseMaterialIds((current) =>
      current.includes(materialId) ? current.filter((id) => id !== materialId) : [...current, materialId]
    );
  }

  async function confirmConversationMaterials() {
    const materialIds = materialDraftIds.filter((materialId) => materials.some((material) => material.id === materialId));
    if (activeHomeThreadId) {
      try {
        await renameTutorSession(activeHomeThreadId, { selected_material_ids: materialIds.map(Number) });
      } catch {
        setMaterialDialogFeedback({ message: "参考资料保存失败，请稍后重试。", tone: "warning" });
        return;
      }
    }
    setConversationMaterialIds(materialIds);
    setMaterialDialogFeedback(null);
    setIsLibraryOpen(false);
    void queryClient.invalidateQueries({ queryKey: ["tutor", "home-history"] });
  }

  function buildHomeSessionTitle(question: string) {
    return Array.from(question).slice(0, 30).join("");
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
    void queryClient.invalidateQueries({ queryKey: ["tutor", "home-history"] });
  }

  function updateDashboardHomeThreads(
    updater: (threads: DashboardSummaryResponse["data"]["recent_conversations"]) => DashboardSummaryResponse["data"]["recent_conversations"]
  ) {
    queryClient.setQueryData<DashboardSummaryResponse>(["dashboard", "summary"], (current) =>
      current
        ? {
            ...current,
            data: {
              ...current.data,
              recent_conversations: updater(current.data.recent_conversations)
            }
          }
        : current
    );
  }

  function renameCachedHomeThread(sessionId: string, title: string) {
    setLocalHomeThreads((current) =>
      current.map((thread) => (thread.id === sessionId ? { ...thread, title } : thread))
    );
    updateDashboardHomeThreads((threads) =>
      threads.map((thread) => (thread.id === sessionId ? { ...thread, title } : thread))
    );
  }

  async function renameHomeConversation(conversation: DashboardSummaryThread, title: string) {
    const normalizedTitle = title.trim();
    if (!normalizedTitle) {
      return;
    }

    try {
      const renamed = await renameTutorSession(conversation.id, { title: normalizedTitle });

      renameCachedHomeThread(conversation.id, renamed.data.title);
      setComposerFeedback(null);
      void queryClient.invalidateQueries({ queryKey: ["dashboard", "summary"] });
      void queryClient.invalidateQueries({ queryKey: ["tutor", "home-history"] });
    } catch {
      setComposerFeedback({ message: "会话改名失败，请稍后再试。", tone: "warning" });
    }
  }

  async function deleteHomeConversation(conversation: DashboardSummaryThread) {
    try {
      await deleteTutorSession(conversation.id);
      setLocalHomeThreads((current) => current.filter((thread) => thread.id !== conversation.id));
      updateDashboardHomeThreads((threads) => threads.filter((thread) => thread.id !== conversation.id));

      if (activeHomeThreadId === conversation.id) {
        resetHomeEntry();
      }

      void queryClient.invalidateQueries({ queryKey: ["dashboard", "summary"] });
      void queryClient.invalidateQueries({ queryKey: ["tutor", "home-history"] });
    } catch {
      setComposerFeedback({ message: "会话删除失败，请稍后再试。", tone: "warning" });
    }
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
    const messagesBeforeSend = messages;
    let optimisticAssistantId: string | null = null;
    let streamWarnings: string[] = [];

    try {
      let sessionId = activeHomeThreadId;

      if (!sessionId) {
        const created = await createTutorSession({
          scope: "home",
          course_id: null,
          mode: "chat",
          title: buildHomeSessionTitle(question),
          selected_material_ids: effectiveConversationMaterialIds.map(Number)
        });
        sessionId = created.data.id;
        setActiveHomeThreadId(sessionId);
      }

      const optimisticKey = `${Date.now()}-${sessionId}`;
      const optimisticUserId = `stream-user-${optimisticKey}`;
      optimisticAssistantId = `stream-assistant-${optimisticKey}`;
      setStreamingAnswerId(optimisticAssistantId);
      setGraphStatus("正在读取会话上下文");
      setMessages([
        ...messagesBeforeSend,
        {
          id: optimisticUserId,
          role: "user",
          content: question,
          citation_json: [],
          trace_id: null
        },
        {
          id: optimisticAssistantId,
          role: "assistant",
          content: "",
          citation_json: [],
          trace_id: null,
          streaming: true
        }
      ]);

      const detail = await streamTutorMessage(
        sessionId,
        {
          message: question
        },
        {
          onMetadata: (metadata) => {
            if (!optimisticAssistantId) {
              return;
            }
            setMessages((current) =>
              current.map((message) =>
                message.id === optimisticAssistantId ? { ...message, trace_id: metadata.trace_id } : message
              )
            );
          },
          onStatus: (status) => setGraphStatus(status.label),
          onSources: (sources) => {
            streamWarnings = sources.warnings;
            if (!optimisticAssistantId) {
              return;
            }
            setAnswerWarnings((current) => ({ ...current, [optimisticAssistantId as string]: sources.warnings }));
            setMessages((current) =>
              current.map((message) =>
                message.id === optimisticAssistantId ? { ...message, citation_json: sources.citations } : message
              )
            );
          },
          onToken: (content) => {
            if (!optimisticAssistantId || !content) {
              return;
            }
            setMessages((current) =>
              current.map((message) =>
                message.id === optimisticAssistantId ? { ...message, content: message.content + content } : message
              )
            );
          },
          onReplace: (replacement) => {
            if (!optimisticAssistantId) {
              return;
            }
            setMessages((current) =>
              current.map((message) =>
                message.id === optimisticAssistantId ? { ...message, content: replacement.content } : message
              )
            );
          }
        }
      );

      const persistedMessages = mapTutorMessages(detail.messages);
      const persistedAssistantId = [...persistedMessages].reverse().find((message) => message.role === "assistant")?.id;
      if (persistedAssistantId && streamWarnings.length > 0) {
        setAnswerWarnings((current) => {
          const next = { ...current, [persistedAssistantId]: streamWarnings };
          if (optimisticAssistantId) {
            delete next[optimisticAssistantId];
          }
          return next;
        });
      }
      setMessages(persistedMessages);
      setActiveHomeThreadId(detail.session.id);
      navigate(`${PATHS.app}?session_id=${detail.session.id}`, { replace: true, state: null });
      upsertHomeThread(detail.session);
      setPrompt("");
      void queryClient.invalidateQueries({ queryKey: ["dashboard", "summary"] });
    } catch (error) {
      setMessages(messagesBeforeSend);
      setComposerFeedback({
        message: error instanceof Error ? error.message : "消息发送失败，请稍后再试。",
        tone: "warning"
      });
    } finally {
      setStreamingAnswerId(null);
      setGraphStatus(null);
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

  function resetHomeEntry() {
    isResettingHomeRef.current = true;
    recognitionRef.current?.stop();
    if (typeof window !== "undefined" && "speechSynthesis" in window) {
      window.speechSynthesis.cancel();
    }
    setPrompt("");
    setMessages([]);
    setActiveHomeThreadId(null);
    setConversationMaterialIds([]);
    setMaterialDraftIds([]);
    setCourseMaterialIds([]);
    setIsHistoryCollapsed(isCompactWorkspaceViewport());
    setIsLibraryOpen(false);
    setIsCourseDialogOpen(false);
    setIsListening(false);
    setActiveAnswerPanel("sources");
    setExpandedAnswerId(null);
    setStreamingAnswerId(null);
    setGraphStatus(null);
    setAnswerWarnings({});
    setComposerFeedback(null);
    setCourseDialogFeedback(null);
    setMaterialDialogFeedback(null);
    navigate(PATHS.app, { replace: true, state: null });
    window.requestAnimationFrame(() => {
      document.documentElement.scrollTop = 0;
      document.documentElement.scrollLeft = 0;
      document.body.scrollTop = 0;
      document.body.scrollLeft = 0;
      if (homeChatStageRef.current) {
        homeChatStageRef.current.scrollTop = 0;
        homeChatStageRef.current.scrollLeft = 0;
      }
    });
  }

  const selectHomeConversation = useCallback(async (conversation: DashboardSummaryThread) => {
    setActiveHomeThreadId(conversation.id);

    try {
      const detail = await getTutorSession(conversation.id);

      setMessages(mapTutorMessages(detail.data.messages));
      setConversationMaterialIds((detail.data.session.selected_material_ids ?? []).map(String));
      setMaterialDraftIds((detail.data.session.selected_material_ids ?? []).map(String));
      navigate(`${PATHS.app}?session_id=${conversation.id}`, { state: null });
    } catch (error) {
      void error;
      setComposerFeedback({ message: "历史对话读取失败，请稍后再试。", tone: "warning" });
    }
  }, [navigate]);

  useEffect(() => {
    if (!selectedHomeThreadIdFromNavigation) {
      isResettingHomeRef.current = false;
      return;
    }
    if (isResettingHomeRef.current || messages.length > 0) {
      return;
    }

    void (async () => {
      try {
        const detail = await getTutorSession(selectedHomeThreadIdFromNavigation);

        setMessages(mapTutorMessages(detail.data.messages));
        setActiveHomeThreadId(selectedHomeThreadIdFromNavigation);
        setConversationMaterialIds((detail.data.session.selected_material_ids ?? []).map(String));
        setMaterialDraftIds((detail.data.session.selected_material_ids ?? []).map(String));
      } catch (error) {
        void error;
        setComposerFeedback({ message: "历史对话读取失败，请稍后再试。", tone: "warning" });
      }
    })();
  }, [messages.length, selectedHomeThreadIdFromNavigation]);

  async function createCourseFromSelectedMaterials(courseTitle: string) {
    const selectedMaterialIdsAsNumbers = courseMaterialIds
      .map((materialId) => Number.parseInt(materialId, 10))
      .filter((materialId) => Number.isFinite(materialId));

    if (selectedMaterialIdsAsNumbers.length === 0) {
      setCourseDialogFeedback({ message: "请先选择至少一份资料。", tone: "warning" });
      return;
    }

    if (isCreatingCourse) {
      return;
    }

    setCourseDialogFeedback(null);

    try {
      const job = await createCourseBuilderJob(
        { material_ids: selectedMaterialIdsAsNumbers, course_title: courseTitle.trim() },
        createIdempotencyKey("home-course")
      );
      setCourseJobId(job.job_id);
      trackJob(job);
    } catch (error) {
      setCourseDialogFeedback({
        message: getApiErrorMessage(error, "课程生成失败，请确认选择的是已解析资料。"),
        tone: "warning"
      });
    }
  }

  return (
    <LearningSpaceShell hideTopNavigation surfaceClassName="home-learning-surface">
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
          onHomeClick={resetHomeEntry}
          onNewChat={resetHomeEntry}
          onSelectConversation={(conversation) => void selectHomeConversation(conversation)}
          onRenameConversation={renameHomeConversation}
          onDeleteConversation={deleteHomeConversation}
          hasMoreConversations={Boolean(historyQuery.hasNextPage)}
          isLoadingMoreConversations={historyQuery.isFetchingNextPage}
          onLoadMoreConversations={() => void historyQuery.fetchNextPage()}
          historySearchResults={historySearch ? historySearchThreads : undefined}
          historySearchPending={historySearchQuery.isPending && Boolean(historySearch)}
          historySearchError={historySearchQuery.isError}
          historySearchHasMore={Boolean(historySearchQuery.hasNextPage)}
          historySearchLoadingMore={historySearchQuery.isFetchingNextPage}
          onHistorySearch={setHistorySearch}
          onRetryHistorySearch={() => void historySearchQuery.refetch()}
          onLoadMoreHistorySearch={() => void historySearchQuery.fetchNextPage()}
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
                  {message.role === "assistant" && message.streaming ? (
                    <span className="message-thinking" role="status" aria-live="polite">
                      {message.id === streamingAnswerId ? graphStatus ?? "正在组织回答" : "正在组织回答"}
                    </span>
                  ) : null}
                  {message.role === "assistant" ? <MarkdownMessage content={message.content} /> : <p>{message.content}</p>}
                  {message.role === "assistant" && !message.streaming ? (
                    <button className="message-speak-button" type="button" aria-label="朗读回答" onClick={() => handleSpeakMessage(message.content)}>
                      <SpeakerHigh size={15} weight="duotone" aria-hidden="true" />
                      <span>朗读</span>
                    </button>
                  ) : null}
                  {message.role === "assistant" && !message.streaming ? (
                    <HomeAnswerInsights
                      message={message}
                      activePanel={activeAnswerPanel}
                      expandedAnswerId={expandedAnswerId}
                      selectedMaterialCount={effectiveConversationMaterialIds.length}
                      warnings={answerWarnings[message.id] ?? []}
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
                <span>{`嗨，${learnerName}，`}</span>
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
            {effectiveConversationMaterialIds.length > 0 ? (
              <div className="selected-materials-note">
                <LinkSimple size={16} weight="duotone" aria-hidden="true" />
                <span>{materials.filter((material) => effectiveConversationMaterialIds.includes(material.id)).slice(0, 3).map((material) => material.title).join("、")}</span>
                <small>{`共 ${effectiveConversationMaterialIds.length} 份`}</small>
                <button type="button" onClick={openLibrary}>管理</button>
              </div>
            ) : null}
            <InlineFeedback message={composerFeedback?.message ?? null} tone={composerFeedback?.tone} className="composer-inline-feedback" />
          </section>

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
                <button
                  className="home-all-courses-button"
                  type="button"
                  aria-expanded={isCourseDrawerOpen}
                  aria-controls="home-course-drawer-title"
                  onClick={() => setIsCourseDrawerOpen(true)}
                >
                  <BookOpen size={15} weight="duotone" aria-hidden="true" />
                  <span>全部课程</span>
                </button>
              </div>
              <ul className="recent-course-list" aria-label="最近学习列表">
                {recentCourses.map((course) => (
                  <li key={course.id}>
                    <Link className="recent-course" to={buildCoursePath(course.id)}>
                      <BookOpen size={18} weight="duotone" aria-hidden="true" />
                      <span className="recent-course-copy">
                        <strong>{course.title}</strong>
                        <small><b>当前重点</b>{course.focus}</small>
                      </span>
                      <span className="recent-course-progress"><small>进度</small><em>{course.progress_label}</em></span>
                      <span className="course-next"><small>下一步</small><strong>{course.next}</strong></span>
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
          selectedMaterialIds={materialDraftIds}
          onToggleMaterial={toggleMaterialDraft}
          onOpenCourseGeneration={openCourseGenerationFromLibrary}
          onConfirm={() => void confirmConversationMaterials()}
          allowClear={effectiveConversationMaterialIds.length > 0}
          feedback={materialDialogFeedback}
          onClose={() => setIsLibraryOpen(false)}
        />
      ) : null}
      {isCourseDrawerOpen ? <HomeCourseDrawer onClose={() => setIsCourseDrawerOpen(false)} /> : null}
      {isCourseDialogOpen ? (
        <CourseGenerationDialog
          materials={materials}
          selectedMaterialIds={courseMaterialIds}
          onToggleMaterial={toggleCourseMaterial}
          onClose={() => setIsCourseDialogOpen(false)}
          onCreate={(courseTitle) => void createCourseFromSelectedMaterials(courseTitle)}
          isCreatingCourse={isCreatingCourse}
          initialCourseTitle={typeof courseJob?.request.course_title === "string" ? courseJob.request.course_title : undefined}
          job={courseJob}
          onCancelJob={() => courseJob && void cancelJob(courseJob.job_id)}
          onRetryJob={() => courseJob && void retryJob(courseJob.job_id).then((job) => setCourseJobId(job.job_id))}
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
  warnings: string[];
  onChangePanel: (panel: HomeAnswerPanel) => void;
  onSetExpandedAnswer: (messageId: string | null) => void;
};

function HomeAnswerInsights({
  message,
  activePanel,
  expandedAnswerId,
  selectedMaterialCount,
  warnings,
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
        ? `系统已检索 ${selectedMaterialCount} 份已选资料，但没有返回可展示来源。`
        : "系统没有找到需要展示的资料或网页来源。";

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
              {warnings.length > 0 ? (
                <ul className="insight-warning-list" aria-label="工具提示">
                  {warnings.map((warning) => (
                    <li key={warning}>{warning}</li>
                  ))}
                </ul>
              ) : null}
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
                      {event.contextMessageCount ? (
                        <span className="trace-context-note">
                          {`已参考最近 ${event.contextMessageCount} 条会话${event.contextSummaryUsed ? "，并使用历史摘要" : ""}`}
                        </span>
                      ) : null}
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
    return "外部补充";
  }
  if (sourceType === "history") {
    return "历史对话";
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
  initialCourseTitle?: string;
  job?: AiJob;
  onCancelJob: () => void;
  onRetryJob: () => void;
  feedback: { message: string; tone: FeedbackTone } | null;
};

function CourseGenerationDialog({
  materials,
  selectedMaterialIds,
  onToggleMaterial,
  onClose,
  onCreate,
  isCreatingCourse,
  initialCourseTitle,
  job,
  onCancelJob,
  onRetryJob,
  feedback
}: CourseGenerationDialogWithNoticeProps) {
  const selectedCount = selectedMaterialIds.length;
  const [courseTitle, setCourseTitle] = useState(initialCourseTitle || "我的资料课程");

  return (
    <ModalFrame title="从资料生成课程" layerClassName="course-dialog-backdrop" onClose={onClose} dismissible={!isCreatingCourse}>
      <section className="course-dialog" aria-labelledby="course-dialog-title">
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
        {job ? <AiJobProgress job={job} onCancel={onCancelJob} onRetry={onRetryJob} /> : null}
        <button
          className={selectedCount > 0 ? "dialog-primary-button" : "dialog-primary-button disabled"}
          type="button"
          disabled={selectedCount === 0 || isCreatingCourse}
          onClick={() => onCreate(courseTitle)}
        >
          {isCreatingCourse ? "生成中" : "生成课程"}
        </button>
      </section>
    </ModalFrame>
  );
}

type MaterialLibraryDrawerProps = CourseGenerationDialogProps & {
  materials: LibraryMaterial[];
  selectedMaterialIds: string[];
  onToggleMaterial: (materialId: string) => void;
  onOpenCourseGeneration: () => void;
  onConfirm: () => void;
  allowClear: boolean;
  feedback: { message: string; tone: FeedbackTone } | null;
};

function MaterialLibraryDrawer({ materials, selectedMaterialIds, onToggleMaterial, onOpenCourseGeneration, onConfirm, allowClear, feedback, onClose }: MaterialLibraryDrawerProps) {
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
    <ModalFrame title="资料库" layerClassName="course-dialog-backdrop" onClose={onClose}>
      <section className="material-drawer" aria-labelledby="library-dialog-title">
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
          <InlineFeedback message={feedback?.message ?? null} tone={feedback?.tone} />
          <button
            className="dialog-primary-button"
            type="button"
            disabled={selectedCount === 0 && !allowClear}
            onClick={onConfirm}
          >
            {selectedCount > 0 || !allowClear ? "作为本次对话参考" : "清空对话参考"}
          </button>
        </div>
      </section>
    </ModalFrame>
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
        const unavailable = Boolean(material.ingestion_status && material.ingestion_status !== "confirmed");

        return (
          <button
            className={isSelected ? "material-file-row selected" : "material-file-row"}
            key={material.id}
            type="button"
            aria-pressed={isSelected}
            disabled={unavailable}
            onClick={() => onToggleMaterial(material.id)}
          >
            <span className="material-file-type">{material.type}</span>
            <span className="material-file-main">
              <strong>{material.title}</strong>
              <small>{unavailable ? "请先到资料库检查并确认目录" : material.detail}</small>
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

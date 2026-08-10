import { useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import { type KeyboardEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { getCourseLearningState, getMasteryMap } from "../../api/courses";
import { getDashboardSummary } from "../../api/dashboard";
import { getLearningNextAction } from "../../api/learning";
import { listMaterials } from "../../api/materials";
import {
  createTutorResourceGenerationJob,
  createTutorSession,
  getTutorSession,
  streamTutorMessage
} from "../../api/tutor";
import { PATHS } from "../../app/routePaths";
import { isCompactWorkspaceViewport, useResponsiveSidebarState } from "../../components/layout/useResponsiveSidebarState";
import type { FeedbackTone } from "../../components/feedback/InlineFeedback";
import { useAiJobs } from "../aiJobs/AiJobProvider";
import { useAuthStore } from "../auth/authStore";
import { learningActionKeys, useLearningNextAction } from "../learning-actions/learningActions";
import { useBrowserSpeech } from "../speech/useBrowserSpeech";
import { appendTutorProgressStage, type TutorResponseProgressState } from "../tutor/tutorResponseProgress";
import { useTutorImageDraft } from "../tutor/useTutorImageDraft";
import { useTutorPersistedResponseProgress } from "../tutor/useTutorPersistedResponseProgress";
import { useHomeConversationThreads } from "./useHomeConversationThreads";
import { useHomeCourseBuilder } from "./useHomeCourseBuilder";
import { useHomeMaterialSelection } from "./useHomeMaterialSelection";
import {
  HOME_COMPOSER_MAX_HEIGHT,
  type DashboardSummaryThread,
  type HomeAnswerPanel,
  type HomeMessage,
  type LearningSpaceNavigationState,
  type LibraryMaterial,
  type PendingHomeResourceGeneration,
  mapTutorMessages
} from "./homeLearningModel";

export function useLearningSpaceController() {
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
  const initialHomeSearch = new URLSearchParams(location.search);
  const initialHomePanel = initialHomeSearch.get("panel");
  const homeChatStageRef = useRef<HTMLElement | null>(null);
  const homeQuestionInputRef = useRef<HTMLTextAreaElement>(null);
  const isResettingHomeRef = useRef(false);
  const refreshedTutorResourceJobIds = useRef(new Set<string>());
  const [prompt, setPrompt] = useState("");
  const [messages, setMessages] = useState<HomeMessage[]>([]);
  const [activeHomeThreadId, setActiveHomeThreadId] = useState<string | null>(() => selectedHomeThreadIdFromNavigation);
  const [isSendingQuestion, setIsSendingQuestion] = useState(false);
  const [isHistoryCollapsed, setIsHistoryCollapsed] = useResponsiveSidebarState();
  const [activeAnswerPanel, setActiveAnswerPanel] = useState<HomeAnswerPanel>(
    initialHomePanel === "why" || initialHomePanel === "trace" ? initialHomePanel : "sources"
  );
  const [expandedAnswerId, setExpandedAnswerId] = useState<string | null>(() => initialHomeSearch.get("message_id"));
  const [streamingAnswerId, setStreamingAnswerId] = useState<string | null>(null);
  const [streamProgress, setStreamProgress] = useState<TutorResponseProgressState | null>(null);
  const [answerProgress, setAnswerProgress] = useState<Record<string, TutorResponseProgressState & { durationMs: number }>>({});
  const [answerWarnings, setAnswerWarnings] = useState<Record<string, string[]>>({});
  const [composerFeedback, setComposerFeedback] = useState<{ message: string; tone: FeedbackTone } | null>(null);
  const [isCourseDrawerOpen, setIsCourseDrawerOpen] = useState(false);
  const [pendingHomeResourceGeneration, setPendingHomeResourceGeneration] = useState<PendingHomeResourceGeneration | null>(null);
  const speech = useBrowserSpeech({
    onTranscript: (transcript) => setPrompt((current) => current.trim() ? `${current.trim()} ${transcript}` : transcript),
    onNotice: (message, tone) => setComposerFeedback({ message, tone })
  });
  const isListening = speech.isListening;
  const isTranscribing = speech.isTranscribing;
  const { jobs, trackJob } = useAiJobs();
  const hasHomeThread = messages.length > 0;
  function updateHomeAnswerState(messageId: string | null, panel: HomeAnswerPanel = activeAnswerPanel) {
    setExpandedAnswerId(messageId);
    setActiveAnswerPanel(panel);
    const params = new URLSearchParams(location.search);
    if (messageId) {
      params.set("message_id", messageId);
      params.set("panel", panel);
    } else {
      params.delete("message_id");
      params.delete("panel");
    }
    navigate(`${PATHS.app}${params.toString() ? `?${params.toString()}` : ""}`, { replace: true, state: null });
  }
  useEffect(() => {
    if (!activeHomeThreadId) return;
    const linkedJobIds = new Set(messages.flatMap((message) => message.resource_jobs?.map((job) => job.job_id) ?? []));
    const terminalJob = jobs.find((job) => linkedJobIds.has(job.job_id) && ["completed", "failed", "cancelled"].includes(job.status) && !refreshedTutorResourceJobIds.current.has(job.job_id));
    if (!terminalJob) return;
    refreshedTutorResourceJobIds.current.add(terminalJob.job_id);
    void getTutorSession(activeHomeThreadId).then((detail) => setMessages(mapTutorMessages(detail.data.messages))).catch(() => {
      refreshedTutorResourceJobIds.current.delete(terminalJob.job_id);
    });
  }, [activeHomeThreadId, jobs, messages]);
  const persistedAnswerProgress = useTutorPersistedResponseProgress(
    messages
      .filter((message) => message.role === "assistant" && !message.streaming)
      .map((message) => ({ messageId: message.id, traceId: message.trace_id })),
    expandedAnswerId
  );
  const dashboardQuery = useQuery({
    queryKey: ["dashboard", "summary"],
    queryFn: getDashboardSummary,
    enabled: Boolean(token),
    staleTime: 30_000
  });
  const dashboardSummary = dashboardQuery.data?.data;
  const recentCourses = useMemo(() => dashboardSummary?.recent_courses ?? [], [dashboardSummary?.recent_courses]);
  const nextActionQuery = useLearningNextAction();
  const insightCourseId = Number(
    nextActionQuery.data?.data.course_id
      ?? dashboardSummary?.current_course_id
      ?? recentCourses.find((course) => course.is_current)?.id
  );
  const hasInsightCourse = Number.isFinite(insightCourseId);
  const insightMasteryQuery = useQuery({
    queryKey: ["courses", "mastery-map", insightCourseId],
    queryFn: () => getMasteryMap(insightCourseId),
    enabled: Boolean(token) && !hasHomeThread && hasInsightCourse,
    staleTime: 10_000,
    retry: false
  });
  const insightLearningStateQuery = useQuery({
    queryKey: ["courses", "learning-state", insightCourseId],
    queryFn: () => getCourseLearningState(insightCourseId),
    enabled: Boolean(token) && !hasHomeThread && hasInsightCourse,
    staleTime: 10_000,
    retry: false
  });
  const allMaterialsQuery = useQuery({
    queryKey: ["materials", "list"],
    queryFn: () => listMaterials(),
    enabled: Boolean(token),
    staleTime: 30_000
  });
  const recentCourseActionQueries = useQueries({
    queries: recentCourses.map((course) => ({
      queryKey: learningActionKeys.detail(Number(course.id)),
      queryFn: () => getLearningNextAction(Number(course.id)),
      enabled: Boolean(token) && !hasHomeThread,
      staleTime: 5_000,
      retry: false
    }))
  });
  const recentCourseActions = useMemo(
    () => new Map(recentCourses.map((course, index) => {
      const action = recentCourseActionQueries[index]?.data?.data;
      return [course.id, action?.kind ? action : undefined];
    })),
    [recentCourseActionQueries, recentCourses]
  );
  const emptyState = dashboardSummary?.empty_state;
  const learnerName = dashboardSummary?.profile_summary.display_name.trim() || "同学";
  const fallbackHomeThreads = useMemo(
    () => dashboardSummary?.recent_conversations ?? [],
    [dashboardSummary?.recent_conversations]
  );
  const conversationThreads = useHomeConversationThreads({
    activeThreadId: activeHomeThreadId,
    enabled: Boolean(token),
    fallbackThreads: fallbackHomeThreads,
    onDeleteActive: resetHomeEntry,
    onFeedback: setComposerFeedback
  });
  const {
    deleteConversation: deleteHomeConversation,
    historyQuery,
    historySearch,
    historySearchQuery,
    historySearchThreads,
    homeThreads,
    renameConversation: renameHomeConversation,
    setHistorySearch,
    upsertThread: upsertHomeThread
  } = conversationThreads;
  const materials = useMemo<LibraryMaterial[]>(() => {
    const allMaterials = allMaterialsQuery.data?.data;
    if (allMaterialsQuery.isSuccess && Array.isArray(allMaterials)) {
      return allMaterials;
    }
    return dashboardSummary?.recent_materials ?? [];
  }, [allMaterialsQuery.data?.data, allMaterialsQuery.isSuccess, dashboardSummary?.recent_materials]);
  const materialSelection = useHomeMaterialSelection({
    activeThreadId: activeHomeThreadId,
    initialMaterialIds: selectedMaterialIdsFromNavigation,
    materials,
    onComposerFeedback: setComposerFeedback
  });
  const {
    closeDialog: closeLibrary,
    confirmSelection: confirmConversationMaterials,
    dialogOpen: isLibraryOpen,
    draftIds: materialDraftIds,
    effectiveIds: effectiveConversationMaterialIds,
    feedback: materialDialogFeedback,
    openDialog: openLibrary,
    resetSelection: resetMaterialSelection,
    restoreSelection: restoreMaterialSelection,
    setDialogOpen: setIsLibraryOpen,
    toggleDraft: toggleMaterialDraft,
    uploadDocuments: handleTutorDocumentFiles
  } = materialSelection;
  const courseBuilder = useHomeCourseBuilder({ onCloseLibrary: closeLibrary });
  const {
    cancelJob,
    createCourse: createCourseFromSelectedMaterials,
    dialogOpen: isCourseDialogOpen,
    feedback: courseDialogFeedback,
    isCreating: isCreatingCourse,
    job: courseJob,
    materialIds: courseMaterialIds,
    retryJob,
    resetDialog: resetCourseBuilderDialog,
    setDialogOpen: setIsCourseDialogOpen,
    setJobId: setCourseJobId,
    toggleMaterial: toggleCourseMaterial
  } = courseBuilder;
  const imageDraft = useTutorImageDraft(
    ensureHomeImageSession,
    (message) => setComposerFeedback({ message, tone: "warning" }),
    handleTutorDocumentFiles
  );

  useEffect(() => {
    const input = homeQuestionInputRef.current;
    if (!input) return;

    input.style.height = "auto";
    const nextHeight = Math.min(input.scrollHeight, HOME_COMPOSER_MAX_HEIGHT);
    input.style.height = `${nextHeight}px`;
    input.style.overflowY = input.scrollHeight > HOME_COMPOSER_MAX_HEIGHT ? "auto" : "hidden";
  }, [prompt]);

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

  function openCourseGeneration() {
    courseBuilder.open(effectiveConversationMaterialIds);
  }

  function openCourseGenerationFromLibrary() {
    courseBuilder.open(materialDraftIds);
  }

  function buildHomeSessionTitle(question: string) {
    return Array.from(question).slice(0, 30).join("");
  }

  async function handleSendQuestion() {
    const question = prompt.trim();

    if (!question && imageDraft.attachmentIds.length === 0) {
      setComposerFeedback({ message: "先输入问题或添加图片。", tone: "warning" });
      return;
    }

    if (imageDraft.uploading || imageDraft.hasFailed) {
      setComposerFeedback({ message: imageDraft.uploading ? "图片上传完成后才能发送。" : "请移除上传失败的图片后重试。", tone: "warning" });
      return;
    }
    if (imageDraft.attachmentIds.length > 0 && !imageDraft.visionReady) {
      setComposerFeedback({ message: "图片草稿已保留，请先配置默认图片理解模型。", tone: "warning" });
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
    const startedAt = Date.now();
    let progressStages = ["正在读取会话上下文"];

    try {
      let sessionId = activeHomeThreadId;

      if (!sessionId) {
        const created = await createTutorSession({
          scope: "home",
          course_id: null,
          mode: "chat",
          title: buildHomeSessionTitle(question || "图片提问"),
          selected_material_ids: effectiveConversationMaterialIds.map(Number)
        });
        sessionId = created.data.id;
        setActiveHomeThreadId(sessionId);
      }

      const optimisticKey = `${Date.now()}-${sessionId}`;
      const optimisticUserId = `stream-user-${optimisticKey}`;
      optimisticAssistantId = `stream-assistant-${optimisticKey}`;
      setStreamingAnswerId(optimisticAssistantId);
      setStreamProgress({ startedAt, stages: progressStages });
      setMessages([
        ...messagesBeforeSend,
        {
          id: optimisticUserId,
          role: "user",
          content: question || "请分析并讲解这张图片",
          citation_json: [],
          trace_id: null,
          attachments: imageDraft.images.flatMap((image) => image.attachment ? [image.attachment] : [])
        },
        {
          id: optimisticAssistantId,
          role: "assistant",
          content: "",
          citation_json: [],
          trace_id: null,
          attachments: [],
          streaming: true
        }
      ]);

      const detail = await streamTutorMessage(
        sessionId,
        {
          message: question,
          ...(imageDraft.attachmentIds.length ? { attachment_ids: imageDraft.attachmentIds } : {})
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
          onStatus: (status) => {
            progressStages = appendTutorProgressStage(progressStages, status.label);
            setStreamProgress((current) => current ? { ...current, stages: progressStages } : current);
          },
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
      const persistedAssistant = [...persistedMessages].reverse().find((message) => message.role === "assistant");
      const persistedAssistantId = persistedAssistant?.id;
      if (persistedAssistantId) {
        setAnswerProgress((current) => ({
          ...current,
          [persistedAssistantId]: { startedAt, stages: progressStages, durationMs: Date.now() - startedAt }
        }));
      }
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
      if (persistedAssistantId && persistedAssistant?.resource_proposal?.action === "generate") {
        setPendingHomeResourceGeneration({ sessionId: detail.session.id, messageId: persistedAssistantId });
      }
      setActiveHomeThreadId(detail.session.id);
      navigate(`${PATHS.app}?session_id=${detail.session.id}`, { replace: true, state: null });
      upsertHomeThread(detail.session);
      setPrompt("");
      imageDraft.clearAfterSend();
      void queryClient.invalidateQueries({ queryKey: ["dashboard", "summary"] });
    } catch (error) {
      setMessages(messagesBeforeSend);
      setComposerFeedback({
        message: error instanceof Error ? error.message : "消息发送失败，请稍后再试。",
        tone: "warning"
      });
    } finally {
      setStreamingAnswerId(null);
      setStreamProgress(null);
      setIsSendingQuestion(false);
    }
  }

  async function ensureHomeImageSession() {
    if (activeHomeThreadId) return activeHomeThreadId;
    const created = await createTutorSession({
      scope: "home", course_id: null, mode: "chat", title: "图片提问",
      selected_material_ids: effectiveConversationMaterialIds.map(Number)
    });
    setActiveHomeThreadId(created.data.id);
    upsertHomeThread(created.data);
    return created.data.id;
  }

  async function generateHomeResource(courseId: number) {
    const pending = pendingHomeResourceGeneration;
    if (!pending) return;
    try {
      const job = await createTutorResourceGenerationJob(pending.sessionId, pending.messageId, { course_id: courseId });
      trackJob(job);
      const detail = await getTutorSession(pending.sessionId);
      setMessages(mapTutorMessages(detail.data.messages));
      setPendingHomeResourceGeneration(null);
    } catch (error) {
      setComposerFeedback({ message: error instanceof Error ? error.message : "资源生成任务创建失败，请稍后再试。", tone: "warning" });
    }
  }

  function handleComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void handleSendQuestion();
    }
  }

  function handleVoiceInput() {
    speech.toggleListening();
  }

  function toggleReadMessage(message: HomeMessage) {
    if (speech.activeSpeechId === message.id) {
      speech.stopSpeaking();
      return;
    }
    speech.speak(message.content, message.id);
  }

  function resetHomeEntry() {
    isResettingHomeRef.current = true;
    speech.stopListening();
    speech.stopSpeaking();
    imageDraft.discardAll();
    setPrompt("");
    setMessages([]);
    setActiveHomeThreadId(null);
    resetMaterialSelection();
    resetCourseBuilderDialog();
    setIsHistoryCollapsed(isCompactWorkspaceViewport());
    setActiveAnswerPanel("sources");
    setExpandedAnswerId(null);
    setStreamingAnswerId(null);
    setStreamProgress(null);
    setAnswerProgress({});
    setAnswerWarnings({});
    setComposerFeedback(null);
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
    speech.stopListening();
    speech.stopSpeaking();
    imageDraft.discardAll();
    setActiveHomeThreadId(conversation.id);

    try {
      const detail = await getTutorSession(conversation.id);

      setMessages(mapTutorMessages(detail.data.messages));
      restoreMaterialSelection((detail.data.session.selected_material_ids ?? []).map(String));
      navigate(`${PATHS.app}?session_id=${conversation.id}`, { state: null });
    } catch (error) {
      void error;
      setComposerFeedback({ message: "历史对话读取失败，请稍后再试。", tone: "warning" });
    }
  }, [imageDraft, navigate, restoreMaterialSelection, speech]);

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
        restoreMaterialSelection((detail.data.session.selected_material_ids ?? []).map(String));
      } catch (error) {
        void error;
        setComposerFeedback({ message: "历史对话读取失败，请稍后再试。", tone: "warning" });
      }
    })();
  }, [messages.length, restoreMaterialSelection, selectedHomeThreadIdFromNavigation]);

  return {
    isHistoryCollapsed,
    hasHomeThread,
    homeThreads,
    activeHomeThreadId,
    setIsHistoryCollapsed,
    resetHomeEntry,
    selectHomeConversation,
    renameHomeConversation,
    deleteHomeConversation,
    historyQuery,
    historySearch,
    historySearchThreads,
    historySearchQuery,
    setHistorySearch,
    homeChatStageRef,
    messages,
    streamingAnswerId,
    streamProgress,
    answerProgress,
    persistedAnswerProgress,
    speech,
    toggleReadMessage,
    activeAnswerPanel,
    expandedAnswerId,
    effectiveConversationMaterialIds,
    answerWarnings,
    updateHomeAnswerState,
    setPendingHomeResourceGeneration,
    homeQuestionInputRef,
    prompt,
    setPrompt,
    handleComposerKeyDown,
    imageDraft,
    openLibrary,
    openCourseGeneration,
    isListening,
    isTranscribing,
    handleVoiceInput,
    isSendingQuestion,
    handleSendQuestion,
    materials,
    composerFeedback,
    learnerName,
    recentCourses,
    insightCourseId,
    nextActionQuery,
    insightMasteryQuery,
    insightLearningStateQuery,
    dashboardQuery,
    recentCourseActions,
    isCourseDrawerOpen,
    setIsCourseDrawerOpen,
    emptyState,
    isLibraryOpen,
    materialDraftIds,
    toggleMaterialDraft,
    openCourseGenerationFromLibrary,
    confirmConversationMaterials,
    materialDialogFeedback,
    setIsLibraryOpen,
    pendingHomeResourceGeneration,
    generateHomeResource,
    isCourseDialogOpen,
    courseMaterialIds,
    toggleCourseMaterial,
    setIsCourseDialogOpen,
    createCourseFromSelectedMaterials,
    isCreatingCourse,
    courseJob,
    cancelJob,
    retryJob,
    setCourseJobId,
    courseDialogFeedback,
  };
}

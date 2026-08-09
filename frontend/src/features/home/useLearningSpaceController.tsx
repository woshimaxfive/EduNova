import { useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import { type KeyboardEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { createCourseBuilderJob, createIdempotencyKey, getAiJob } from "../../api/aiJobs";
import { getCourseLearningState, getMasteryMap } from "../../api/courses";
import { getDashboardSummary } from "../../api/dashboard";
import { getApiErrorMessage } from "../../api/errors";
import { getLearningNextAction } from "../../api/learning";
import { listMaterials, uploadMaterial } from "../../api/materials";
import {
  createTutorResourceGenerationJob,
  createTutorSession,
  deleteTutorSession,
  getTutorSession,
  renameTutorSession,
  streamTutorMessage,
  type TutorSessionSummary
} from "../../api/tutor";
import { buildCoursePath, PATHS } from "../../app/routePaths";
import { isCompactWorkspaceViewport, useResponsiveSidebarState } from "../../components/layout/useResponsiveSidebarState";
import type { FeedbackTone } from "../../components/feedback/InlineFeedback";
import { useAiJobs } from "../aiJobs/AiJobProvider";
import { isRestorableCourseBuilderJob } from "../aiJobs/jobRestoration";
import { useAuthStore } from "../auth/authStore";
import { invalidateLearningNextActions, learningActionKeys, useLearningNextAction } from "../learning-actions/learningActions";
import { useBrowserSpeech } from "../speech/useBrowserSpeech";
import { appendTutorProgressStage, type TutorResponseProgressState } from "../tutor/tutorResponseProgress";
import { useTutorImageDraft } from "../tutor/useTutorImageDraft";
import { useTutorPersistedResponseProgress } from "../tutor/useTutorPersistedResponseProgress";
import { useHomeConversationHistory } from "./useHomeConversationHistory";
import {
  HOME_COMPOSER_MAX_HEIGHT,
  type DashboardSummaryResponse,
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
  const [localHomeThreads, setLocalHomeThreads] = useState<DashboardSummaryThread[]>([]);
  const [historySearch, setHistorySearch] = useState("");
  const [activeHomeThreadId, setActiveHomeThreadId] = useState<string | null>(() => selectedHomeThreadIdFromNavigation);
  const [isSendingQuestion, setIsSendingQuestion] = useState(false);
  const [conversationMaterialIds, setConversationMaterialIds] = useState<string[]>([]);
  const [materialDraftIds, setMaterialDraftIds] = useState<string[]>(() => selectedMaterialIdsFromNavigation);
  const [courseMaterialIds, setCourseMaterialIds] = useState<string[]>([]);
  const [isHistoryCollapsed, setIsHistoryCollapsed] = useResponsiveSidebarState();
  const [isCourseDialogOpen, setIsCourseDialogOpen] = useState(false);
  const [courseJobId, setCourseJobId] = useState<string | null>(null);
  const [isLibraryOpen, setIsLibraryOpen] = useState(() => selectedMaterialIdsFromNavigation.length > 0);
  const [activeAnswerPanel, setActiveAnswerPanel] = useState<HomeAnswerPanel>(
    initialHomePanel === "why" || initialHomePanel === "trace" ? initialHomePanel : "sources"
  );
  const [expandedAnswerId, setExpandedAnswerId] = useState<string | null>(() => initialHomeSearch.get("message_id"));
  const [streamingAnswerId, setStreamingAnswerId] = useState<string | null>(null);
  const [streamProgress, setStreamProgress] = useState<TutorResponseProgressState | null>(null);
  const [answerProgress, setAnswerProgress] = useState<Record<string, TutorResponseProgressState & { durationMs: number }>>({});
  const [answerWarnings, setAnswerWarnings] = useState<Record<string, string[]>>({});
  const [composerFeedback, setComposerFeedback] = useState<{ message: string; tone: FeedbackTone } | null>(null);
  const [courseDialogFeedback, setCourseDialogFeedback] = useState<{ message: string; tone: FeedbackTone } | null>(null);
  const [materialDialogFeedback, setMaterialDialogFeedback] = useState<{ message: string; tone: FeedbackTone } | null>(null);
  const [isCourseDrawerOpen, setIsCourseDrawerOpen] = useState(false);
  const [pendingHomeResourceGeneration, setPendingHomeResourceGeneration] = useState<PendingHomeResourceGeneration | null>(null);
  const imageDraft = useTutorImageDraft(
    ensureHomeImageSession,
    (message) => setComposerFeedback({ message, tone: "warning" }),
    handleTutorDocumentFiles
  );
  const speech = useBrowserSpeech({
    onTranscript: (transcript) => setPrompt((current) => current.trim() ? `${current.trim()} ${transcript}` : transcript),
    onNotice: (message, tone) => setComposerFeedback({ message, tone })
  });
  const isListening = speech.isListening;
  const isTranscribing = speech.isTranscribing;
  const { jobs, trackJob, getJob, cancelJob, retryJob } = useAiJobs();
  const courseJob = getJob(courseJobId);
  const isCreatingCourse = Boolean(courseJob && ["queued", "running", "cancelling"].includes(courseJob.status));
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
  const historyQuery = useHomeConversationHistory("", Boolean(token));
  const historySearchQuery = useHomeConversationHistory(historySearch, Boolean(token && historySearch));
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
    const input = homeQuestionInputRef.current;
    if (!input) return;

    input.style.height = "auto";
    const nextHeight = Math.min(input.scrollHeight, HOME_COMPOSER_MAX_HEIGHT);
    input.style.height = `${nextHeight}px`;
    input.style.overflowY = input.scrollHeight > HOME_COMPOSER_MAX_HEIGHT ? "auto" : "hidden";
  }, [prompt]);

  useEffect(() => {
    if (courseJobId) return;
    const restored = jobs.find(isRestorableCourseBuilderJob);
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
      void invalidateLearningNextActions(queryClient);
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

  async function handleTutorDocumentFiles(files: File[]) {
    if (files.length === 0) return;
    try {
      for (const file of files) {
        const response = await uploadMaterial({ file });
        if (response.data.ingestion_job_id) {
          trackJob(await getAiJob(response.data.ingestion_job_id));
        }
      }
      await queryClient.invalidateQueries({ queryKey: ["materials", "list"] });
      await queryClient.invalidateQueries({ queryKey: ["dashboard", "summary"] });
      await invalidateLearningNextActions(queryClient);
      setComposerFeedback({ message: `${files.length} 份资料已上传，正在后台识别目录和正文切片。`, tone: "success" });
    } catch (error) {
      void error;
      setComposerFeedback({ message: "资料上传失败，请稍后再试。", tone: "warning" });
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
    setConversationMaterialIds([]);
    setMaterialDraftIds([]);
    setCourseMaterialIds([]);
    setIsHistoryCollapsed(isCompactWorkspaceViewport());
    setIsLibraryOpen(false);
    setIsCourseDialogOpen(false);
    setActiveAnswerPanel("sources");
    setExpandedAnswerId(null);
    setStreamingAnswerId(null);
    setStreamProgress(null);
    setAnswerProgress({});
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
    speech.stopListening();
    speech.stopSpeaking();
    imageDraft.discardAll();
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
  }, [imageDraft, navigate, speech]);

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

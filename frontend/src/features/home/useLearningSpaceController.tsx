import { useQueries, useQuery } from "@tanstack/react-query";
import { type KeyboardEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { getCourseLearningState, getMasteryMap } from "../../api/courses";
import { getDashboardSummary } from "../../api/dashboard";
import { getLearningNextAction } from "../../api/learning";
import { listMaterials } from "../../api/materials";
import { createTutorSession, getTutorSession } from "../../api/tutor";
import { PATHS } from "../../app/routePaths";
import { isCompactWorkspaceViewport, useResponsiveSidebarState } from "../../components/layout/useResponsiveSidebarState";
import type { FeedbackTone } from "../../components/feedback/InlineFeedback";
import { useAuthStore } from "../auth/authStore";
import { learningActionKeys, useLearningNextAction } from "../learning-actions/learningActions";
import { useBrowserSpeech } from "../speech/useBrowserSpeech";
import { useTutorImageDraft } from "../tutor/useTutorImageDraft";
import { useTutorPersistedResponseProgress } from "../tutor/useTutorPersistedResponseProgress";
import { useHomeConversationThreads } from "./useHomeConversationThreads";
import { useHomeCourseBuilder } from "./useHomeCourseBuilder";
import { useHomeMaterialSelection } from "./useHomeMaterialSelection";
import { useHomeTutorConversation } from "./useHomeTutorConversation";
import {
  HOME_COMPOSER_MAX_HEIGHT,
  type DashboardSummaryThread,
  type HomeAnswerPanel,
  type HomeMessage,
  type LearningSpaceNavigationState,
  type LibraryMaterial,
  mapTutorMessages
} from "./homeLearningModel";

export function useLearningSpaceController() {
  const token = useAuthStore((state) => state.token);
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
  const [prompt, setPrompt] = useState("");
  const [activeHomeThreadId, setActiveHomeThreadId] = useState<string | null>(() => selectedHomeThreadIdFromNavigation);
  const [isHistoryCollapsed, setIsHistoryCollapsed] = useResponsiveSidebarState();
  const [activeAnswerPanel, setActiveAnswerPanel] = useState<HomeAnswerPanel>(
    initialHomePanel === "why" || initialHomePanel === "trace" ? initialHomePanel : "sources"
  );
  const [expandedAnswerId, setExpandedAnswerId] = useState<string | null>(() => initialHomeSearch.get("message_id"));
  const [composerFeedback, setComposerFeedback] = useState<{ message: string; tone: FeedbackTone } | null>(null);
  const [isCourseDrawerOpen, setIsCourseDrawerOpen] = useState(false);
  const speech = useBrowserSpeech({
    onTranscript: (transcript) => setPrompt((current) => current.trim() ? `${current.trim()} ${transcript}` : transcript),
    onNotice: (message, tone) => setComposerFeedback({ message, tone })
  });
  const isListening = speech.isListening;
  const isTranscribing = speech.isTranscribing;
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
  const allMaterialsQuery = useQuery({
    queryKey: ["materials", "list"],
    queryFn: () => listMaterials(),
    enabled: Boolean(token),
    staleTime: 30_000
  });
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
  const conversation = useHomeTutorConversation({
    activeThreadId: activeHomeThreadId,
    onActiveThreadChange: setActiveHomeThreadId,
    onComposerFeedback: setComposerFeedback,
    onPromptChange: setPrompt,
    prompt,
    upsertHomeThread
  });
  const {
    answerProgress,
    answerWarnings,
    closeResourceGeneration,
    generateResource: generateHomeResource,
    hasHomeThread,
    isSending: isSendingQuestion,
    messages,
    openResourceGeneration,
    pendingResourceGeneration: pendingHomeResourceGeneration,
    resetConversation,
    restoreMessages,
    handleSendQuestion: sendHomeTutorQuestion,
    streamProgress,
    streamingAnswerId
  } = conversation;
  const persistedAnswerProgress = useTutorPersistedResponseProgress(
    messages
      .filter((message) => message.role === "assistant" && !message.streaming)
      .map((message) => ({ messageId: message.id, traceId: message.trace_id })),
    expandedAnswerId
  );
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
    toggleDraft: toggleMaterialDraft,
    uploadDocuments: handleTutorDocumentFiles
  } = materialSelection;
  const courseBuilder = useHomeCourseBuilder({ onCloseLibrary: closeLibrary });
  const {
    cancelCreation: cancelCourseCreation,
    closeDialog: closeCourseGeneration,
    createCourse: createCourseFromSelectedMaterials,
    dialogOpen: isCourseDialogOpen,
    feedback: courseDialogFeedback,
    isCreating: isCreatingCourse,
    job: courseJob,
    materialIds: courseMaterialIds,
    resetDialog: resetCourseBuilderDialog,
    retryCreation: retryCourseCreation,
    toggleMaterial: toggleCourseMaterial
  } = courseBuilder;
  const imageDraft = useTutorImageDraft(
    ensureHomeImageSession,
    (message) => setComposerFeedback({ message, tone: "warning" }),
    handleTutorDocumentFiles
  );

  function handleSendQuestion() {
    return sendHomeTutorQuestion({ effectiveMaterialIds: effectiveConversationMaterialIds, imageDraft });
  }

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
    resetConversation();
    setActiveHomeThreadId(null);
    resetMaterialSelection();
    resetCourseBuilderDialog();
    setIsHistoryCollapsed(isCompactWorkspaceViewport());
    setActiveAnswerPanel("sources");
    setExpandedAnswerId(null);
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

      restoreMessages(mapTutorMessages(detail.data.messages));
      restoreMaterialSelection((detail.data.session.selected_material_ids ?? []).map(String));
      navigate(`${PATHS.app}?session_id=${conversation.id}`, { state: null });
    } catch (error) {
      void error;
      setComposerFeedback({ message: "历史对话读取失败，请稍后再试。", tone: "warning" });
    }
  }, [imageDraft, navigate, restoreMaterialSelection, restoreMessages, speech]);

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

        restoreMessages(mapTutorMessages(detail.data.messages));
        setActiveHomeThreadId(selectedHomeThreadIdFromNavigation);
        restoreMaterialSelection((detail.data.session.selected_material_ids ?? []).map(String));
      } catch (error) {
        void error;
        setComposerFeedback({ message: "历史对话读取失败，请稍后再试。", tone: "warning" });
      }
    })();
  }, [messages.length, restoreMaterialSelection, restoreMessages, selectedHomeThreadIdFromNavigation]);

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
    closeLibrary,
    pendingHomeResourceGeneration,
    generateHomeResource,
    openResourceGeneration,
    closeResourceGeneration,
    isCourseDialogOpen,
    courseMaterialIds,
    toggleCourseMaterial,
    closeCourseGeneration,
    createCourseFromSelectedMaterials,
    isCreatingCourse,
    courseJob,
    cancelCourseCreation,
    retryCourseCreation,
    courseDialogFeedback,
  };
}

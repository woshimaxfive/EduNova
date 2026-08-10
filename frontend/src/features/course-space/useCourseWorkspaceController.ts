import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";

import { PATHS } from "../../app/routePaths";
import { getAgentTrace, mapAgentTraceStepToEvent } from "../../api/agents";
import { type LearningNextAction } from "../../api/learning";
import {
  activateCourse,
  getKnowledgePointContent,
  updateCourseWeaknessReviewItem,
  type CourseWeaknessReviewAction,
  type CourseWeaknessReviewItem
} from "../../api/courses";
import { type RagSearchResultItem } from "../../api/rag";
import { type CourseAnswerPanelKind } from "../../components/course-space/CourseClosedLoopActions";
import { useResponsiveSidebarState } from "../../components/layout/useResponsiveSidebarState";
import { buildCourseLoopSummary, buildStudySteps, calculateMasteryPercent } from "./a3Loop";
import { invalidateCourseLearningLoop } from "./courseLoopQueries";
import { useCourseWorkspaceData } from "./useCourseWorkspaceData";
import { useCourseResourceGeneration } from "./useCourseResourceGeneration";
import { useCourseTutorConversation } from "./useCourseTutorConversation";
import { useCourseWorkspaceUrlState } from "./useCourseWorkspaceUrlState";
import {
  findBestCitationKnowledgePoint
} from "./courseRecommendation";
import {
  buildCourseClosureHref,
  buildCourseStarterQuestions
} from "./courseConversation";
import { useLearningNextAction } from "../learning-actions/learningActions";

export function useCourseWorkspaceController() {
  const { courseId } = useParams();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const numericCourseId = courseId ? Number.parseInt(courseId, 10) : Number.NaN;
  const hasRealCourseId = Number.isFinite(numericCourseId);
  const queryClient = useQueryClient();
  useEffect(() => {
    if (!hasRealCourseId) return;
    void activateCourse(numericCourseId).then(() => {
      void queryClient.invalidateQueries({ queryKey: ["courses"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard", "summary"] });
      void queryClient.invalidateQueries({ queryKey: ["learning", "next-action", "global"] });
    }).catch(() => undefined);
  }, [hasRealCourseId, numericCourseId, queryClient]);
  const {
    courseOverviewQuery,
    courseQuery,
    courseResourcesQuery,
    courseSessionsQuery,
    currentPathQuery,
    knowledgePointsQuery,
    latestPracticeQuery,
    latestReportQuery,
    learningStateQuery,
    masteryMapQuery
  } = useCourseWorkspaceData(numericCourseId, hasRealCourseId);
  const [isProgressDrawerOpen, setIsProgressDrawerOpen] = useState(searchParams.get("open_progress") === "1");
  const [isProgressSyncing, setIsProgressSyncing] = useState(false);
  const [progressSyncWarning, setProgressSyncWarning] = useState<string | null>(null);
  const [isHistoryCollapsed, setIsHistoryCollapsed] = useResponsiveSidebarState();
  const [weaknessFeedback, setWeaknessFeedback] = useState<string | null>(null);
  const [updatingWeaknessItemId, setUpdatingWeaknessItemId] = useState<string | null>(null);
  const apiCourse = courseQuery.data?.data;
  const overviewCourse = courseOverviewQuery.data?.data.course;
  const fallbackCourse = apiCourse ?? overviewCourse;
  const apiKnowledgePoints = useMemo(
    () => knowledgePointsQuery.data?.data ?? [],
    [knowledgePointsQuery.data?.data]
  );
  const overviewMaterials = courseOverviewQuery.data?.data.materials ?? [];
  const learningState = learningStateQuery.data?.data;
  const weaknessSummary = learningState?.weakness_summary;
  const weaknessItems = (learningState?.weakness_review_queue ?? []).filter((item) => item.status !== "dismissed");
  const activeWeaknessCount = weaknessItems.filter((item) => ["pending", "confirmed", "reviewing"].includes(item.status)).length;
  const masteryPoints = useMemo(() => masteryMapQuery.data?.data.points ?? [], [masteryMapQuery.data?.data.points]);
  const nextActionQuery = useLearningNextAction(hasRealCourseId ? numericCourseId : null);
  const recommendation: LearningNextAction = nextActionQuery.data?.data ?? {
    kind: "study_knowledge_point",
    status: "ready",
    label: "从课程内容开始学习",
    description: "先建立课程知识基础，再通过问答和练习形成学习闭环。",
    course_id: hasRealCourseId ? String(numericCourseId) : null,
    material_id: null,
    knowledge_point_id: apiKnowledgePoints[0]?.id ?? null,
    path_task_id: null,
    resource_id: null
  };
  const activeWeaknessPointIds = weaknessItems
    .filter((item) => ["confirmed", "reviewing", "pending"].includes(item.status) && item.knowledge_point_id)
    .map((item) => item.knowledge_point_id as string);
  const {
    activeTurnDetail,
    changeCourseContentView,
    changeCourseMode,
    changeGraphChapter,
    changeGraphScope,
    changeKnowledgeDetail,
    courseContentView,
    courseMode,
    graphChapter,
    graphScope,
    isKnowledgeDetailOpen,
    isStudyAssistantOpen,
    openCitationStudy,
    openKnowledgeStudy,
    setActiveTurnDetail,
    setCourseMode,
    setIsStudyAssistantOpen,
    setStudyTarget,
    studyTarget
  } = useCourseWorkspaceUrlState({
    enabled: hasRealCourseId,
    masteryPoints,
    recommendedPointId: recommendation.knowledge_point_id,
    activeWeaknessPointIds,
    searchParams,
    setSearchParams
  });
  const courseSessions = Array.isArray(courseSessionsQuery.data?.data) ? courseSessionsQuery.data.data : [];
  const {
    answerProgress: courseAnswerProgress,
    chatEndRef: courseChatEndRef,
    createConversation: createCourseConversation,
    deleteConversation: deleteCourseConversation,
    displayedMessages: displayedCourseMessages,
    feedback: courseFeedback,
    generateSuggestedResources: generateSuggestedCourseResources,
    handleComposerKeyDown: handleCourseComposerKeyDown,
    hasDisplayedMessages: hasDisplayedCourseMessages,
    imageDraft,
    inputRef: courseQuestionInputRef,
    isSending: isSearchingCourse,
    persistedAnswerProgress: persistedCourseAnswerProgress,
    prompt: coursePrompt,
    renameConversation: renameCourseConversation,
    selectConversation: selectCourseConversation,
    selectedSessionId: selectedCourseSessionId,
    sendQuestion: sendCourseQuestion,
    setPrompt: setCoursePrompt,
    sidebarConversations,
    speech,
    streamProgress: courseStreamProgress,
    toggleReadMessage
  } = useCourseTutorConversation({
    activeTurnMessageId: activeTurnDetail?.messageId ?? null,
    courseId: numericCourseId,
    courseMode,
    enabled: hasRealCourseId,
    queryClient,
    resetWorkspace: resetConversationWorkspace,
    searchParams,
    sessions: courseSessions,
    setSearchParams
  });
  const isCourseLoading = hasRealCourseId && courseQuery.isPending && !fallbackCourse;
  const courseSummary = fallbackCourse
    ? {
        id: Number.parseInt(fallbackCourse.id, 10),
        title: fallbackCourse.title,
        description: fallbackCourse.description,
        subject: fallbackCourse.subject,
        sourceType: fallbackCourse.source_type,
        progressPercent: calculateMasteryPercent(masteryMapQuery.data?.data.points ?? [])
      }
    : {
        id: Number.isFinite(numericCourseId) ? numericCourseId : 0,
        title: isCourseLoading ? "课程加载中" : "课程暂不可用",
        description: isCourseLoading ? "正在读取这门课的资料、知识点和历史对话。" : "请从学习主页或课程列表重新进入。",
        subject: "课程空间",
        sourceType: "uploaded" as const,
        progressPercent: null
      };
  const latestAssistantWithRetrieval = [...displayedCourseMessages].reverse().find((message) => message.role === "assistant" && message.citations !== undefined);
  const latestRagResults = latestAssistantWithRetrieval?.citations ?? [];
  const latestAgentTraceId = latestAssistantWithRetrieval?.traceId ?? learningState?.evidence_summary?.latest_trace_id ?? null;
  const activeDetailMessage = activeTurnDetail
    ? displayedCourseMessages.find((message) => message.id === activeTurnDetail.messageId && message.role === "assistant") ?? null
    : null;
  const activeDetailTraceId = activeDetailMessage?.traceId
    ?? (activeDetailMessage?.id === latestAssistantWithRetrieval?.id ? latestAgentTraceId : null);
  const agentTraceQuery = useQuery({
    queryKey: ["agents", "trace", activeDetailTraceId],
    queryFn: () => getAgentTrace(activeDetailTraceId ?? ""),
    enabled: Boolean(activeDetailTraceId) && (activeTurnDetail?.panel === "thinking" || activeTurnDetail?.panel === "why"),
    staleTime: 10_000
  });
  const agentTraceEvents = useMemo(
    () => agentTraceQuery.data?.data.steps.map(mapAgentTraceStepToEvent) ?? [],
    [agentTraceQuery.data?.data.steps]
  );
  const selectedKnowledgePoint =
    studyTarget?.type === "knowledge"
      ? apiKnowledgePoints.find((point) => point.id === studyTarget.id) ?? null
      : studyTarget?.type === "citation"
        ? apiKnowledgePoints.find((point) => point.id === String(studyTarget.citation.knowledge_point_id)) ?? null
        : apiKnowledgePoints[0] ?? null;
  const selectedCitation = studyTarget?.type === "citation" ? studyTarget.citation : null;
  const selectedKnowledgePointId = selectedKnowledgePoint ? Number.parseInt(selectedKnowledgePoint.id, 10) : Number.NaN;
  const knowledgePointContentQuery = useQuery({
    queryKey: ["courses", "knowledge-point-content", numericCourseId, selectedKnowledgePointId],
    queryFn: () => getKnowledgePointContent(numericCourseId, selectedKnowledgePointId),
    enabled: hasRealCourseId && Number.isFinite(selectedKnowledgePointId),
    staleTime: 30_000
  });
  const materialCount = fallbackCourse?.material_count ?? overviewMaterials.length;
  const knowledgePointCount = fallbackCourse?.knowledge_point_count ?? apiKnowledgePoints.length;
  const generatedResources = courseResourcesQuery.data?.data ?? [];
  const currentPath = currentPathQuery.data?.data ?? null;
  const currentPathTaskPointId = (Array.isArray(currentPath?.tasks) ? currentPath.tasks : []).find((task) => task.status === "doing")?.knowledge_point_id ?? null;
  const latestReport = latestReportQuery.data?.data ?? null;
  const latestPractice = latestPracticeQuery.data?.data ?? null;
  const latestUserQuestion = [...displayedCourseMessages].reverse().find((message) => message.role === "user")?.content ?? null;
  const hasActivePath = Boolean(currentPath?.path) || learningState?.path_summary?.status === "active";
  const courseStarterQuestions = buildCourseStarterQuestions(recommendation, apiKnowledgePoints);
  const profileOverlay = learningState?.profile_overlay;
  const hasProfileEvidence = Boolean(
    profileOverlay?.learning_goal.trim()
      || profileOverlay?.knowledge_foundation.trim()
      || profileOverlay?.weak_points.length
  );
  const courseLoopInput = {
    courseTitle: courseSummary.title,
    materialCount,
    knowledgePointCount,
    progressPercent: courseSummary.progressPercent,
    latestQuestion: latestUserQuestion,
    citationCount: latestRagResults.length,
    pendingWeaknessCount: weaknessSummary?.pending_count ?? 0,
    confirmedWeaknessCount: weaknessSummary?.confirmed_count ?? 0,
    resourceCount: generatedResources.length,
    hasActivePath,
    latestTraceWorkflow: latestAgentTraceId ? "CourseTutorGraph" : null,
    latestTraceId: latestAgentTraceId,
    hasLatestReport: latestReport?.status === "ready",
    hasProfileEvidence,
    hasCompletedPractice: latestPractice?.status === "completed",
    recommendedGoal: recommendation.description,
    recommendedAction: recommendation.label
  };
  const courseLoopSummary = buildCourseLoopSummary(courseLoopInput);
  const courseStudySteps = buildStudySteps(courseLoopInput);
  const {
    cancelResourceJob,
    feedback: courseResourceFeedback,
    isGenerating: isGeneratingCourseResources,
    latestGeneratedResources,
    mutation: courseResourceMutation,
    resourceJob,
    retryResourceJob,
    selectedResourceTypes: selectedCourseResourceTypes,
    setResourceContext,
    submitGeneration: submitCourseResourceGeneration,
    toggleResourceType: toggleCourseResourceType
  } = useCourseResourceGeneration({
    courseId: numericCourseId,
    enabled: hasRealCourseId,
    courseResourcesQuery,
    masteryPoints,
    latestUserQuestion,
    currentGoal: courseLoopSummary.currentGoal
  });

  function resetConversationWorkspace() {
    setCourseMode("chat");
    setStudyTarget(null);
    setActiveTurnDetail(null);
    setIsStudyAssistantOpen(false);
  }

  function changeStudyAssistant(open: boolean) {
    setIsStudyAssistantOpen(open);
    if (!open) {
      speech.stopListening();
      speech.stopSpeaking();
    } else if (!coursePrompt.trim() && selectedKnowledgePoint) {
      setCoursePrompt(`关于“${selectedKnowledgePoint.title}”，`);
    }
    const nextParams = new URLSearchParams(searchParams);
    nextParams.set("mode", "study");
    if (open) {
      nextParams.set("mentor", "open");
      if (selectedCourseSessionId) nextParams.set("course_session_id", selectedCourseSessionId);
    } else {
      nextParams.delete("mentor");
    }
    setSearchParams(nextParams, { replace: true });
  }

  async function syncCourseProgress() {
    if (!hasRealCourseId || isProgressSyncing) return;

    setIsProgressSyncing(true);
    setProgressSyncWarning(null);
    try {
      const results = await Promise.all([
        learningStateQuery.refetch(),
        masteryMapQuery.refetch(),
        courseResourcesQuery.refetch(),
        currentPathQuery.refetch(),
        latestReportQuery.refetch(),
        latestPracticeQuery.refetch()
      ]);
      if (results.some((result) => result.isError)) {
        setProgressSyncWarning("部分学习状态暂未更新，已保留上次成功结果。");
      }
    } catch {
      setProgressSyncWarning("部分学习状态暂未更新，已保留上次成功结果。");
    } finally {
      setIsProgressSyncing(false);
    }
  }

  function openCourseProgress() {
    setIsProgressDrawerOpen(true);
    void syncCourseProgress();
  }

  function toggleTurnPanel(
    messageId: string,
    panel: CourseAnswerPanelKind,
    question: string | null,
    citations: RagSearchResultItem[]
  ) {
    const closes = activeTurnDetail?.messageId === messageId && activeTurnDetail.panel === panel;
    setActiveTurnDetail(closes ? null : { messageId, panel });
    const nextParams = new URLSearchParams(searchParams);
    nextParams.set("mode", "chat");
    nextParams.set("course_message_id", messageId);
    if (closes) nextParams.delete("panel");
    else nextParams.set("panel", panel === "thinking" ? "trace" : panel);
    setSearchParams(nextParams, { replace: true });
    if (panel === "resources") {
      setResourceContext({ question, knowledgePointId: findBestCitationKnowledgePoint(citations) });
    }
  }

  function runRecommendedAction(
    messageId: string,
    citations: RagSearchResultItem[],
    turnRecommendation: LearningNextAction
  ) {
    const knowledgePointId = turnRecommendation.knowledge_point_id ?? findBestCitationKnowledgePoint(citations);

    if (turnRecommendation.kind === "confirm_weakness") {
      openCourseProgress();
      return;
    }
    if (turnRecommendation.kind === "study_knowledge_point" && knowledgePointId) {
      openKnowledgeStudy(knowledgePointId);
      return;
    }
    if (turnRecommendation.kind === "continue_path_task") {
      if (turnRecommendation.resource_id) {
        const params = new URLSearchParams({ course_id: String(numericCourseId), resource_id: turnRecommendation.resource_id });
        if (turnRecommendation.path_task_id) params.set("path_task_id", turnRecommendation.path_task_id);
        navigate(`${PATHS.studio}?${params.toString()}`);
      } else if (knowledgePointId) {
        openKnowledgeStudy(knowledgePointId);
      } else {
        navigate(buildCourseClosureHref(PATHS.path, numericCourseId, selectedCourseSessionId, messageId));
      }
      return;
    }
    if (turnRecommendation.kind === "practice_weakness") {
      navigate(buildCourseClosureHref(PATHS.practice, numericCourseId, selectedCourseSessionId, messageId, knowledgePointId));
      return;
    }
    if (turnRecommendation.kind === "generate_path") {
      navigate(buildCourseClosureHref(PATHS.path, numericCourseId, selectedCourseSessionId, messageId, knowledgePointId));
      return;
    }
    navigate(buildCourseClosureHref(PATHS.reports, numericCourseId, selectedCourseSessionId, messageId));
  }

  async function updateWeaknessReviewItem(item: CourseWeaknessReviewItem, action: CourseWeaknessReviewAction) {
    if (!hasRealCourseId || updatingWeaknessItemId !== null) {
      return;
    }

    setUpdatingWeaknessItemId(item.id);
    setWeaknessFeedback(null);

    try {
      await updateCourseWeaknessReviewItem(numericCourseId, item.id, action);
      await invalidateCourseLearningLoop(queryClient, numericCourseId);
    } catch {
      setWeaknessFeedback("弱点状态更新失败，请稍后重试。");
    } finally {
      setUpdatingWeaknessItemId(null);
    }
  }

  return {
    activeTurnDetail,
    activeWeaknessCount,
    agentTraceEvents,
    agentTraceQuery,
    apiCourse,
    apiKnowledgePoints,
    cancelResourceJob,
    changeCourseContentView,
    changeCourseMode,
    changeGraphChapter,
    changeGraphScope,
    changeKnowledgeDetail,
    changeStudyAssistant,
    courseAnswerProgress,
    courseChatEndRef,
    courseContentView,
    courseFeedback,
    courseLoopSummary,
    courseMode,
    coursePrompt,
    courseQuestionInputRef,
    courseResourceFeedback,
    courseResourceMutation,
    courseStarterQuestions,
    courseStreamProgress,
    courseStudySteps,
    courseSummary,
    createCourseConversation,
    currentPathTaskPointId,
    deleteCourseConversation,
    displayedCourseMessages,
    fallbackCourse,
    generateSuggestedCourseResources,
    generatedResources,
    graphChapter,
    graphScope,
    handleCourseComposerKeyDown,
    hasDisplayedCourseMessages,
    hasRealCourseId,
    imageDraft,
    isGeneratingCourseResources,
    isHistoryCollapsed,
    isKnowledgeDetailOpen,
    isProgressDrawerOpen,
    isProgressSyncing,
    isSearchingCourse,
    isStudyAssistantOpen,
    knowledgePointContentQuery,
    knowledgePointCount,
    latestAgentTraceId,
    latestAssistantWithRetrieval,
    latestGeneratedResources,
    learningState,
    learningStateQuery,
    masteryMapQuery,
    materialCount,
    navigate,
    numericCourseId,
    openCitationStudy,
    openCourseProgress,
    openKnowledgeStudy,
    persistedCourseAnswerProgress,
    progressSyncWarning,
    recommendation,
    renameCourseConversation,
    resourceJob,
    retryResourceJob,
    runRecommendedAction,
    searchParams,
    selectCourseConversation,
    selectedCitation,
    selectedCourseResourceTypes,
    selectedCourseSessionId,
    selectedKnowledgePoint,
    sendCourseQuestion,
    setCoursePrompt,
    setIsHistoryCollapsed,
    setIsProgressDrawerOpen,
    sidebarConversations,
    speech,
    submitCourseResourceGeneration,
    syncCourseProgress,
    toggleCourseResourceType,
    toggleReadMessage,
    toggleTurnPanel,
    updateWeaknessReviewItem,
    updatingWeaknessItemId,
    weaknessFeedback,
    weaknessItems,
    weaknessSummary,
  };
}

export type CourseWorkspaceController = ReturnType<typeof useCourseWorkspaceController>;

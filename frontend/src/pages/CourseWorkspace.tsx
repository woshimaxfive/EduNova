import {
  ArrowRight,
  ChartLineUp,
  ListChecks,
  MapTrifold,
  Microphone
} from "@phosphor-icons/react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type KeyboardEvent, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";

import { PATHS, buildCoursePathWorkspacePath, buildCoursePracticeWorkspacePath, buildCourseReportsWorkspacePath } from "../app/routePaths";
import { getAgentTrace, mapAgentTraceStepToEvent } from "../api/agents";
import { createIdempotencyKey, createResourceGenerationJob, getAiJob } from "../api/aiJobs";
import { uploadMaterial } from "../api/materials";
import {
  activateCourse,
  getKnowledgePointContent,
  updateCourseWeaknessReviewItem,
  type CourseWeaknessReviewAction,
  type CourseWeaknessReviewItem
} from "../api/courses";
import { type RagSearchResultItem } from "../api/rag";
import { type GeneratedResource, type ResourceType } from "../api/resources";
import {
  createTutorSession,
  deleteTutorSession,
  getTutorSession,
  listTutorSessions,
  renameTutorSession,
  streamTutorMessage,
  createTutorResourceGenerationJob,
  type TutorSessionSummary
} from "../api/tutor";
import { CourseAnswerDetailPanel } from "../components/course-space/CourseAnswerDetailPanel";
import { CourseAssistantTurn } from "../components/course-space/CourseAssistantTurn";
import { CourseClosedLoopActions, type CourseAnswerPanelKind } from "../components/course-space/CourseClosedLoopActions";
import { CourseContentView, type CourseContentMode } from "../components/course-space/CourseContentView";
import { CourseInlineResourcePanel } from "../components/course-space/CourseInlineResourcePanel";
import { CourseProgressDrawer } from "../components/course-space/CourseProgressDrawer";
import { NextLearningAction } from "../components/learning/NextLearningAction";
import { CourseWorkspaceHeader, type CourseWorkspaceMode } from "../components/course-space/CourseWorkspaceHeader";
import { InlineFeedback } from "../components/feedback/InlineFeedback";
import { AppSidebar } from "../components/layout/AppSidebar";
import { LearningSpaceShell } from "../components/layout/LearningSpaceShell";
import { useResponsiveSidebarState } from "../components/layout/useResponsiveSidebarState";
import { buildCourseLoopSummary, buildStudySteps, calculateMasteryPercent } from "../features/course-space/a3Loop";
import { invalidateCourseLearningLoop } from "../features/course-space/courseLoopQueries";
import { useCourseWorkspaceData } from "../features/course-space/useCourseWorkspaceData";
import {
  normalizeCourseWorkspaceParams,
  parseCourseWorkspaceUrl,
  sameSearchParams,
  selectCourseWorkspacePoint,
  type GraphScope
} from "../features/course-space/courseWorkspaceState";
import {
  findBestCitationKnowledgePoint,
  resourceDifficultyForPoint
} from "../features/course-space/courseRecommendation";
import {
  buildCourseClosureHref,
  buildCourseStarterQuestions,
  courseQuestionTitle,
  findQuestionForAssistant,
  mapCourseSessionsToConversations,
  mapTutorMessagesToCourseMessages,
  sanitizeCourseAnswerContent,
  type CourseMessage
} from "../features/course-space/courseConversation";
import { useAiJobs } from "../features/aiJobs/AiJobProvider";
import { useLearningNextAction } from "../features/learning-actions/learningActions";
import { type LearningNextAction } from "../api/learning";
import { useBrowserSpeech } from "../features/speech/useBrowserSpeech";
import { SecureTutorImages, TutorImagePicker } from "../features/tutor/TutorImageAttachments";
import { useTutorImageDraft } from "../features/tutor/useTutorImageDraft";
import { appendTutorProgressStage, type TutorResponseProgressState } from "../features/tutor/tutorResponseProgress";
import { useTutorPersistedResponseProgress } from "../features/tutor/useTutorPersistedResponseProgress";
import { TutorResponseProgress } from "../components/tutor/TutorResponseProgress";
import "../styles/course-space.css";

type TutorSessionsResponse = Awaited<ReturnType<typeof listTutorSessions>>;
type TurnDetailState = {
  messageId: string;
  panel: CourseAnswerPanelKind;
} | null;
type StudyTarget =
  | {
      type: "knowledge";
      id: string;
    }
  | {
      type: "citation";
      citation: RagSearchResultItem;
    };

const COURSE_COMPOSER_MAX_HEIGHT = 154;

export function CourseWorkspace() {
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
  const initialWorkspaceState = parseCourseWorkspaceUrl(searchParams);
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
  const [activeCourseSessionId, setActiveCourseSessionId] = useState<string | null>(null);
  const [activeTurnDetail, setActiveTurnDetail] = useState<TurnDetailState>(
    initialWorkspaceState.courseMessageId && initialWorkspaceState.panel
      ? { messageId: initialWorkspaceState.courseMessageId, panel: initialWorkspaceState.panel }
      : null
  );
  const initialKnowledgePointId = initialWorkspaceState.knowledgePointId;
  const [courseMode, setCourseMode] = useState<CourseWorkspaceMode>(hasRealCourseId ? initialWorkspaceState.mode : "chat");
  const [courseContentView, setCourseContentView] = useState<CourseContentMode>(hasRealCourseId ? initialWorkspaceState.view : "overview");
  const [graphScope, setGraphScope] = useState<GraphScope>(initialWorkspaceState.graphScope);
  const [graphChapter, setGraphChapter] = useState(initialWorkspaceState.graphChapter);
  const [isKnowledgeDetailOpen, setIsKnowledgeDetailOpen] = useState(initialWorkspaceState.detailKnowledge);
  const [isProgressDrawerOpen, setIsProgressDrawerOpen] = useState(searchParams.get("open_progress") === "1");
  const [isProgressSyncing, setIsProgressSyncing] = useState(false);
  const [progressSyncWarning, setProgressSyncWarning] = useState<string | null>(null);
  const [isStudyAssistantOpen, setIsStudyAssistantOpen] = useState(initialWorkspaceState.mentorOpen);
  const [studyTarget, setStudyTarget] = useState<StudyTarget | null>(
    initialKnowledgePointId ? { type: "knowledge", id: initialKnowledgePointId } : null
  );
  const [isHistoryCollapsed, setIsHistoryCollapsed] = useResponsiveSidebarState();
  const [coursePrompt, setCoursePrompt] = useState("");
  const [courseMessages, setCourseMessages] = useState<CourseMessage[]>([]);
  const [streamingSessionId, setStreamingSessionId] = useState<string | null>(null);
  const [courseStreamProgress, setCourseStreamProgress] = useState<TutorResponseProgressState | null>(null);
  const [courseAnswerProgress, setCourseAnswerProgress] = useState<Record<string, TutorResponseProgressState & { durationMs: number }>>({});
  const [isSearchingCourse, setIsSearchingCourse] = useState(false);
  const [courseFeedback, setCourseFeedback] = useState<string | null>(null);
  const imageDraft = useTutorImageDraft(ensureCourseImageSession, setCourseFeedback, handleCourseDocumentFiles);
  const [weaknessFeedback, setWeaknessFeedback] = useState<string | null>(null);
  const [courseResourceFeedback, setCourseResourceFeedback] = useState<string | null>(null);
  const [latestGeneratedResources, setLatestGeneratedResources] = useState<GeneratedResource[]>([]);
  const [resourceContext, setResourceContext] = useState<{ question: string | null; knowledgePointId: string | null }>({
    question: null,
    knowledgePointId: null
  });
  const [resourceJobId, setResourceJobId] = useState<string | null>(null);
  const [selectedCourseResourceTypes, setSelectedCourseResourceTypes] = useState<ResourceType[]>(["doc", "mindmap", "quiz"]);
  const [updatingWeaknessItemId, setUpdatingWeaknessItemId] = useState<string | null>(null);
  const speech = useBrowserSpeech({
    onTranscript: (transcript) => setCoursePrompt((current) => current.trim() ? `${current.trim()} ${transcript}` : transcript),
    onNotice: (message) => setCourseFeedback(message)
  });
  const optimisticMessageSequence = useRef(0);
  const handledResourceJobId = useRef<string | null>(null);
  const courseQuestionInputRef = useRef<HTMLTextAreaElement>(null);
  const courseChatEndRef = useRef<HTMLDivElement>(null);
  const { jobs, trackJob, getJob, cancelJob, retryJob } = useAiJobs();
  const resourceJob = getJob(resourceJobId);
  const isGeneratingCourseResources = Boolean(resourceJob && ["queued", "running", "cancelling"].includes(resourceJob.status));

  useEffect(() => {
    if (resourceJobId || !hasRealCourseId) return;
    const restored = jobs.find((job) => job.workflow === "resource_generation"
      && Number(job.request.course_id) === numericCourseId
      && ["queued", "running", "cancelling", "failed"].includes(job.status));
    if (!restored) return;
    // Restore durable server state after navigation or refresh.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (Array.isArray(restored.request.resource_types)) setSelectedCourseResourceTypes(restored.request.resource_types as ResourceType[]);
    setResourceJobId(restored.job_id);
  }, [hasRealCourseId, jobs, numericCourseId, resourceJobId]);

  useEffect(() => {
    const input = courseQuestionInputRef.current;
    if (!input) return;

    input.style.height = "auto";
    const nextHeight = Math.min(input.scrollHeight, COURSE_COMPOSER_MAX_HEIGHT);
    input.style.height = `${nextHeight}px`;
    input.style.overflowY = input.scrollHeight > COURSE_COMPOSER_MAX_HEIGHT ? "auto" : "hidden";
  }, [coursePrompt]);
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
  const courseSessions = Array.isArray(courseSessionsQuery.data?.data) ? courseSessionsQuery.data.data : [];
  const latestCourseSessionId = courseSessions[0]?.id ?? null;
  const requestedCourseSessionId = searchParams.get("course_session_id");
  const requestedCourseMessageId = searchParams.get("course_message_id");
  const restorableCourseSessionId = courseSessions.some((session) => session.id === requestedCourseSessionId)
    ? requestedCourseSessionId
    : null;
  const selectedCourseSessionId = hasRealCourseId
    ? (activeCourseSessionId ?? restorableCourseSessionId ?? latestCourseSessionId)
    : null;
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
  const persistedCourseAnswerProgress = useTutorPersistedResponseProgress(
    displayedCourseMessages
      .filter((message) => message.role === "assistant")
      .map((message) => ({ messageId: message.id, traceId: message.traceId })),
    activeTurnDetail?.messageId
  );
  const hasDisplayedCourseMessages = displayedCourseMessages.length > 0;
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
  const latestMessageSignature = displayedCourseMessages.length > 0
    ? `${displayedCourseMessages.at(-1)?.id ?? ""}:${displayedCourseMessages.at(-1)?.content.length ?? 0}`
    : "empty";
  const hasActivePath = Boolean(currentPath?.path) || learningState?.path_summary?.status === "active";
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
  const workspaceSearchSignature = searchParams.toString();
  const activeWeaknessPointSignature = weaknessItems
    .filter((item) => ["confirmed", "reviewing", "pending"].includes(item.status) && item.knowledge_point_id)
    .map((item) => item.knowledge_point_id)
    .join(",");
  const recommendedWorkspacePointId = recommendation.knowledge_point_id;
  useEffect(() => {
    if (!hasRealCourseId || masteryPoints.length === 0) return;
    const requested = parseCourseWorkspaceUrl(new URLSearchParams(workspaceSearchSignature));
    const selectedPointId = selectCourseWorkspacePoint(
      masteryPoints,
      requested.knowledgePointId,
      recommendedWorkspacePointId,
      activeWeaknessPointSignature ? activeWeaknessPointSignature.split(",") : []
    );
    const chapters = new Set(masteryPoints.map((point) => point.chapter?.trim()).filter((value): value is string => Boolean(value)));
    const normalized = normalizeCourseWorkspaceParams(new URLSearchParams(workspaceSearchSignature), requested, selectedPointId, chapters);

    // URL 是可恢复语义状态的事实来源；这里同时响应浏览器前进、后退和刷新。
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setCourseMode(requested.mode);
    setCourseContentView(requested.view);
    setGraphScope(requested.graphScope);
    setGraphChapter(requested.graphChapter && chapters.has(requested.graphChapter) ? requested.graphChapter : "");
    setIsKnowledgeDetailOpen(requested.detailKnowledge && Boolean(selectedPointId));
    setIsStudyAssistantOpen(requested.mode === "study" && requested.mentorOpen);
    if (selectedPointId) setStudyTarget({ type: "knowledge", id: selectedPointId });
    setActiveTurnDetail(requested.courseMessageId && requested.panel
      ? { messageId: requested.courseMessageId, panel: requested.panel }
      : null);
    if (!sameSearchParams(new URLSearchParams(workspaceSearchSignature), normalized)) {
      setSearchParams(normalized, { replace: true });
    }
  }, [activeWeaknessPointSignature, hasRealCourseId, masteryPoints, recommendedWorkspacePointId, setSearchParams, workspaceSearchSignature]);
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

  useEffect(() => {
    if (courseMode !== "chat" || !hasDisplayedCourseMessages) return;
    const frame = window.requestAnimationFrame(() => {
      const requestedTarget = requestedCourseMessageId
        ? document.getElementById(`course-message-${requestedCourseMessageId}`)
        : null;
      const target = requestedTarget ?? courseChatEndRef.current;
      if (target && typeof target.scrollIntoView === "function") {
        target.scrollIntoView({ block: requestedTarget ? "center" : "end" });
      }
    });
    return () => window.cancelAnimationFrame(frame);
  }, [courseMode, hasDisplayedCourseMessages, latestMessageSignature, requestedCourseMessageId, selectedCourseSessionId]);

  useEffect(() => {
    if (!resourceJob) return;
    if (resourceJob.status === "failed") {
      // Surface the terminal state delivered by the external job runtime.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setCourseResourceFeedback(resourceJob.error_message ?? "课程资源生成失败，请稍后重试。");
      return;
    }
    if (resourceJob.status !== "completed" || handledResourceJobId.current === resourceJob.job_id) return;
    handledResourceJobId.current = resourceJob.job_id;
    const resourceIds = Array.isArray(resourceJob.result.resource_ids)
      ? resourceJob.result.resource_ids.map(String)
      : [];
    setCourseResourceFeedback(resourceJob.warnings.length > 0 ? resourceJob.warnings.join(" ") : null);
    void (async () => {
      await invalidateCourseLearningLoop(queryClient, numericCourseId);
      const refreshed = await courseResourcesQuery.refetch();
      const resources = refreshed.data?.data ?? [];
      setLatestGeneratedResources(resourceIds.length > 0 ? resources.filter((item) => resourceIds.includes(item.id)) : resources.slice(0, 6));
    })();
  }, [courseResourcesQuery, numericCourseId, queryClient, resourceJob]);

  const courseResourceMutation = useMutation({
    mutationFn: () => {
      const parsedKnowledgePointId = resourceContext.knowledgePointId
        ? Number.parseInt(resourceContext.knowledgePointId, 10)
        : Number.NaN;
      const masteryPoint = masteryPoints.find((point) => point.id === resourceContext.knowledgePointId);

      return createResourceGenerationJob(
        {
          course_id: numericCourseId,
          knowledge_point_id: Number.isFinite(parsedKnowledgePointId) ? parsedKnowledgePointId : undefined,
          resource_types: selectedCourseResourceTypes,
          learning_goal: resourceContext.question ?? latestUserQuestion ?? courseLoopSummary.currentGoal,
          difficulty: resourceDifficultyForPoint(masteryPoint)
        },
        createIdempotencyKey("course-resource")
      );
    },
    onSuccess: (job) => {
      handledResourceJobId.current = null;
      setResourceJobId(job.job_id);
      trackJob(job);
    },
    onError: () => {
      setCourseResourceFeedback("课程资源生成失败，请稍后重试。");
    }
  });

  function selectCourseConversation(sessionId: string) {
    if (!hasRealCourseId) {
      return;
    }

    speech.stopListening();
    speech.stopSpeaking();
    imageDraft.discardAll();
    setActiveCourseSessionId(sessionId);
    setStreamingSessionId(null);
    setCourseMessages([]);
    setCourseMode("chat");
    setStudyTarget(null);
    setActiveTurnDetail(null);
    setIsStudyAssistantOpen(false);
    const nextParams = new URLSearchParams(searchParams);
    nextParams.set("mode", "chat");
    nextParams.set("view", "overview");
    nextParams.set("course_session_id", sessionId);
    nextParams.delete("course_message_id");
    nextParams.delete("panel");
    nextParams.delete("detail");
    nextParams.delete("mentor");
    setSearchParams(nextParams, { replace: true });
  }

  async function createCourseConversation() {
    if (!hasRealCourseId) return;
    speech.stopListening();
    speech.stopSpeaking();
    imageDraft.discardAll();
    setCoursePrompt("");
    setCourseMessages([]);
    setActiveTurnDetail(null);
    setStudyTarget(null);
    setCourseMode("chat");
    try {
      const created = await createTutorSession({ scope: "course", course_id: numericCourseId, mode: "chat", title: "新建课程对话" });
      setActiveCourseSessionId(created.data.id);
      const nextParams = new URLSearchParams(searchParams);
      nextParams.set("mode", "chat");
      nextParams.set("view", "overview");
      nextParams.set("course_session_id", created.data.id);
      nextParams.delete("course_message_id");
      nextParams.delete("knowledge_point_id");
      nextParams.delete("panel");
      nextParams.delete("detail");
      setSearchParams(nextParams, { replace: true });
      void queryClient.invalidateQueries({ queryKey: ["tutor", "sessions", "course", numericCourseId] });
    } catch {
      setCourseFeedback("新建课程对话失败，请稍后重试。");
    }
  }

  function updateCourseSessionList(updater: (sessions: TutorSessionSummary[]) => TutorSessionSummary[]) {
    queryClient.setQueryData<TutorSessionsResponse>(["tutor", "sessions", "course", numericCourseId], (current) =>
      current
        ? {
            ...current,
            data: updater(current.data)
          }
        : current
    );
  }

  async function renameCourseConversation(conversation: { id: string; title: string }, title: string) {
    const normalizedTitle = title.trim();
    if (!hasRealCourseId || !normalizedTitle) {
      return;
    }

    try {
      const renamed = await renameTutorSession(conversation.id, { title: normalizedTitle });

      updateCourseSessionList((sessions) =>
        sessions.map((session) => (session.id === conversation.id ? { ...session, title: renamed.data.title } : session))
      );
      setCourseFeedback(null);
      void queryClient.invalidateQueries({ queryKey: ["tutor", "sessions", "course", numericCourseId] });
    } catch {
      setCourseFeedback("会话改名失败，请稍后重试。");
    }
  }

  async function deleteCourseConversation(conversation: { id: string }) {
    if (!hasRealCourseId) {
      return;
    }

    try {
      await deleteTutorSession(conversation.id);
      updateCourseSessionList((sessions) => sessions.filter((session) => session.id !== conversation.id));
      queryClient.removeQueries({ queryKey: ["tutor", "session", conversation.id] });

      if (selectedCourseSessionId === conversation.id || activeCourseSessionId === conversation.id) {
        setActiveCourseSessionId(null);
        setStreamingSessionId(null);
        setCourseMessages([]);
        setCourseMode("chat");
        setStudyTarget(null);
        setActiveTurnDetail(null);
        setIsStudyAssistantOpen(false);
        const nextParams = new URLSearchParams(searchParams);
        nextParams.delete("course_session_id");
        nextParams.delete("course_message_id");
        nextParams.delete("mentor");
        setSearchParams(nextParams, { replace: true });
      }

      setCourseFeedback(null);
      void queryClient.invalidateQueries({ queryKey: ["tutor", "sessions", "course", numericCourseId] });
    } catch {
      setCourseFeedback("会话删除失败，请稍后重试。");
    }
  }

  function openKnowledgeStudy(pointId: string, view: CourseContentMode = "overview") {
    setCourseMode("study");
    setStudyTarget({ type: "knowledge", id: pointId });
    setCourseContentView(view);
    setIsKnowledgeDetailOpen(view === "graph");
    const nextParams = new URLSearchParams(searchParams);
    nextParams.set("mode", "study");
    nextParams.set("view", view);
    nextParams.set("knowledge_point_id", pointId);
    if (view === "graph") nextParams.set("detail", "knowledge");
    else nextParams.delete("detail");
    setSearchParams(nextParams, { replace: true });
  }

  function openCitationStudy(citation: RagSearchResultItem) {
    setCourseMode("study");
    setStudyTarget({ type: "citation", citation });
    setCourseContentView("overview");
    if (citation.knowledge_point_id) {
      const nextParams = new URLSearchParams(searchParams);
      nextParams.set("mode", "study");
      nextParams.set("view", "overview");
      nextParams.set("knowledge_point_id", String(citation.knowledge_point_id));
      nextParams.delete("detail");
      setSearchParams(nextParams, { replace: true });
    }
  }

  function changeCourseMode(mode: CourseWorkspaceMode) {
    setCourseMode(mode);
    if (mode === "chat") setIsStudyAssistantOpen(false);
    const nextParams = new URLSearchParams(searchParams);
    nextParams.set("mode", mode);
    if (mode === "chat") nextParams.delete("mentor");
    if (mode === "study" && !nextParams.has("view")) nextParams.set("view", "graph");
    setSearchParams(nextParams, { replace: true });
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

  function changeCourseContentView(view: CourseContentMode) {
    setCourseContentView(view);
    const nextParams = new URLSearchParams(searchParams);
    nextParams.set("mode", "study");
    nextParams.set("view", view);
    if (view !== "graph") nextParams.delete("detail");
    setSearchParams(nextParams, { replace: true });
  }

  function changeGraphScope(scope: GraphScope) {
    setGraphScope(scope);
    const nextParams = new URLSearchParams(searchParams);
    nextParams.set("graph_scope", scope);
    if (scope === "focus") nextParams.delete("graph_chapter");
    setSearchParams(nextParams, { replace: true });
  }

  function changeGraphChapter(chapter: string) {
    setGraphChapter(chapter);
    const nextParams = new URLSearchParams(searchParams);
    if (chapter) nextParams.set("graph_chapter", chapter);
    else nextParams.delete("graph_chapter");
    setSearchParams(nextParams, { replace: true });
  }

  function changeKnowledgeDetail(open: boolean) {
    setIsKnowledgeDetailOpen(open);
    const nextParams = new URLSearchParams(searchParams);
    if (open) nextParams.set("detail", "knowledge");
    else nextParams.delete("detail");
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

  function toggleReadMessage(message: CourseMessage) {
    if (speech.activeSpeechId === message.id) {
      speech.stopSpeaking();
      return;
    }
    speech.speak(sanitizeCourseAnswerContent(message.content), message.id);
  }

  function toggleCourseResourceType(resourceType: ResourceType) {
    setSelectedCourseResourceTypes((current) =>
      current.includes(resourceType) ? current.filter((item) => item !== resourceType) : [...current, resourceType]
    );
  }

  function submitCourseResourceGeneration() {
    if (!hasRealCourseId || courseResourceMutation.isPending || isGeneratingCourseResources || selectedCourseResourceTypes.length === 0) {
      return;
    }

    setCourseResourceFeedback(null);
    courseResourceMutation.mutate();
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

  async function sendCourseQuestion() {
    const question = coursePrompt.trim();

    if (!question && imageDraft.attachmentIds.length === 0) {
      setCourseFeedback("先输入课程问题或添加图片。");
      return;
    }
    if (imageDraft.uploading || imageDraft.hasFailed) {
      setCourseFeedback(imageDraft.uploading ? "图片上传完成后才能发送。" : "请移除上传失败的图片后重试。");
      return;
    }
    if (imageDraft.attachmentIds.length > 0 && !imageDraft.visionReady) {
      setCourseFeedback("图片草稿已保留，请先配置默认图片理解模型。");
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
    const startedAt = Date.now();
    let progressStages = ["正在准备课程回答"];
    setCourseStreamProgress({ startedAt, stages: progressStages });
    setCourseFeedback(null);
    const previousMessages = displayedCourseMessages;

    try {
      let sessionId = selectedCourseSessionId;

      if (!sessionId) {
        const createdSession = await createTutorSession({
          scope: "course",
          course_id: numericCourseId,
          mode: "chat",
          title: courseQuestionTitle(question || "图片提问")
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
        { id: `course-user-stream-${optimisticId}`, role: "user", content: question || "请分析并讲解这张图片", attachments: imageDraft.images.flatMap((image) => image.attachment ? [image.attachment] : []) },
        { id: assistantMessageId, role: "assistant", content: "", citations: [], attachments: [] }
      ];
      setCourseMessages(optimisticMessages);

      const detail = await streamTutorMessage(sessionId, {
        message: question,
        ...(imageDraft.attachmentIds.length ? { attachment_ids: imageDraft.attachmentIds } : {})
      }, {
        onStatus: (status) => {
          progressStages = appendTutorProgressStage(progressStages, status.label);
          setCourseStreamProgress((current) => current ? { ...current, stages: progressStages } : current);
        },
        onToken: (content) => {
          setCourseMessages((current) =>
            current.map((message) =>
              message.id === assistantMessageId ? { ...message, content: `${message.content}${content}` } : message
            )
          );
        }
      });
      let messages = mapTutorMessagesToCourseMessages(detail.messages);

      const persistedAssistant = [...messages].reverse().find((message) => message.role === "assistant");
      if (persistedAssistant?.resourceProposal?.action === "generate") {
        try {
          const job = await createTutorResourceGenerationJob(detail.session.id, persistedAssistant.id, { course_id: numericCourseId });
          trackJob(job);
          const refreshed = await getTutorSession(detail.session.id);
          messages = mapTutorMessagesToCourseMessages(refreshed.data.messages);
        } catch (resourceError) {
          setCourseFeedback(resourceError instanceof Error ? resourceError.message : "回答已保存，但资源任务创建失败，请在回答下方重试。");
        }
      }

      setActiveCourseSessionId(detail.session.id);
      setCourseMessages(messages);
      setStreamingSessionId(null);
      setCourseStreamProgress(null);
      setCoursePrompt("");
      imageDraft.clearAfterSend();
      if (persistedAssistant) {
        setCourseAnswerProgress((current) => ({
          ...current,
          [persistedAssistant.id]: { startedAt, stages: progressStages, durationMs: Date.now() - startedAt }
        }));
      }
      const nextParams = new URLSearchParams(searchParams);
      nextParams.set("course_session_id", detail.session.id);
      if (persistedAssistant) nextParams.set("course_message_id", persistedAssistant.id);
      setSearchParams(nextParams, { replace: true });
      queryClient.setQueryData(["tutor", "session", detail.session.id], { data: detail, trace_id: null });
      void queryClient.invalidateQueries({ queryKey: ["tutor", "sessions", "course", numericCourseId] });
      void invalidateCourseLearningLoop(queryClient, numericCourseId);
    } catch (error) {
      setCourseMessages(previousMessages);
      setStreamingSessionId(null);
      setCourseStreamProgress(null);
      setCourseFeedback(error instanceof Error ? error.message : "模型暂不可用，请检查设置或稍后重试。");
    } finally {
      setIsSearchingCourse(false);
    }
  }

  async function generateSuggestedCourseResources(message: CourseMessage) {
    if (!selectedCourseSessionId || !hasRealCourseId || !message.resourceProposal) return;
    try {
      const job = await createTutorResourceGenerationJob(selectedCourseSessionId, message.id, { course_id: numericCourseId });
      trackJob(job);
      const refreshed = await getTutorSession(selectedCourseSessionId);
      setCourseMessages(mapTutorMessagesToCourseMessages(refreshed.data.messages));
    } catch (error) {
      setCourseFeedback(error instanceof Error ? error.message : "资源生成任务创建失败，请稍后再试。");
    }
  }

  async function ensureCourseImageSession() {
    if (selectedCourseSessionId) return selectedCourseSessionId;
    if (!hasRealCourseId) throw new Error("课程地址无效");
    const created = await createTutorSession({ scope: "course", course_id: numericCourseId, mode: "chat", title: "图片提问" });
    setActiveCourseSessionId(created.data.id);
    return created.data.id;
  }

  async function handleCourseDocumentFiles(files: File[]) {
    if (!hasRealCourseId || files.length === 0) return;
    try {
      for (const file of files) {
        const response = await uploadMaterial({ file, courseId: numericCourseId });
        if (response.data.ingestion_job_id) trackJob(await getAiJob(response.data.ingestion_job_id));
      }
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["materials", "list"] }),
        queryClient.invalidateQueries({ queryKey: ["courses", "overview", numericCourseId] })
      ]);
      setCourseFeedback(null);
    } catch {
      setCourseFeedback("资料上传失败，请稍后再试。");
    }
  }

  function handleCourseComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void sendCourseQuestion();
    }
  }

  return (
    <LearningSpaceShell hideTopNavigation mainClassName="course-learning-shell" surfaceClassName="course-learning-surface">
      <section className={isHistoryCollapsed ? "app-workspace-layout course-workspace-layout history-collapsed" : "app-workspace-layout course-workspace-layout"}>
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
          onNewChat={() => void createCourseConversation()}
          onSelectConversation={(conversation) =>
            hasRealCourseId ? void selectCourseConversation(conversation.id) : undefined
          }
          onRenameConversation={renameCourseConversation}
          onDeleteConversation={deleteCourseConversation}
        />
        <section className="route-main-surface course-route-surface">
          <div className="course-space">
            <CourseWorkspaceHeader
              title={courseSummary.title}
              progressPercent={courseSummary.progressPercent}
              materialCount={materialCount}
              knowledgePointCount={knowledgePointCount}
              weaknessCount={activeWeaknessCount}
              mode={courseMode}
              onModeChange={changeCourseMode}
              onOpenProgress={openCourseProgress}
            />

            {courseMode === "chat" ? (
              <section className="course-chat-panel course-chat-mode" role="region" aria-label="课程对话空间">
                <div className="course-chat-scroll-area" aria-label="课程学习内容">
                  {hasDisplayedCourseMessages ? (
                    <section className="course-message-stack" aria-label="课程即时对话">
                      {displayedCourseMessages.map((message, index) => {
                        if (message.role === "user") {
                          return <article className="course-message user" key={message.id}><SecureTutorImages attachments={message.attachments ?? []} /><p>{message.content}</p></article>;
                        }

                        const isPersisted = !message.id.startsWith("course-assistant-stream-");
                        const turnPanel = activeTurnDetail?.messageId === message.id ? activeTurnDetail.panel : null;
                        const question = findQuestionForAssistant(displayedCourseMessages, index);
                        const citations = message.citations ?? [];
                        const citationKnowledgePointId = findBestCitationKnowledgePoint(citations);
                        const isLatestAssistant = !displayedCourseMessages.slice(index + 1).some((item) => item.role === "assistant");
                        const turnKnowledgePointId = recommendation.knowledge_point_id ?? citationKnowledgePointId;
                        const practiceHref = buildCourseClosureHref(
                          PATHS.practice,
                          numericCourseId,
                          selectedCourseSessionId,
                          message.id,
                          turnKnowledgePointId
                        );
                        const reportHref = buildCourseClosureHref(
                          PATHS.reports,
                          numericCourseId,
                          selectedCourseSessionId,
                          message.id
                        );
                        const pathHref = buildCourseClosureHref(
                          PATHS.path,
                          numericCourseId,
                          selectedCourseSessionId,
                          message.id,
                          turnKnowledgePointId
                        );
                        const effectiveTraceId = message.traceId
                          ?? (message.id === latestAssistantWithRetrieval?.id ? latestAgentTraceId : null);
                        const detail = turnPanel ? (
                          <>
                            {turnPanel === "resources" ? (
                              <CourseInlineResourcePanel
                                selectedTypes={selectedCourseResourceTypes}
                                isGenerating={courseResourceMutation.isPending || isGeneratingCourseResources}
                                feedback={courseResourceFeedback}
                                generatedCount={generatedResources.length}
                                generatedResources={latestGeneratedResources}
                                job={resourceJob}
                                onCancelJob={() => resourceJob && void cancelJob(resourceJob.job_id)}
                                onRetryJob={() => resourceJob && void retryJob(resourceJob.job_id).then((job) => {
                                  handledResourceJobId.current = null;
                                  setResourceJobId(job.job_id);
                                })}
                                onToggleType={toggleCourseResourceType}
                                onGenerate={submitCourseResourceGeneration}
                              />
                            ) : null}
                            <CourseAnswerDetailPanel
                              activePanel={turnPanel}
                              courseId={hasRealCourseId ? numericCourseId : null}
                              citations={citations}
                              supplementalSources={message.supplementalSources ?? []}
                              hasRealCourse={Boolean(apiCourse)}
                              hasSearched
                              pathSummary={learningState?.path_summary ?? null}
                              pathHref={pathHref}
                              agentTraceId={effectiveTraceId}
                              agentTraceEvents={agentTraceEvents}
                              agentTraceSummary={agentTraceQuery.data?.data.summary ?? null}
                              isAgentTraceLoading={agentTraceQuery.isPending && agentTraceQuery.fetchStatus !== "idle"}
                              isAgentTraceError={agentTraceQuery.isError}
                              onOpenCitation={openCitationStudy}
                            />
                          </>
                        ) : null;

                        return (
                          <CourseAssistantTurn
                            key={message.id}
                            messageId={message.id}
                            content={sanitizeCourseAnswerContent(message.content)}
                            progress={!isPersisted && courseStreamProgress ? (
                              <TutorResponseProgress state={courseStreamProgress} />
                            ) : isPersisted && (courseAnswerProgress[message.id] ?? persistedCourseAnswerProgress[message.id]) ? (
                              <TutorResponseProgress
                                state={courseAnswerProgress[message.id] ?? persistedCourseAnswerProgress[message.id]}
                                completed
                                durationMs={(courseAnswerProgress[message.id] ?? persistedCourseAnswerProgress[message.id]).durationMs}
                                storageKey={`course-message:${message.id}`}
                              />
                            ) : undefined}
                            actions={isPersisted && message.content.trim() ? (
                              <CourseClosedLoopActions
                                recommendation={isLatestAssistant ? recommendation : null}
                                citationCount={citations.length}
                                resourceCount={generatedResources.length}
                                hasTrace={Boolean(effectiveTraceId)}
                                activePanel={turnPanel}
                                isSpeaking={speech.activeSpeechId === message.id}
                                pathHref={pathHref}
                                practiceHref={practiceHref}
                                reportHref={reportHref}
                                onRecommendedAction={() => runRecommendedAction(message.id, citations, recommendation)}
                                onRead={() => toggleReadMessage(message)}
                                onOpenCitations={() => toggleTurnPanel(message.id, "citations", question, citations)}
                                onOpenResources={() => toggleTurnPanel(message.id, "resources", question, citations)}
                                onOpenWhy={() => toggleTurnPanel(message.id, "why", question, citations)}
                                onOpenTrace={() => toggleTurnPanel(message.id, "thinking", question, citations)}
                              />
                            ) : undefined}
                            detail={
                              <>
                                {message.resourceJobs?.map((job) => (
                                  <section className="tutor-resource-card" key={job.job_id} aria-label="对话生成资源">
                                    <strong>{job.status === "completed" ? "已生成学习资源" : job.status === "failed" ? "资源生成失败" : job.label}</strong>
                                    {job.resources.map((resource) => <Link key={resource.id} to={`${PATHS.studio}?course_id=${numericCourseId}&resource_id=${resource.id}`}>{resource.title}</Link>)}
                                    {job.error_message ? <small>{job.error_message}</small> : null}
                                  </section>
                                ))}
                                {message.resourceProposal && message.resourceProposal.action !== "none" && !(message.resourceJobs?.length) ? (
                                  <section className="tutor-resource-card" aria-label="学习资源建议">
                                    <strong>{message.resourceProposal.action === "generate" ? "准备生成学习资源" : "建议补充学习资源"}</strong>
                                    <small>{message.resourceProposal.reason_summary}</small>
                                    <button type="button" onClick={() => void generateSuggestedCourseResources(message)}>生成建议资源</button>
                                  </section>
                                ) : null}
                                {detail}
                              </>
                            }
                          />
                        );
                      })}
                    </section>
                  ) : (
                    <article className="course-answer course-start-panel" role="region" aria-label="课程提问引导">
                      <h2>可以从这些问题开始</h2>
                      <div className="course-question-suggestions" aria-label="推荐问题">
                        {courseStarterQuestions.map((question) => (
                          <button type="button" key={question} onClick={() => setCoursePrompt(question)}>
                            {question}
                          </button>
                        ))}
                      </div>
                    </article>
                  )}

                  {!hasDisplayedCourseMessages && hasRealCourseId ? (
                    <>
                      <NextLearningAction action={recommendation} compact />
                      <nav className="course-action-links" aria-label="课程辅助入口">
                        <Link to={buildCoursePathWorkspacePath(numericCourseId)}>
                          <MapTrifold size={17} weight="duotone" aria-hidden="true" />
                          <span>学习路径</span>
                        </Link>
                        <Link to={buildCoursePracticeWorkspacePath(numericCourseId)}>
                          <ListChecks size={17} weight="duotone" aria-hidden="true" />
                          <span>自由练习</span>
                        </Link>
                        <Link to={buildCourseReportsWorkspacePath(numericCourseId)}>
                          <ChartLineUp size={17} weight="duotone" aria-hidden="true" />
                          <span>查看报告</span>
                        </Link>
                      </nav>
                    </>
                  ) : null}
                  <div className="course-chat-end" ref={courseChatEndRef} aria-hidden="true" />
                </div>

                <div className="course-composer" role="region" aria-label="课程输入区">
                  <label htmlFor="course-question-input">课程问题输入</label>
                  <div className="conversation-composer course-conversation-composer">
                    <TutorImagePicker draft={imageDraft} compact display="previews" />
                    <textarea
                      ref={courseQuestionInputRef}
                      id="course-question-input"
                      rows={2}
                      value={coursePrompt}
                      onChange={(event) => setCoursePrompt(event.target.value)}
                      onKeyDown={handleCourseComposerKeyDown}
                      onPaste={(event) => {
                        const files = Array.from(event.clipboardData.files).filter((file) => file.type.startsWith("image/"));
                        if (files.length) { event.preventDefault(); void imageDraft.addFiles(files); }
                      }}
                      onDrop={(event) => {
                        const files = Array.from(event.dataTransfer.files).filter((file) => file.type.startsWith("image/"));
                        if (files.length) { event.preventDefault(); void imageDraft.addFiles(files); }
                      }}
                      onDragOver={(event) => event.preventDefault()}
                      placeholder="继续问这门课，例如：给我生成监督学习 10 分钟复习路线"
                    />
                    <div className="composer-actions">
                      <div className="composer-toolbar" aria-label="输入工具">
                        <TutorImagePicker draft={imageDraft} compact display="controls" />
                      </div>
                      <div className="composer-submit-row">
                        <button
                          className={speech.isListening ? "voice-button active" : "voice-button"}
                          type="button"
                          title={speech.isTranscribing ? "正在识别" : speech.isListening ? "结束录音" : "语音输入"}
                          aria-label="语音输入"
                          aria-pressed={speech.isListening}
                          disabled={speech.isTranscribing}
                          onClick={speech.toggleListening}
                        >
                          <Microphone size={18} weight="duotone" aria-hidden="true" />
                        </button>
                        <button className="ask-button" type="button" title={isSearchingCourse ? "正在回答" : "发送"} aria-label="发送" disabled={isSearchingCourse} onClick={() => void sendCourseQuestion()}>
                          <ArrowRight size={18} weight="bold" aria-hidden="true" />
                        </button>
                      </div>
                    </div>
                  </div>
                  <InlineFeedback message={courseFeedback} tone="warning" className="course-inline-feedback" />
                </div>
              </section>
            ) : (
              <CourseContentView
                courseId={numericCourseId}
                courseTitle={courseSummary.title}
                courseSessionId={selectedCourseSessionId}
                points={apiKnowledgePoints}
                masteryPoints={masteryMapQuery.data?.data.points ?? []}
                selectedPoint={selectedKnowledgePoint}
                content={knowledgePointContentQuery.data?.data ?? null}
                contentPending={knowledgePointContentQuery.isPending && knowledgePointContentQuery.fetchStatus !== "idle"}
                contentError={knowledgePointContentQuery.isError}
                selectedCitation={selectedCitation}
                guided={searchParams.get("guided") === "1"}
                view={courseContentView}
                graphScope={graphScope}
                graphChapter={graphChapter}
                graphDetailOpen={isKnowledgeDetailOpen}
                weaknesses={weaknessItems}
                recommendation={recommendation}
                currentTaskPointId={currentPathTaskPointId}
                assistantOpen={isStudyAssistantOpen}
                messages={displayedCourseMessages.map((message) => message.role === "assistant"
                  ? { ...message, content: sanitizeCourseAnswerContent(message.content) }
                  : message)}
                prompt={coursePrompt}
                isSending={isSearchingCourse}
                feedback={courseFeedback}
                isListening={speech.isListening}
                isTranscribing={speech.isTranscribing}
                isSpeaking={Boolean(speech.activeSpeechId)}
                isSpeechPaused={speech.isSpeechPaused}
                onViewChange={changeCourseContentView}
                onGraphScopeChange={changeGraphScope}
                onGraphChapterChange={changeGraphChapter}
                onGraphDetailClose={() => changeKnowledgeDetail(false)}
                onSelectPoint={openKnowledgeStudy}
                onSelectPrevious={() => {
                  const pointId = knowledgePointContentQuery.data?.data.previous_knowledge_point_id;
                  if (pointId) openKnowledgeStudy(pointId);
                }}
                onSelectNext={() => {
                  const pointId = knowledgePointContentQuery.data?.data.next_knowledge_point_id;
                  if (pointId) openKnowledgeStudy(pointId);
                }}
                onAssistantOpenChange={changeStudyAssistant}
                onPromptChange={setCoursePrompt}
                onPromptKeyDown={handleCourseComposerKeyDown}
                onSend={() => void sendCourseQuestion()}
                onToggleListening={() => void speech.toggleListening()}
                onReadLatest={() => {
                  const latest = [...displayedCourseMessages].reverse().find((message) => message.role === "assistant" && message.content.trim());
                  if (latest) toggleReadMessage(latest);
                }}
                onPauseOrResumeSpeaking={speech.pauseOrResumeSpeaking}
                onStopSpeaking={speech.stopSpeaking}
              />
            )}

            <CourseProgressDrawer
              open={isProgressDrawerOpen}
              summary={courseLoopSummary}
              steps={courseStudySteps}
              traceId={fallbackCourse?.agent_trace_id}
              weaknessSummary={weaknessSummary}
              learnerContext={learningState?.learner_context}
              weaknessItems={weaknessItems}
              updatingWeaknessItemId={updatingWeaknessItemId}
              learningStateError={learningStateQuery.isError && learningStateQuery.data === undefined}
              weaknessFeedback={weaknessFeedback}
              isRefreshing={isProgressSyncing}
              refreshWarning={progressSyncWarning}
              onClose={() => setIsProgressDrawerOpen(false)}
              onRefresh={() => void syncCourseProgress()}
              onWeaknessAction={(item, action) => void updateWeaknessReviewItem(item, action)}
              onPracticeWeakness={(item) => {
                const params = new URLSearchParams({
                  course_id: String(numericCourseId),
                  knowledge_point_id: item.knowledge_point_id ?? "",
                  weakness_item_id: item.id,
                  new: "1"
                });
                navigate(`${buildCoursePracticeWorkspacePath(numericCourseId)}?${params.toString()}`);
              }}
              onOpenWeaknessResource={(item, resourceId) => {
                const params = new URLSearchParams({
                  course_id: String(numericCourseId),
                  knowledge_point_id: item.knowledge_point_id ?? "",
                  learning_goal: item.diagnosis?.recommended_action || `复习并掌握${item.title}`
                });
                if (resourceId) params.set("resource_id", resourceId);
                navigate(`${PATHS.studio}?${params.toString()}`);
              }}
            />
          </div>
        </section>
      </section>
    </LearningSpaceShell>
  );
}

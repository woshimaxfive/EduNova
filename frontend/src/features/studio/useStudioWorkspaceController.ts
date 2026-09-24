import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { getAgentTrace, mapAgentTraceStepToEvent } from "../../api/agents";
import type { AiJob } from "../../api/aiJobs";
import { getCourseLearningState, getKnowledgePoints, getMasteryMap, listCourses } from "../../api/courses";
import { getPathTask } from "../../api/paths";
import {
  deleteResource,
  getResourceQuality,
  listResources,
  type GeneratedResource,
  type ResourceDifficulty,
  type ResourceType
} from "../../api/resources";
import type { StudioDetailTab } from "../../components/studio/StudioDrawer";
import { groupResourceVersions } from "../../components/studio/studioResourceVersions";
import { courseLoopQueryKeys, invalidateCourseLearningLoop } from "../course-space/courseLoopQueries";
import { useLearningNextAction } from "../learning-actions/learningActions";
import { useCourseMentorConversation } from "../tutor/useCourseMentorConversation";
import { useStudioResourceGeneration } from "./useStudioResourceGeneration";

function parsePositiveId(value: string | null) {
  if (!value) return null;
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

export function useStudioWorkspaceController() {
  const [searchParams, setSearchParams] = useSearchParams();
  const queryClient = useQueryClient();
  const initialCourseId = parsePositiveId(searchParams.get("course_id"));
  const initialResourceId = searchParams.get("resource_id");
  const initialKnowledgePointId = parsePositiveId(searchParams.get("knowledge_point_id"));
  const initialLearningGoal = searchParams.get("learning_goal") ?? "";
  const pathTaskId = searchParams.get("path_task_id");
  const requestedCourseSessionId = searchParams.get("course_session_id");
  const mentorOpen = searchParams.get("mentor") === "open";
  const numericPathTaskId = parsePositiveId(pathTaskId);
  const [selectedCourseId, setSelectedCourseId] = useState<number | null>(initialCourseId);
  const [selectedKnowledgePointId, setSelectedKnowledgePointId] = useState<number | null>(initialKnowledgePointId);
  const [selectedResourceId, setSelectedResourceId] = useState<string | null>(initialResourceId);
  const [selectedResourceTypes, setSelectedResourceTypes] = useState<ResourceType[]>(["doc"]);
  const [learningGoal, setLearningGoal] = useState(initialLearningGoal);
  const [difficulty, setDifficulty] = useState<ResourceDifficulty>("medium");
  const [librarySearch, setLibrarySearch] = useState("");
  const [resourceTypeFilter, setResourceTypeFilter] = useState<"all" | ResourceType>("all");
  const [detailTab, setDetailTab] = useState<StudioDetailTab>("quality");
  const [compareDialogOpen, setCompareDialogOpen] = useState(false);
  const [resourcePendingDeletion, setResourcePendingDeletion] = useState<GeneratedResource | null>(null);
  const [isDeletingResource, setIsDeletingResource] = useState(false);

  const coursesQuery = useQuery({
    queryKey: ["courses", "studio"],
    queryFn: () => listCourses(),
    staleTime: 30_000
  });
  const courses = useMemo(
    () => (Array.isArray(coursesQuery.data?.data) ? coursesQuery.data.data : []),
    [coursesQuery.data]
  );
  const effectiveCourseId = useMemo(() => {
    if (courses.length === 0) return null;
    if (selectedCourseId !== null && courses.some((course) => Number(course.id) === selectedCourseId)) {
      return selectedCourseId;
    }
    if (initialCourseId !== null && courses.some((course) => Number(course.id) === initialCourseId)) {
      return initialCourseId;
    }
    const currentCourse = courses.find((course) => course.is_current && course.learning_status !== "archived");
    const firstActiveCourse = courses.find((course) => course.learning_status !== "archived");
    return Number.parseInt((currentCourse ?? firstActiveCourse ?? courses[0]).id, 10);
  }, [courses, initialCourseId, selectedCourseId]);
  const selectedCourse = courses.find((course) => Number(course.id) === effectiveCourseId) ?? null;

  const knowledgePointsQuery = useQuery({
    queryKey: ["courses", "knowledge-points", effectiveCourseId],
    queryFn: () => getKnowledgePoints(effectiveCourseId ?? 0),
    enabled: effectiveCourseId !== null,
    staleTime: 30_000
  });
  const knowledgePoints = useMemo(
    () => (Array.isArray(knowledgePointsQuery.data?.data) ? knowledgePointsQuery.data.data : []),
    [knowledgePointsQuery.data]
  );
  const effectiveKnowledgePointId = useMemo(() => {
    if (knowledgePoints.length === 0) return null;
    if (
      selectedKnowledgePointId !== null
      && knowledgePoints.some((point) => Number(point.id) === selectedKnowledgePointId)
    ) {
      return selectedKnowledgePointId;
    }
    return Number.parseInt(knowledgePoints[0].id, 10);
  }, [knowledgePoints, selectedKnowledgePointId]);

  const resourcesQuery = useQuery({
    queryKey: effectiveCourseId !== null ? courseLoopQueryKeys.resources(effectiveCourseId) : ["resources", "all"],
    queryFn: () => listResources(effectiveCourseId !== null ? { courseId: effectiveCourseId } : undefined),
    enabled: effectiveCourseId !== null,
    staleTime: 10_000
  });
  const resources = useMemo(
    () => (
      Array.isArray(resourcesQuery.data?.data)
        ? [...resourcesQuery.data.data].sort((left, right) => right.created_at.localeCompare(left.created_at))
        : []
    ),
    [resourcesQuery.data]
  );
  const currentPathQuery = useQuery({
    queryKey: ["paths", "task", numericPathTaskId],
    queryFn: () => getPathTask(numericPathTaskId ?? 0),
    enabled: effectiveCourseId !== null && numericPathTaskId !== null,
    staleTime: 5_000
  });
  const pathTask = currentPathQuery.data?.data.course_id === String(effectiveCourseId) ? currentPathQuery.data.data : null;
  const bundleItems = pathTask?.learning_bundle?.items ?? [];
  const preferredBundleResourceId = bundleItems.find(
    (item) => item.resource_id && item.learning_status !== "completed"
  )?.resource_id ?? bundleItems.find((item) => item.resource_id)?.resource_id ?? null;
  const requestedResourceId = selectedResourceId ?? preferredBundleResourceId;
  const selectedResource = numericPathTaskId !== null
    ? resources.find((resource) => resource.id === requestedResourceId && bundleItems.some((item) => item.resource_id === resource.id)) ?? null
    : selectedResourceId !== null
      ? resources.find((resource) => resource.id === selectedResourceId) ?? null
      : resources[0] ?? null;
  const selectedBundleIndex = bundleItems.findIndex((item) => item.resource_id === selectedResource?.id);
  const selectedBundleItem = selectedBundleIndex >= 0 ? bundleItems[selectedBundleIndex] : null;
  const nextBundleItem = selectedBundleIndex >= 0
    ? bundleItems.slice(selectedBundleIndex + 1).find(
        (item) => item.resource_id && item.learning_status !== "completed"
      )
    : bundleItems.find((item) => item.resource_id && item.learning_status !== "completed");
  const resourceFamilies = useMemo(() => groupResourceVersions(resources), [resources]);
  const selectedFamily = useMemo(
    () => resourceFamilies.find(
      (family) => family.versions.some((resource) => resource.id === selectedResource?.id)
    ) ?? null,
    [resourceFamilies, selectedResource?.id]
  );
  const selectedVersions = selectedFamily?.versions ?? (selectedResource ? [selectedResource] : []);
  const filteredFamilies = useMemo(() => {
    const keyword = librarySearch.trim().toLocaleLowerCase("zh-CN");
    return resourceFamilies.filter((family) => {
      const matchesType = resourceTypeFilter === "all" || family.latest.resource_type === resourceTypeFilter;
      const matchesSearch = !keyword || family.versions.some(
        (resource) => resource.title.toLocaleLowerCase("zh-CN").includes(keyword)
      );
      return matchesType && matchesSearch;
    });
  }, [librarySearch, resourceFamilies, resourceTypeFilter]);

  const selectedResourceKnowledgePointTitle = selectedResource?.knowledge_point_id
    ? knowledgePoints.find((point) => point.id === selectedResource.knowledge_point_id)?.title ?? "课程知识点"
    : "整门课程";

  useEffect(() => {
    if (!selectedResource || selectedResource.id === selectedResourceId) return;
    // Lock the first path-planned selection so later progress refreshes do not skip ahead automatically.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setSelectedResourceId(selectedResource.id);
    const next = new URLSearchParams(searchParams);
    if (effectiveCourseId !== null) next.set("course_id", String(effectiveCourseId));
    next.set("resource_id", selectedResource.id);
    setSearchParams(next, { replace: true });
  }, [effectiveCourseId, searchParams, selectedResource, selectedResourceId, setSearchParams]);

  const restoreGenerationRequest = useCallback((request: AiJob["request"]) => {
    if (Number.isFinite(Number(request.course_id))) setSelectedCourseId(Number(request.course_id));
    if (request.knowledge_point_id !== null && Number.isFinite(Number(request.knowledge_point_id))) {
      setSelectedKnowledgePointId(Number(request.knowledge_point_id));
    }
    if (Array.isArray(request.resource_types)) setSelectedResourceTypes(request.resource_types as ResourceType[]);
    if (typeof request.learning_goal === "string") setLearningGoal(request.learning_goal);
    if (["easy", "medium", "hard"].includes(String(request.difficulty))) {
      setDifficulty(request.difficulty as ResourceDifficulty);
    }
    if (Number.isFinite(Number(request.source_resource_id))) {
      setSelectedResourceId(String(request.source_resource_id));
    }
  }, []);

  const completeGeneration = useCallback(async (completedCourseId: number, resourceIds: string[]) => {
    if (completedCourseId !== effectiveCourseId) return false;
    const refreshed = await resourcesQuery.refetch();
    const refreshedResources = Array.isArray(refreshed.data?.data) ? refreshed.data.data : [];
    const nextResource = resourceIds
      .map((id) => refreshedResources.find((resource) => resource.id === id))
      .find(Boolean);
    if (nextResource) {
      setSelectedResourceId(nextResource.id);
      const next = new URLSearchParams(searchParams);
      next.set("course_id", String(completedCourseId));
      next.set("resource_id", nextResource.id);
      setSearchParams(next, { replace: true });
    }
    return true;
  }, [effectiveCourseId, resourcesQuery, searchParams, setSearchParams]);

  const generation = useStudioResourceGeneration({
    courseId: effectiveCourseId,
    difficulty,
    initialCourseId,
    knowledgePointId: effectiveKnowledgePointId,
    learningGoal,
    numericPathTaskId,
    onCompleted: completeGeneration,
    onRestoreRequest: restoreGenerationRequest,
    pathTaskId,
    resource: selectedResource,
    selectedTypes: selectedResourceTypes
  });

  const masteryQuery = useQuery({
    queryKey: courseLoopQueryKeys.masteryMap(effectiveCourseId ?? 0),
    queryFn: () => getMasteryMap(effectiveCourseId ?? 0),
    enabled: effectiveCourseId !== null,
    staleTime: 10_000
  });
  const learningStateQuery = useQuery({
    queryKey: courseLoopQueryKeys.learningState(effectiveCourseId ?? 0),
    queryFn: () => getCourseLearningState(effectiveCourseId ?? 0),
    enabled: effectiveCourseId !== null,
    staleTime: 10_000
  });
  const updateMentorSession = useCallback((sessionId: string) => {
    setSearchParams((current) => {
      const next = new URLSearchParams(current);
      next.set("course_session_id", sessionId);
      return next;
    }, { replace: true });
  }, [setSearchParams]);
  const mentor = useCourseMentorConversation({
    courseId: effectiveCourseId,
    requestedSessionId: requestedCourseSessionId,
    contextResourceId: selectedResource ? Number.parseInt(selectedResource.id, 10) : null,
    enabled: mentorOpen,
    onSessionChange: updateMentorSession
  });
  const selectedMastery = masteryQuery.data?.data?.points?.find(
    (point) => point.id === selectedResource?.knowledge_point_id
  ) ?? null;
  const selectedWeaknessCount = (learningStateQuery.data?.data?.weakness_review_queue ?? []).filter(
    (item) => item.knowledge_point_id === selectedResource?.knowledge_point_id
      && ["pending", "confirmed", "reviewing"].includes(item.status)
  ).length;
  const selectedResourceTraceId = selectedResource?.agent_trace_id
    ?? selectedResource?.content_json.metadata?.agent_trace_id
    ?? null;
  const resourceQualityQuery = useQuery({
    queryKey: ["resources", "quality", selectedResource?.id],
    queryFn: () => getResourceQuality(Number.parseInt(selectedResource?.id ?? "0", 10)),
    enabled: generation.drawerMode === "details" && detailTab === "quality" && selectedResource !== null,
    staleTime: 10_000
  });
  const resourceTraceQuery = useQuery({
    queryKey: ["agents", "trace", selectedResourceTraceId],
    queryFn: () => getAgentTrace(selectedResourceTraceId ?? ""),
    enabled: generation.drawerMode === "details" && detailTab === "trace" && Boolean(selectedResourceTraceId),
    staleTime: 30_000
  });
  const resourceTraceEvents = useMemo(
    () => resourceTraceQuery.data?.data.steps?.map(mapAgentTraceStepToEvent) ?? [],
    [resourceTraceQuery.data?.data.steps]
  );

  function setUrlSelection(courseId: number | null, resourceId?: string | null) {
    const next = new URLSearchParams(searchParams);
    if (courseId === null) next.delete("course_id");
    else next.set("course_id", String(courseId));
    if (resourceId) next.set("resource_id", resourceId);
    else next.delete("resource_id");
    if (pathTaskId && !bundleItems.some((item) => item.resource_id === resourceId)) {
      next.delete("path_task_id");
    }
    setSearchParams(next, { replace: true });
  }

  function handleCourseChange(courseId: number | null) {
    setSelectedCourseId(courseId);
    setSelectedKnowledgePointId(null);
    setSelectedResourceId(null);
    setLibrarySearch("");
    setResourceTypeFilter("all");
    generation.clearFeedback();
    setDetailTab("quality");
    const next = new URLSearchParams(searchParams);
    if (courseId === null) next.delete("course_id");
    else next.set("course_id", String(courseId));
    next.delete("resource_id");
    next.delete("path_task_id");
    next.delete("course_session_id");
    next.delete("mentor");
    setSearchParams(next, { replace: true });
  }

  function selectResource(resourceId: string) {
    generation.clearFeedback();
    setSelectedResourceId(resourceId);
    setUrlSelection(effectiveCourseId, resourceId);
  }

  async function handleDeleteResource() {
    if (!resourcePendingDeletion || isDeletingResource) return;
    const resource = resourcePendingDeletion;
    setIsDeletingResource(true);
    try {
      await deleteResource(Number(resource.id));
      const remaining = resources.filter((item) => item.id !== resource.id);
      const nextResource = remaining[0] ?? null;
      setResourcePendingDeletion(null);
      generation.closeDrawer();
      setCompareDialogOpen(false);
      setSelectedResourceId(nextResource?.id ?? null);
      setUrlSelection(effectiveCourseId, nextResource?.id ?? null);
      if (effectiveCourseId !== null) await invalidateCourseLearningLoop(queryClient, effectiveCourseId);
      await resourcesQuery.refetch();
    } catch {
      generation.reportFailure("资源删除失败，请稍后再试。");
    } finally {
      setIsDeletingResource(false);
    }
  }

  function toggleResourceType(type: ResourceType) {
    setSelectedResourceTypes((current) => {
      if (current.includes(type)) {
        return current.length === 1 ? current : current.filter((item) => item !== type);
      }
      return [...current, type];
    });
  }

  function changeMentorOpen(open: boolean) {
    if (!open) {
      mentor.speech.stopListening();
      mentor.speech.stopSpeaking();
    }
    const next = new URLSearchParams(searchParams);
    if (open) {
      next.set("mentor", "open");
      if (mentor.selectedSessionId) next.set("course_session_id", mentor.selectedSessionId);
    } else {
      next.delete("mentor");
    }
    setSearchParams(next, { replace: true });
  }

  function retryWorkspaceData() {
    void coursesQuery.refetch();
    void resourcesQuery.refetch();
    if (numericPathTaskId !== null) void currentPathQuery.refetch();
  }

  const dataError = coursesQuery.isError || resourcesQuery.isError
    || (numericPathTaskId !== null && (currentPathQuery.isError || (!currentPathQuery.isPending && !selectedResource)))
    || (selectedResourceId !== null && !resourcesQuery.isPending && !selectedResource);
  const nextActionQuery = useLearningNextAction(effectiveCourseId);
  const resourcesLoading = effectiveCourseId !== null && resourcesQuery.isPending && resources.length === 0;

  return {
    artifact: {
      dataError,
      isLoading: coursesQuery.isPending || resourcesLoading,
      knowledgePointTitle: selectedResourceKnowledgePointTitle,
      resource: selectedResource,
      retry: retryWorkspaceData,
      versions: selectedVersions
    },
    course: {
      change: handleCourseChange,
      changeKnowledgePoint: setSelectedKnowledgePointId,
      id: effectiveCourseId,
      items: courses,
      knowledgePointId: effectiveKnowledgePointId,
      knowledgePoints,
      selected: selectedCourse
    },
    deletion: {
      cancel: () => setResourcePendingDeletion(null),
      confirm: handleDeleteResource,
      isDeleting: isDeletingResource,
      pending: resourcePendingDeletion,
      setPending: setResourcePendingDeletion
    },
    dialogs: {
      closeCompare: () => setCompareDialogOpen(false),
      closeRegenerate: generation.closeRegenerateDialog,
      compareOpen: compareDialogOpen,
      openCompare: () => setCompareDialogOpen(true),
      openRegenerate: generation.openRegenerateDialog,
      regenerateOpen: generation.regenerateDialogOpen
    },
    drawer: {
      cancelJob: generation.cancelJob,
      canGenerate: generation.canGenerate,
      changeDetailTab: setDetailTab,
      changeDifficulty: setDifficulty,
      changeLearningGoal: setLearningGoal,
      close: generation.closeDrawer,
      deleteJob: generation.deleteCurrentJob,
      detailTab,
      difficulty,
      feedback: generation.drawerMode === "generate" ? generation.feedback : null,
      generate: generation.generate,
      isGenerating: generation.isGenerating || generation.mutationPending,
      learningGoal,
      mode: generation.drawerMode,
      openDetails: generation.openDetails,
      openGenerate: generation.openGenerate,
      qualityScores: resourceQualityQuery.data?.data ?? [],
      retryJob: generation.retryCurrentJob,
      selectedTypes: selectedResourceTypes,
      toggleResourceType,
      traceError: resourceTraceQuery.isError,
      traceEvents: resourceTraceEvents,
      traceId: selectedResourceTraceId,
      traceLoading: resourceTraceQuery.isPending && resourceTraceQuery.fetchStatus !== "idle"
    },
    generation: {
      cancelJob: generation.cancelJob,
      feedback: generation.feedback,
      feedbackTone: generation.feedbackTone,
      isGenerating: generation.isGenerating,
      job: generation.job,
      mutationPending: generation.mutationPending,
      regenerate: generation.regenerate,
      showCompactJob: generation.showCompactJob
    },
    library: {
      changeSearch: setLibrarySearch,
      changeTypeFilter: setResourceTypeFilter,
      families: filteredFamilies,
      isLoading: resourcesLoading,
      search: librarySearch,
      selectResource,
      typeFilter: resourceTypeFilter
    },
    mentor: {
      changeOpen: changeMentorOpen,
      controller: mentor,
      masteryScore: selectedMastery?.score ?? null,
      open: mentorOpen,
      weaknessCount: selectedWeaknessCount
    },
    nextAction: {
      error: nextActionQuery.isError,
      isLoading: nextActionQuery.isPending,
      value: nextActionQuery.data?.data
    },
    path: {
      nextBundleItem,
      pathTask,
      pathTaskId,
      selectedBundleItem
    },
    resourceFamilies,
    selectResource,
    selectedResource,
    selectedVersions
  };
}

export type StudioWorkspaceController = ReturnType<typeof useStudioWorkspaceController>;

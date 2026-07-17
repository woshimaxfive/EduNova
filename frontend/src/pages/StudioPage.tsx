import { ArrowClockwise, CheckCircle, X } from "@phosphor-icons/react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { getAgentTrace, mapAgentTraceStepToEvent } from "../api/agents";
import { createIdempotencyKey, createResourceGenerationJob } from "../api/aiJobs";
import { getKnowledgePoints, listCourses } from "../api/courses";
import { getCurrentPath } from "../api/paths";
import {
  getResourceQuality,
  listResources,
  type GeneratedResource,
  type ResourceDifficulty,
  type ResourceGenerationAction,
  type ResourceType
} from "../api/resources";
import { InlineFeedback, type FeedbackTone } from "../components/feedback/InlineFeedback";
import { NextLearningAction } from "../components/learning/NextLearningAction";
import { StudioArtifactCanvas } from "../components/studio/StudioArtifactCanvas";
import {
  StudioDrawer,
  type StudioDetailTab,
  type StudioDrawerMode
} from "../components/studio/StudioDrawer";
import { StudioResourceLibrary } from "../components/studio/StudioResourceLibrary";
import { StudioWorkspaceToolbar } from "../components/studio/StudioWorkspaceToolbar";
import { StudioRegenerateDialog, StudioVersionCompareDialog } from "../components/studio/StudioVersionDialogs";
import { groupResourceVersions } from "../components/studio/studioResourceVersions";
import { courseLoopQueryKeys, invalidateCourseLearningLoop } from "../features/course-space/courseLoopQueries";
import { useAiJobs } from "../features/aiJobs/AiJobProvider";
import { useLearningNextAction } from "../features/learning-actions/learningActions";
import { PageFrame } from "./PageFrame";
import { PATHS } from "../app/routePaths";
import "../styles/studio.css";

function parsePositiveId(value: string | null) {
  if (!value) return null;
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

export function StudioPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const queryClient = useQueryClient();
  const initialCourseId = parsePositiveId(searchParams.get("course_id"));
  const initialResourceId = searchParams.get("resource_id");
  const initialKnowledgePointId = parsePositiveId(searchParams.get("knowledge_point_id"));
  const initialLearningGoal = searchParams.get("learning_goal") ?? "";
  const pathTaskId = searchParams.get("path_task_id");
  const numericPathTaskId = parsePositiveId(pathTaskId);
  const [selectedCourseId, setSelectedCourseId] = useState<number | null>(initialCourseId);
  const [selectedKnowledgePointId, setSelectedKnowledgePointId] = useState<number | null>(initialKnowledgePointId);
  const [selectedResourceId, setSelectedResourceId] = useState<string | null>(initialResourceId);
  const [selectedResourceTypes, setSelectedResourceTypes] = useState<ResourceType[]>(["doc"]);
  const [learningGoal, setLearningGoal] = useState(initialLearningGoal);
  const [difficulty, setDifficulty] = useState<ResourceDifficulty>("medium");
  const [librarySearch, setLibrarySearch] = useState("");
  const [resourceTypeFilter, setResourceTypeFilter] = useState<"all" | ResourceType>("all");
  const [drawerMode, setDrawerMode] = useState<StudioDrawerMode>(null);
  const [detailTab, setDetailTab] = useState<StudioDetailTab>("quality");
  const [feedback, setFeedback] = useState<string | null>(null);
  const [feedbackTone, setFeedbackTone] = useState<FeedbackTone>("info");
  const [resourceJobId, setResourceJobId] = useState<string | null>(null);
  const [regenerateDialogOpen, setRegenerateDialogOpen] = useState(false);
  const [compareDialogOpen, setCompareDialogOpen] = useState(false);
  const handledCompletedJobIds = useRef(new Set<string>());
  const { jobs, trackJob, getJob, cancelJob, retryJob, deleteJob } = useAiJobs();
  const resourceJob = getJob(resourceJobId);
  const isGenerating = Boolean(resourceJob && ["queued", "running", "cancelling"].includes(resourceJob.status));

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
    if (selectedCourseId !== null && courses.some((course) => Number(course.id) === selectedCourseId)) return selectedCourseId;
    if (initialCourseId !== null && courses.some((course) => Number(course.id) === initialCourseId)) return initialCourseId;
    return Number.parseInt(courses[0].id, 10);
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
    if (selectedKnowledgePointId !== null && knowledgePoints.some((point) => Number(point.id) === selectedKnowledgePointId)) {
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
    () => (Array.isArray(resourcesQuery.data?.data) ? [...resourcesQuery.data.data].sort((left, right) => right.created_at.localeCompare(left.created_at)) : []),
    [resourcesQuery.data]
  );
  const currentPathQuery = useQuery({
    queryKey: courseLoopQueryKeys.currentPath(effectiveCourseId ?? 0),
    queryFn: () => getCurrentPath(effectiveCourseId ?? 0),
    enabled: effectiveCourseId !== null && numericPathTaskId !== null,
    staleTime: 5_000
  });
  const pathTask = currentPathQuery.data?.data.tasks.find((task) => Number(task.id) === numericPathTaskId) ?? null;
  const bundleItems = pathTask?.learning_bundle?.items ?? [];
  const preferredBundleResourceId = bundleItems.find((item) => item.resource_id && item.learning_status !== "completed")?.resource_id
    ?? bundleItems.find((item) => item.resource_id)?.resource_id
    ?? null;
  const selectedResource = resources.find((resource) => resource.id === selectedResourceId)
    ?? resources.find((resource) => resource.id === preferredBundleResourceId)
    ?? resources[0]
    ?? null;
  const selectedBundleIndex = bundleItems.findIndex((item) => item.resource_id === selectedResource?.id);
  const selectedBundleItem = selectedBundleIndex >= 0 ? bundleItems[selectedBundleIndex] : null;
  const nextBundleItem = selectedBundleIndex >= 0
    ? bundleItems.slice(selectedBundleIndex + 1).find((item) => item.resource_id && item.learning_status !== "completed")
    : bundleItems.find((item) => item.resource_id && item.learning_status !== "completed");
  const resourceFamilies = useMemo(() => groupResourceVersions(resources), [resources]);
  const selectedFamily = useMemo(
    () => resourceFamilies.find((family) => family.versions.some((resource) => resource.id === selectedResource?.id)) ?? null,
    [resourceFamilies, selectedResource?.id]
  );
  const selectedVersions = selectedFamily?.versions ?? (selectedResource ? [selectedResource] : []);
  const filteredFamilies = useMemo(() => {
    const keyword = librarySearch.trim().toLocaleLowerCase("zh-CN");
    return resourceFamilies.filter((family) => {
      const matchesType = resourceTypeFilter === "all" || family.latest.resource_type === resourceTypeFilter;
      const matchesSearch = !keyword || family.versions.some((resource) => resource.title.toLocaleLowerCase("zh-CN").includes(keyword));
      return matchesType && matchesSearch;
    });
  }, [librarySearch, resourceFamilies, resourceTypeFilter]);

  const selectedResourceKnowledgePointTitle = selectedResource?.knowledge_point_id
    ? knowledgePoints.find((point) => point.id === selectedResource.knowledge_point_id)?.title ?? "课程知识点"
    : "整门课程";
  const selectedResourceTraceId = selectedResource?.agent_trace_id ?? selectedResource?.content_json.metadata?.agent_trace_id ?? null;
  const resourceQualityQuery = useQuery({
    queryKey: ["resources", "quality", selectedResource?.id],
    queryFn: () => getResourceQuality(Number.parseInt(selectedResource?.id ?? "0", 10)),
    enabled: drawerMode === "details" && detailTab === "quality" && selectedResource !== null,
    staleTime: 10_000
  });
  const resourceTraceQuery = useQuery({
    queryKey: ["agents", "trace", selectedResourceTraceId],
    queryFn: () => getAgentTrace(selectedResourceTraceId ?? ""),
    enabled: drawerMode === "details" && detailTab === "trace" && Boolean(selectedResourceTraceId),
    staleTime: 30_000
  });
  const resourceTraceEvents = useMemo(
    () => resourceTraceQuery.data?.data.steps?.map(mapAgentTraceStepToEvent) ?? [],
    [resourceTraceQuery.data?.data.steps]
  );

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

  useEffect(() => {
    if (resourceJobId) return;
    const restored = jobs.find((job) => {
      const requestCourseId = Number(job.request.course_id);
      return job.workflow === "resource_generation"
        && ["queued", "running", "cancelling", "failed"].includes(job.status)
        && (initialCourseId === null || requestCourseId === initialCourseId)
        && (numericPathTaskId === null || Number(job.request.path_task_id) === numericPathTaskId);
    });
    if (!restored) return;
    const request = restored.request;
    // Restore durable server state after navigation or refresh.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (Number.isFinite(Number(request.course_id))) setSelectedCourseId(Number(request.course_id));
    if (request.knowledge_point_id !== null && Number.isFinite(Number(request.knowledge_point_id))) setSelectedKnowledgePointId(Number(request.knowledge_point_id));
    if (Array.isArray(request.resource_types)) setSelectedResourceTypes(request.resource_types as ResourceType[]);
    if (typeof request.learning_goal === "string") setLearningGoal(request.learning_goal);
    if (["easy", "medium", "hard"].includes(String(request.difficulty))) setDifficulty(request.difficulty as ResourceDifficulty);
    if (Number.isFinite(Number(request.source_resource_id))) setSelectedResourceId(String(request.source_resource_id));
    setResourceJobId(restored.job_id);
    if (restored.status === "failed") {
      if (request.generation_action === "alternative" || request.generation_action === "refine") setRegenerateDialogOpen(true);
      else setDrawerMode("generate");
    }
  }, [initialCourseId, jobs, numericPathTaskId, resourceJobId]);

  useEffect(() => {
    if (!resourceJob) return;
    if (resourceJob.status === "failed") {
      // Keep the failure visible without forcing a drawer the user has closed to reopen.
      // Initial page restoration is handled once by the effect above.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setFeedbackTone("warning");
      setFeedback(resourceJob.error_message ?? "资源生成失败，请稍后重试。");
      return;
    }
    if (resourceJob.status !== "completed" || handledCompletedJobIds.current.has(resourceJob.job_id)) return;
    handledCompletedJobIds.current.add(resourceJob.job_id);
    const resourceIds = Array.isArray(resourceJob.result.resource_ids) ? resourceJob.result.resource_ids.map(String) : [];
    setFeedbackTone(resourceJob.warnings.length > 0 ? "warning" : "success");
    setFeedback(resourceJob.warnings.join(" ") || "资源生成完成。");
    void (async () => {
      const completedCourseId = Number(resourceJob.request.course_id ?? resourceJob.course_id);
      if (Number.isFinite(completedCourseId) && completedCourseId > 0) {
        await invalidateCourseLearningLoop(queryClient, completedCourseId);
      }
      if (completedCourseId !== effectiveCourseId) return;
      const refreshed = await resourcesQuery.refetch();
      const refreshedResources = Array.isArray(refreshed.data?.data) ? refreshed.data.data : [];
      const nextResource = resourceIds.map((id) => refreshedResources.find((resource) => resource.id === id)).find(Boolean);
      if (nextResource) {
        setSelectedResourceId(nextResource.id);
        const next = new URLSearchParams(searchParams);
        next.set("course_id", String(completedCourseId));
        next.set("resource_id", nextResource.id);
        setSearchParams(next, { replace: true });
      }
      setDrawerMode(null);
    })();
  }, [effectiveCourseId, queryClient, resourceJob, resourcesQuery, searchParams, setSearchParams]);

  const generateMutation = useMutation({
    mutationFn: ({ action, source }: { action: ResourceGenerationAction; source?: GeneratedResource }) => {
      if (effectiveCourseId === null) throw new Error("missing course");
      const sourceIntent = source?.intent_summary ?? source?.content_json.intent;
      const sourceDifficulty = source?.content_json.metadata?.difficulty;
      return createResourceGenerationJob(
        {
          course_id: effectiveCourseId,
          knowledge_point_id: source?.knowledge_point_id ? Number(source.knowledge_point_id) : effectiveKnowledgePointId,
          resource_types: source ? [source.resource_type] : selectedResourceTypes,
          learning_goal: source ? sourceIntent?.learning_goal ?? learningGoal : learningGoal,
          difficulty: sourceDifficulty ?? difficulty,
          generation_action: action,
          source_resource_id: source ? Number(source.id) : null,
          ...(pathTaskId && /^\d+$/.test(pathTaskId) ? { path_task_id: Number.parseInt(pathTaskId, 10) } : {})
        },
        createIdempotencyKey("studio-resource")
      );
    },
    onSuccess: (job) => {
      setFeedback(null);
      setResourceJobId(job.job_id);
      trackJob(job);
      setRegenerateDialogOpen(false);
    },
    onError: (_error, variables) => {
      setFeedbackTone("warning");
      setFeedback("资源生成失败，请稍后重试。");
      if (variables.action === "new") setDrawerMode("generate");
      else setRegenerateDialogOpen(true);
    }
  });

  function setUrlSelection(courseId: number | null, resourceId?: string | null) {
    const next = new URLSearchParams(searchParams);
    if (courseId === null) next.delete("course_id");
    else next.set("course_id", String(courseId));
    if (resourceId) next.set("resource_id", resourceId);
    else next.delete("resource_id");
    setSearchParams(next, { replace: true });
  }

  function handleCourseChange(courseId: number | null) {
    setSelectedCourseId(courseId);
    setSelectedKnowledgePointId(null);
    setSelectedResourceId(null);
    setLibrarySearch("");
    setResourceTypeFilter("all");
    setFeedback(null);
    setDetailTab("quality");
    setUrlSelection(courseId, null);
  }

  function selectResource(resourceId: string) {
    setSelectedResourceId(resourceId);
    setUrlSelection(effectiveCourseId, resourceId);
  }

  function toggleResourceType(type: ResourceType) {
    setSelectedResourceTypes((current) => {
      if (current.includes(type)) return current.length === 1 ? current : current.filter((item) => item !== type);
      return [...current, type];
    });
  }

  function handleGenerate() {
    if (effectiveCourseId === null || generateMutation.isPending || isGenerating || selectedResourceTypes.length === 0) return;
    generateMutation.mutate({ action: "new" });
  }

  function handleRegenerate(action: Exclude<ResourceGenerationAction, "new">) {
    if (!selectedResource || generateMutation.isPending || isGenerating) return;
    generateMutation.mutate({ action, source: selectedResource });
  }

  async function handleRetryJob() {
    if (!resourceJob) return;
    const job = await retryJob(resourceJob.job_id);
    setFeedback(null);
    setResourceJobId(job.job_id);
  }

  async function handleDeleteJob() {
    if (!resourceJob || !["failed", "cancelled"].includes(resourceJob.status)) return;
    try {
      await deleteJob(resourceJob.job_id);
      setResourceJobId(null);
      setFeedbackTone("info");
      setFeedback("失败任务已删除。你可以调整设置后重新生成。");
      setDrawerMode(null);
      setRegenerateDialogOpen(false);
    } catch {
      setFeedbackTone("warning");
      setFeedback("任务删除失败，请稍后重试。");
    }
  }

  const canGenerate = effectiveCourseId !== null
    && selectedResourceTypes.length > 0
    && !generateMutation.isPending
    && !isGenerating;
  const showCompactJob = resourceJob && ["queued", "running", "cancelling"].includes(resourceJob.status);
  const dataError = coursesQuery.isError || resourcesQuery.isError;
  const nextActionQuery = useLearningNextAction(effectiveCourseId);

  return (
    <>
      <PageFrame title="资源工坊" titleMode="sr-only" variant="wide-workspace">
        <section className="studio-workspace" aria-label="资源成果工作台">
          <StudioWorkspaceToolbar
            courses={courses}
            courseId={effectiveCourseId}
            resourceCount={resourceFamilies.length}
            selectedResource={selectedResource}
            isGenerating={isGenerating}
            onCourseChange={handleCourseChange}
            onOpenGenerate={() => setDrawerMode("generate")}
            onOpenDetails={() => setDrawerMode("details")}
            onRegenerate={() => setRegenerateDialogOpen(true)}
          />

          {showCompactJob ? (
            <section className="studio-job-strip" role="status" aria-label="资源生成进度">
              <ArrowClockwise className="spinning" size={17} aria-hidden="true" />
              <div><strong>{resourceJob.label}</strong><span>{resourceJob.stage} · {resourceJob.progress_percent}%</span></div>
              <progress max="100" value={resourceJob.progress_percent}>{resourceJob.progress_percent}%</progress>
              <button type="button" onClick={() => void cancelJob(resourceJob.job_id)}><X size={15} /><span>取消</span></button>
            </section>
          ) : null}
          {feedback && drawerMode === null ? (
            <InlineFeedback message={feedback} tone={feedbackTone} className="studio-workspace-feedback" />
          ) : null}
          {pathTaskId ? (
            <section className="studio-job-strip" aria-label="路径任务">
              <CheckCircle size={17} weight="duotone" aria-hidden="true" />
              <div>
                <strong>本节已完成 {pathTask?.learning_bundle?.completed_count ?? 0}/{pathTask?.learning_bundle?.ready_count ?? 0} 个可学习资源</strong>
                <span>逐项学习资源，最后返回路径确认完成本节。</span>
              </div>
              {selectedBundleItem?.learning_status === "completed" && nextBundleItem?.resource_id ? (
                <button type="button" onClick={() => selectResource(nextBundleItem.resource_id as string)}>学习下一项</button>
              ) : (
                <Link to={`${PATHS.path}?course_id=${effectiveCourseId ?? ""}`}>返回本节学习安排</Link>
              )}
            </section>
          ) : (
            <NextLearningAction action={nextActionQuery.data?.data} isLoading={nextActionQuery.isPending} error={nextActionQuery.isError} compact />
          )}

          <div className="studio-workspace-body">
            <StudioResourceLibrary
              hasCourse={effectiveCourseId !== null}
              families={filteredFamilies}
              selectedResourceId={selectedResource?.id ?? null}
              search={librarySearch}
              typeFilter={resourceTypeFilter}
              isLoading={effectiveCourseId !== null && resourcesQuery.isPending && resources.length === 0}
              onSearchChange={setLibrarySearch}
              onTypeFilterChange={setResourceTypeFilter}
              onSelectResource={selectResource}
            />
            <StudioArtifactCanvas
              resource={selectedResource}
              hasCourse={effectiveCourseId !== null}
              courseTitle={selectedCourse?.title ?? null}
              knowledgePointTitle={selectedResourceKnowledgePointTitle}
              isLoading={coursesQuery.isPending || (effectiveCourseId !== null && resourcesQuery.isPending && resources.length === 0)}
              isError={dataError}
              onCreate={() => setDrawerMode("generate")}
              onRetry={() => {
                void coursesQuery.refetch();
                void resourcesQuery.refetch();
              }}
              versions={selectedVersions}
              onSelectVersion={selectResource}
              onCompareVersions={() => setCompareDialogOpen(true)}
              onRegenerate={() => setRegenerateDialogOpen(true)}
            />
          </div>
        </section>
      </PageFrame>

      <StudioDrawer
        mode={drawerMode}
        detailTab={detailTab}
        courses={courses}
        courseId={effectiveCourseId}
        knowledgePoints={knowledgePoints}
        knowledgePointId={effectiveKnowledgePointId}
        selectedTypes={selectedResourceTypes}
        learningGoal={learningGoal}
        difficulty={difficulty}
        resource={selectedResource}
        qualityScores={resourceQualityQuery.data?.data ?? []}
        traceEvents={resourceTraceEvents}
        traceLoading={resourceTraceQuery.isPending && resourceTraceQuery.fetchStatus !== "idle"}
        traceError={resourceTraceQuery.isError}
        traceId={selectedResourceTraceId}
        job={resourceJob}
        feedback={drawerMode === "generate" ? feedback : null}
        canGenerate={canGenerate}
        isGenerating={isGenerating || generateMutation.isPending}
        onClose={() => setDrawerMode(null)}
        onDetailTabChange={setDetailTab}
        onCourseChange={handleCourseChange}
        onKnowledgePointChange={setSelectedKnowledgePointId}
        onToggleType={toggleResourceType}
        onLearningGoalChange={setLearningGoal}
        onDifficultyChange={setDifficulty}
        onGenerate={handleGenerate}
        onCancelJob={() => resourceJob ? void cancelJob(resourceJob.job_id) : undefined}
        onRetryJob={() => void handleRetryJob()}
        onDeleteJob={() => void handleDeleteJob()}
      />

      {regenerateDialogOpen && selectedResource ? (
        <StudioRegenerateDialog
          resource={selectedResource}
          isSubmitting={generateMutation.isPending || isGenerating}
          onClose={() => setRegenerateDialogOpen(false)}
          onChoose={handleRegenerate}
        />
      ) : null}

      {compareDialogOpen && selectedResource && selectedVersions.length > 1 ? (
        <StudioVersionCompareDialog
          key={`${selectedResource.id}-${selectedVersions.map((resource) => resource.id).join("-")}`}
          current={selectedResource}
          versions={selectedVersions}
          onClose={() => setCompareDialogOpen(false)}
        />
      ) : null}
    </>
  );
}

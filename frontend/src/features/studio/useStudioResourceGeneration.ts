import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import {
  createIdempotencyKey,
  createResourceGenerationJob,
  type AiJob
} from "../../api/aiJobs";
import type {
  GeneratedResource,
  ResourceDifficulty,
  ResourceGenerationAction,
  ResourceType
} from "../../api/resources";
import type { FeedbackTone } from "../../components/feedback/InlineFeedback";
import type { StudioDrawerMode } from "../../components/studio/StudioDrawer";
import { useAiJobs } from "../aiJobs/AiJobProvider";
import { invalidateCourseLearningLoop } from "../course-space/courseLoopQueries";

type StudioResourceGenerationParams = {
  courseId: number | null;
  difficulty: ResourceDifficulty;
  initialCourseId: number | null;
  knowledgePointId: number | null;
  learningGoal: string;
  numericPathTaskId: number | null;
  onCompleted: (courseId: number, resourceIds: string[]) => Promise<boolean>;
  onRestoreRequest: (request: AiJob["request"]) => void;
  pathTaskId: string | null;
  resource: GeneratedResource | null;
  selectedTypes: ResourceType[];
};

export function useStudioResourceGeneration({
  courseId,
  difficulty,
  initialCourseId,
  knowledgePointId,
  learningGoal,
  numericPathTaskId,
  onCompleted,
  onRestoreRequest,
  pathTaskId,
  resource,
  selectedTypes
}: StudioResourceGenerationParams) {
  const queryClient = useQueryClient();
  const [drawerMode, setDrawerMode] = useState<StudioDrawerMode>(null);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [feedbackTone, setFeedbackTone] = useState<FeedbackTone>("info");
  const [resourceJobId, setResourceJobId] = useState<string | null>(null);
  const [regenerateDialogOpen, setRegenerateDialogOpen] = useState(false);
  const handledCompletedJobIds = useRef(new Set<string>());
  const { jobs, trackJob, getJob, cancelJob, retryJob, deleteJob } = useAiJobs();
  const resourceJob = getJob(resourceJobId);
  const isGenerating = Boolean(resourceJob && ["queued", "running", "cancelling"].includes(resourceJob.status));

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
    // Restore durable server state after navigation or refresh.
    onRestoreRequest(restored.request);
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setResourceJobId(restored.job_id);
    if (restored.status === "failed") {
      if (restored.request.generation_action === "alternative" || restored.request.generation_action === "refine") {
        setRegenerateDialogOpen(true);
      } else {
        setDrawerMode("generate");
      }
    }
  }, [initialCourseId, jobs, numericPathTaskId, onRestoreRequest, resourceJobId]);

  useEffect(() => {
    if (!resourceJob) return;
    if (resourceJob.status === "failed") {
      // Keep the failure visible without forcing a drawer the user has closed to reopen.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setFeedbackTone("warning");
      setFeedback(resourceJob.error_message ?? "资源生成失败，请稍后重试。");
      return;
    }
    if (resourceJob.status !== "completed" || handledCompletedJobIds.current.has(resourceJob.job_id)) return;
    handledCompletedJobIds.current.add(resourceJob.job_id);
    const resourceIds = Array.isArray(resourceJob.result.resource_ids)
      ? resourceJob.result.resource_ids.map(String)
      : [];
    setFeedbackTone(resourceJob.warnings.length > 0 ? "warning" : "success");
    setFeedback(resourceJob.warnings.join(" ") || "资源生成完成。");
    void (async () => {
      const completedCourseId = Number(resourceJob.request.course_id ?? resourceJob.course_id);
      if (Number.isFinite(completedCourseId) && completedCourseId > 0) {
        await invalidateCourseLearningLoop(queryClient, completedCourseId);
        if (await onCompleted(completedCourseId, resourceIds)) {
          setDrawerMode(null);
        }
      }
    })();
  }, [onCompleted, queryClient, resourceJob]);

  const generateMutation = useMutation({
    mutationFn: ({ action, source }: { action: ResourceGenerationAction; source?: GeneratedResource }) => {
      if (courseId === null) throw new Error("missing course");
      const sourceIntent = source?.intent_summary ?? source?.content_json.intent;
      const sourceDifficulty = source?.content_json.metadata?.difficulty;
      return createResourceGenerationJob(
        {
          course_id: courseId,
          knowledge_point_id: source?.knowledge_point_id ? Number(source.knowledge_point_id) : knowledgePointId,
          resource_types: source ? [source.resource_type] : selectedTypes,
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

  function generate() {
    if (courseId === null || generateMutation.isPending || isGenerating || selectedTypes.length === 0) return;
    generateMutation.mutate({ action: "new" });
  }

  function regenerate(action: Exclude<ResourceGenerationAction, "new">) {
    if (!resource || generateMutation.isPending || isGenerating) return;
    generateMutation.mutate({ action, source: resource });
  }

  async function retryCurrentJob() {
    if (!resourceJob) return;
    const job = await retryJob(resourceJob.job_id);
    setFeedback(null);
    setResourceJobId(job.job_id);
  }

  async function deleteCurrentJob() {
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

  function clearFeedback() {
    setFeedback(null);
  }

  function reportFailure(message: string) {
    setFeedbackTone("warning");
    setFeedback(message);
  }

  const canGenerate = courseId !== null
    && selectedTypes.length > 0
    && !generateMutation.isPending
    && !isGenerating;
  const showCompactJob = resourceJob && ["queued", "running", "cancelling"].includes(resourceJob.status);

  return {
    canGenerate,
    cancelJob,
    clearFeedback,
    closeDrawer: () => setDrawerMode(null),
    closeRegenerateDialog: () => setRegenerateDialogOpen(false),
    deleteCurrentJob,
    drawerMode,
    feedback,
    feedbackTone,
    generate,
    isGenerating,
    job: resourceJob,
    mutationPending: generateMutation.isPending,
    openDetails: () => setDrawerMode("details"),
    openGenerate: () => setDrawerMode("generate"),
    openRegenerateDialog: () => setRegenerateDialogOpen(true),
    regenerate,
    regenerateDialogOpen,
    reportFailure,
    retryCurrentJob,
    showCompactJob
  };
}

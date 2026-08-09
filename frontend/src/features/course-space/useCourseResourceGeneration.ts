import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import { createIdempotencyKey, createResourceGenerationJob } from "../../api/aiJobs";
import type { CourseMasteryPoint } from "../../api/courses";
import type { GeneratedResource, ResourceType } from "../../api/resources";
import { useAiJobs } from "../aiJobs/AiJobProvider";
import { invalidateCourseLearningLoop } from "./courseLoopQueries";
import { resourceDifficultyForPoint } from "./courseRecommendation";
import type { useCourseWorkspaceData } from "./useCourseWorkspaceData";

type CourseResourceGenerationParams = {
  courseId: number;
  enabled: boolean;
  courseResourcesQuery: ReturnType<typeof useCourseWorkspaceData>["courseResourcesQuery"];
  masteryPoints: CourseMasteryPoint[];
  latestUserQuestion: string | null;
  currentGoal: string;
};

export function useCourseResourceGeneration({
  courseId,
  enabled,
  courseResourcesQuery,
  masteryPoints,
  latestUserQuestion,
  currentGoal
}: CourseResourceGenerationParams) {
  const queryClient = useQueryClient();
  const [feedback, setFeedback] = useState<string | null>(null);
  const [latestGeneratedResources, setLatestGeneratedResources] = useState<GeneratedResource[]>([]);
  const [resourceContext, setResourceContext] = useState<{ question: string | null; knowledgePointId: string | null }>({
    question: null,
    knowledgePointId: null
  });
  const [resourceJobId, setResourceJobId] = useState<string | null>(null);
  const [selectedResourceTypes, setSelectedResourceTypes] = useState<ResourceType[]>(["doc", "mindmap", "quiz"]);
  const handledResourceJobId = useRef<string | null>(null);
  const { jobs, trackJob, getJob, cancelJob, retryJob } = useAiJobs();
  const resourceJob = getJob(resourceJobId);
  const isGenerating = Boolean(resourceJob && ["queued", "running", "cancelling"].includes(resourceJob.status));

  useEffect(() => {
    if (resourceJobId || !enabled) return;
    const restored = jobs.find((job) => job.workflow === "resource_generation"
      && Number(job.request.course_id) === courseId
      && ["queued", "running", "cancelling", "failed"].includes(job.status));
    if (!restored) return;
    // Restore durable server state after navigation or refresh.
    if (Array.isArray(restored.request.resource_types)) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setSelectedResourceTypes(restored.request.resource_types as ResourceType[]);
    }
    setResourceJobId(restored.job_id);
  }, [courseId, enabled, jobs, resourceJobId]);

  useEffect(() => {
    if (!resourceJob) return;
    if (resourceJob.status === "failed") {
      // Surface the terminal state delivered by the external job runtime.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setFeedback(resourceJob.error_message ?? "课程资源生成失败，请稍后重试。");
      return;
    }
    if (resourceJob.status !== "completed" || handledResourceJobId.current === resourceJob.job_id) return;
    handledResourceJobId.current = resourceJob.job_id;
    const resourceIds = Array.isArray(resourceJob.result.resource_ids)
      ? resourceJob.result.resource_ids.map(String)
      : [];
    setFeedback(resourceJob.warnings.length > 0 ? resourceJob.warnings.join(" ") : null);
    void (async () => {
      await invalidateCourseLearningLoop(queryClient, courseId);
      const refreshed = await courseResourcesQuery.refetch();
      const resources = refreshed.data?.data ?? [];
      setLatestGeneratedResources(
        resourceIds.length > 0 ? resources.filter((item) => resourceIds.includes(item.id)) : resources.slice(0, 6)
      );
    })();
  }, [courseId, courseResourcesQuery, queryClient, resourceJob]);

  const mutation = useMutation({
    mutationFn: () => {
      const parsedKnowledgePointId = resourceContext.knowledgePointId
        ? Number.parseInt(resourceContext.knowledgePointId, 10)
        : Number.NaN;
      const masteryPoint = masteryPoints.find((point) => point.id === resourceContext.knowledgePointId);
      return createResourceGenerationJob(
        {
          course_id: courseId,
          knowledge_point_id: Number.isFinite(parsedKnowledgePointId) ? parsedKnowledgePointId : undefined,
          resource_types: selectedResourceTypes,
          learning_goal: resourceContext.question ?? latestUserQuestion ?? currentGoal,
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
    onError: () => setFeedback("课程资源生成失败，请稍后重试。")
  });

  function toggleResourceType(resourceType: ResourceType) {
    setSelectedResourceTypes((current) =>
      current.includes(resourceType) ? current.filter((item) => item !== resourceType) : [...current, resourceType]
    );
  }

  function submitGeneration() {
    if (!enabled || mutation.isPending || isGenerating || selectedResourceTypes.length === 0) return;
    setFeedback(null);
    mutation.mutate();
  }

  async function retryResourceJob() {
    if (!resourceJob) return;
    const retried = await retryJob(resourceJob.job_id);
    handledResourceJobId.current = null;
    setResourceJobId(retried.job_id);
  }

  async function cancelResourceJob() {
    if (resourceJob) await cancelJob(resourceJob.job_id);
  }

  return {
    cancelResourceJob,
    feedback,
    isGenerating,
    latestGeneratedResources,
    mutation,
    resourceJob,
    retryResourceJob,
    selectedResourceTypes,
    setResourceContext,
    submitGeneration,
    toggleResourceType
  };
}

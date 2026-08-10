import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { createCourseBuilderJob, createIdempotencyKey } from "../../api/aiJobs";
import { getApiErrorMessage } from "../../api/errors";
import { buildCoursePath } from "../../app/routePaths";
import type { FeedbackTone } from "../../components/feedback/InlineFeedback";
import { useAiJobs } from "../aiJobs/AiJobProvider";
import { isRestorableCourseBuilderJob } from "../aiJobs/jobRestoration";
import { invalidateLearningNextActions } from "../learning-actions/learningActions";

type HomeCourseBuilderParams = {
  onCloseLibrary: () => void;
};

export function useHomeCourseBuilder({ onCloseLibrary }: HomeCourseBuilderParams) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const { jobs, getJob, trackJob, cancelJob, retryJob } = useAiJobs();
  const [materialIds, setMaterialIds] = useState<string[]>([]);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<{ message: string; tone: FeedbackTone } | null>(null);
  const job = getJob(jobId);
  const isCreating = Boolean(job && ["queued", "running", "cancelling"].includes(job.status));

  useEffect(() => {
    if (jobId) return;
    const restored = jobs.find(isRestorableCourseBuilderJob);
    if (!restored) return;
    const restoredMaterialIds = Array.isArray(restored.request.material_ids)
      ? restored.request.material_ids.map(String)
      : [];
    // Restore durable server state after navigation or refresh.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setMaterialIds(restoredMaterialIds);
    setJobId(restored.job_id);
    onCloseLibrary();
    setDialogOpen(true);
  }, [jobId, jobs, onCloseLibrary]);

  useEffect(() => {
    if (!job) return;
    if (job.status === "failed") {
      // Surface the terminal state delivered by the external job runtime.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setFeedback({ message: job.error_message ?? "课程生成失败，请稍后重试。", tone: "warning" });
      return;
    }
    const courseId = job.result.course_id;
    if (job.status === "completed" && (typeof courseId === "string" || typeof courseId === "number")) {
      setJobId(null);
      setDialogOpen(false);
      onCloseLibrary();
      void queryClient.invalidateQueries({ queryKey: ["dashboard", "summary"] });
      void invalidateLearningNextActions(queryClient);
      navigate(buildCoursePath(String(courseId)));
    }
  }, [job, navigate, onCloseLibrary, queryClient]);

  function open(nextMaterialIds: string[]) {
    setMaterialIds(nextMaterialIds);
    onCloseLibrary();
    setDialogOpen(true);
  }

  function toggleMaterial(materialId: string) {
    setMaterialIds((current) => (
      current.includes(materialId)
        ? current.filter((id) => id !== materialId)
        : [...current, materialId]
    ));
  }

  async function createCourse(courseTitle: string) {
    const selectedIds = materialIds
      .map((materialId) => Number.parseInt(materialId, 10))
      .filter((materialId) => Number.isFinite(materialId));
    if (selectedIds.length === 0) {
      setFeedback({ message: "请先选择至少一份资料。", tone: "warning" });
      return;
    }
    if (isCreating) return;
    setFeedback(null);
    try {
      const createdJob = await createCourseBuilderJob(
        { material_ids: selectedIds, course_title: courseTitle.trim() },
        createIdempotencyKey("home-course")
      );
      setJobId(createdJob.job_id);
      trackJob(createdJob);
    } catch (error) {
      setFeedback({
        message: getApiErrorMessage(error, "课程生成失败，请确认选择的是已解析资料。"),
        tone: "warning"
      });
    }
  }

  function resetDialog() {
    setMaterialIds([]);
    setDialogOpen(false);
    setFeedback(null);
  }

  return {
    cancelJob,
    createCourse,
    dialogOpen,
    feedback,
    isCreating,
    job,
    materialIds,
    open,
    resetDialog,
    retryJob,
    setDialogOpen,
    setJobId,
    toggleMaterial
  };
}

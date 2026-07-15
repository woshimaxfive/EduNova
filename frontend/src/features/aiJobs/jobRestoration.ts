import type { AiJob } from "../../api/aiJobs";

export function isRestorableCourseBuilderJob(job: Pick<AiJob, "workflow" | "status">) {
  return job.workflow === "course_builder" && ["queued", "running", "cancelling"].includes(job.status);
}

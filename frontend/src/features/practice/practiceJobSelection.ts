import { type AiJob } from "../../api/aiJobs";

export function selectResumablePracticeJob(
  jobs: AiJob[],
  courseId: number,
  weaknessItemId: number | null
) {
  return jobs.find((job) => (
    job.workflow === "practice_generation"
    && Number(job.request.course_id) === courseId
    && ["queued", "running", "cancelling"].includes(job.status)
    && Number(job.request.weakness_item_id ?? 0) === (weaknessItemId ?? 0)
  ));
}

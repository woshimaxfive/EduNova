import { type AiJob } from "../api/aiJobs";

export function makeCompletedAiJob(overrides: Partial<AiJob> = {}): AiJob {
  return {
    job_id: "9001",
    workflow: "resource_generation",
    status: "completed",
    course_id: "808",
    retry_of_job_id: null,
    progress_percent: 100,
    stage: "completed",
    label: "任务已完成",
    steps: [],
    agent_trace_id: "trace_ai_job",
    request: {},
    result: {},
    warnings: [],
    error_code: null,
    error_message: null,
    attempt_count: 0,
    can_cancel: false,
    can_retry: false,
    created_at: "2026-07-11T10:00:00Z",
    updated_at: "2026-07-11T10:00:01Z",
    started_at: "2026-07-11T10:00:00Z",
    completed_at: "2026-07-11T10:00:01Z",
    ...overrides
  };
}

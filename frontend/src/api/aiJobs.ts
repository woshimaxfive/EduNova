import { apiClient } from "./client";
import { useAuthStore } from "../features/auth/authStore";
import { type ApiEnvelope } from "../types/api";
import { type CreateCourseFromMaterialsRequest } from "./courses";
import { type GenerateResourcesRequest } from "./resources";

export type AiJobWorkflow = "course_builder" | "resource_generation" | "embedding_reindex" | "material_ingestion";
export type AiJobStatus = "queued" | "running" | "cancelling" | "cancelled" | "completed" | "failed";

export type AiJobStep = {
  name: string;
  label: string;
  status: string;
  progress_percent: number;
  resource_type: string | null;
  updated_at: string;
};

export type AiJob = {
  job_id: string;
  workflow: AiJobWorkflow;
  status: AiJobStatus;
  course_id: string | null;
  retry_of_job_id: string | null;
  progress_percent: number;
  stage: string;
  label: string;
  steps: AiJobStep[];
  agent_trace_id: string;
  request: Record<string, unknown>;
  result: Record<string, unknown>;
  warnings: string[];
  error_code: string | null;
  error_message: string | null;
  attempt_count: number;
  can_cancel: boolean;
  can_retry: boolean;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  completed_at: string | null;
};

export type AiJobList = { data: AiJob[]; total: number };
export type AiJobEventName = "snapshot" | "done" | "error" | "cancelled";

export const AI_JOB_ENDPOINTS = {
  list: "/ai-jobs",
  detail: (jobId: string) => `/ai-jobs/${jobId}`,
  events: (jobId: string) => `/ai-jobs/${jobId}/events`,
  cancel: (jobId: string) => `/ai-jobs/${jobId}/cancel`,
  retry: (jobId: string) => `/ai-jobs/${jobId}/retry`,
  courseBuilder: "/courses/from-materials/jobs",
  resourceGeneration: "/resources/generation-jobs"
} as const;

export function createIdempotencyKey(prefix: string) {
  const suffix = typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`;
  return `${prefix}-${suffix}`;
}

export async function createCourseBuilderJob(payload: CreateCourseFromMaterialsRequest, idempotencyKey: string) {
  const response = await apiClient.post<ApiEnvelope<AiJob>>(AI_JOB_ENDPOINTS.courseBuilder, payload, {
    headers: { "Idempotency-Key": idempotencyKey }
  });
  return response.data.data;
}

export async function createResourceGenerationJob(payload: GenerateResourcesRequest, idempotencyKey: string) {
  const response = await apiClient.post<ApiEnvelope<AiJob>>(AI_JOB_ENDPOINTS.resourceGeneration, payload, {
    headers: { "Idempotency-Key": idempotencyKey }
  });
  return response.data.data;
}

export async function listAiJobs() {
  const response = await apiClient.get<ApiEnvelope<AiJobList>>(AI_JOB_ENDPOINTS.list, { params: { status: "active", limit: 20 } });
  return response.data.data;
}

export async function getAiJob(jobId: string) {
  const response = await apiClient.get<ApiEnvelope<AiJob>>(AI_JOB_ENDPOINTS.detail(jobId));
  return response.data.data;
}

export async function cancelAiJob(jobId: string) {
  const response = await apiClient.post<ApiEnvelope<AiJob>>(AI_JOB_ENDPOINTS.cancel(jobId));
  return response.data.data;
}

export async function retryAiJob(jobId: string) {
  const response = await apiClient.post<ApiEnvelope<AiJob>>(AI_JOB_ENDPOINTS.retry(jobId));
  return response.data.data;
}

export async function streamAiJob(
  jobId: string,
  onEvent: (event: AiJobEventName, job: AiJob) => void,
  signal?: AbortSignal
) {
  const token = useAuthStore.getState().token;
  const baseUrl = String(apiClient.defaults.baseURL ?? "/api/v1").replace(/\/$/, "");
  const response = await fetch(`${baseUrl}${AI_JOB_ENDPOINTS.events(jobId)}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    signal
  });
  if (!response.ok || !response.body) {
    throw new Error("任务进度连接失败");
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value, { stream: !done });
    const blocks = buffer.split("\n\n");
    buffer = blocks.pop() ?? "";
    for (const block of blocks) {
      const eventLine = block.split("\n").find((line) => line.startsWith("event:"));
      const dataLines = block.split("\n").filter((line) => line.startsWith("data:"));
      if (!eventLine || dataLines.length === 0) continue;
      const event = eventLine.slice(6).trim() as AiJobEventName;
      const data = dataLines.map((line) => line.slice(5).trimStart()).join("\n");
      onEvent(event, JSON.parse(data) as AiJob);
      if (event === "done" || event === "error" || event === "cancelled") {
        await reader.cancel();
        return;
      }
    }
    if (done) break;
  }
}

import { apiClient } from "./client";
import { useAuthStore } from "../features/auth/authStore";
import { consumeSseResponse } from "./sse";
import { type ApiEnvelope } from "../types/api";
import { type CreateCourseFromMaterialsRequest } from "./courses";
import { type GenerateResourcesRequest } from "./resources";
import { type GeneratePathRequest } from "./paths";

export type AiJobWorkflow = "course_builder" | "resource_generation" | "embedding_reindex" | "material_ingestion" | "path_planning";
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
  resourceGeneration: "/resources/generation-jobs",
  pathPlanning: "/paths/generation-jobs"
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

export async function createPathPlanningJob(payload: GeneratePathRequest, idempotencyKey: string) {
  const response = await apiClient.post<ApiEnvelope<AiJob>>(AI_JOB_ENDPOINTS.pathPlanning, payload, {
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
  await consumeSseResponse(response, ({ event, data }) => {
    const eventName = event as AiJobEventName;
    onEvent(eventName, data as AiJob);
    return eventName === "done" || eventName === "error" || eventName === "cancelled" ? false : undefined;
  });
}

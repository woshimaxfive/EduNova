import { apiClient } from "./client";
import { type ApiEnvelope } from "../types/api";
import { type CourseResourceBrief } from "./courses";
import type { PersonalizationFreshness } from "./personalization";

export const PATH_ENDPOINTS = {
  generate: "/paths/generate",
  current: "/paths/current",
  updateTask: (taskId: number) => `/paths/tasks/${taskId}`
} as const;

export type PathTaskStatus = "todo" | "doing" | "completed";

export type GeneratePathRequest = {
  course_id: number;
};

export type UpdatePathTaskRequest = {
  status: PathTaskStatus;
};

export type LearningPath = {
  id: string;
  course_id: string;
  title: string;
  goal: string;
  status: "active" | "archived" | string;
  agent_trace_id?: string | null;
  plan_json: Record<string, unknown>;
  personalization?: PersonalizationFreshness | null;
  created_at: string;
  updated_at: string;
};

export type LearningPathTask = {
  id: string;
  path_id: string;
  course_id: string;
  knowledge_point_id: string | null;
  title: string;
  task_type: "review" | "learn" | "resource" | string;
  reason: string;
  recommended_resource_ids: string[];
  recommended_resources: CourseResourceBrief[];
  learning_bundle?: {
    strategy: string;
    rationale: string;
    items: Array<{
      resource_type: string;
      role: string;
      resource_id: string | null;
      status: "available" | "recommended" | "generating" | "failed" | string;
    }>;
  } | null;
  status: PathTaskStatus;
  created_at: string;
  updated_at: string;
};

export type PathEvidenceSummary = {
  knowledge_point_count: number;
  confirmed_or_reviewing_weakness_count: number;
  pending_weakness_count: number;
  resource_count: number;
  basis: string[];
};

export type LearningPathDetail = {
  course_id: string;
  status: "not_started" | "active" | string;
  message: string;
  agent_trace_id?: string | null;
  path: LearningPath | null;
  tasks: LearningPathTask[];
  evidence_summary: PathEvidenceSummary;
};

export async function generatePath(payload: GeneratePathRequest) {
  const response = await apiClient.post<ApiEnvelope<LearningPathDetail>>(PATH_ENDPOINTS.generate, payload);
  return response.data;
}

export async function getCurrentPath(courseId: number) {
  const response = await apiClient.get<ApiEnvelope<LearningPathDetail>>(PATH_ENDPOINTS.current, {
    params: { course_id: courseId }
  });
  return response.data;
}

export async function updatePathTask(taskId: number, payload: UpdatePathTaskRequest) {
  const response = await apiClient.patch<ApiEnvelope<LearningPathTask>>(PATH_ENDPOINTS.updateTask(taskId), payload);
  return response.data;
}

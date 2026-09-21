import { apiClient } from "./client";
import { type ApiEnvelope } from "../types/api";
import { type CourseResourceBrief } from "./courses";
import type { PersonalizationFreshness } from "./personalization";

export const PATH_ENDPOINTS = {
  generate: "/paths/generate",
  generationJobs: "/paths/generation-jobs",
  current: "/paths/current",
  updateTask: (taskId: number) => `/paths/tasks/${taskId}`,
  taskResourceJobs: (taskId: number) => `/paths/tasks/${taskId}/resource-jobs`
} as const;

export type PathTaskStatus = "todo" | "doing" | "completed";

export type GeneratePathRequest = {
  course_id: number;
  draft?: boolean;
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
  approval_status?: "legacy" | "draft" | "approved";
  approved_at?: string | null;
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
    teaching_strategy: string;
    learning_problem?: string;
    example_direction?: string;
    difficulty: "easy" | "medium" | "hard";
    used_profile_factor_codes: string[];
    generation_mode: string;
    rationale: string;
    items: Array<{
      resource_type: string;
      role: string;
      resource_id: string | null;
      status: "available" | "recommended" | "generating" | "failed" | string;
      learning_status: "not_started" | "in_progress" | "completed";
    }>;
    ready_count: number;
    completed_count: number;
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

export async function getPathTask(taskId: number) {
  const response = await apiClient.get<ApiEnvelope<LearningPathTask>>(`/paths/tasks/${taskId}`);
  return response.data;
}

export async function listPathDrafts(courseId: number) {
  const response = await apiClient.get<ApiEnvelope<LearningPath[]>>("/paths/drafts", { params: { course_id: courseId } });
  return response.data;
}

export async function getPathVersion(pathId: string) {
  const response = await apiClient.get<ApiEnvelope<LearningPathDetail>>(`/paths/${pathId}`);
  return response.data;
}

export async function approvePath(pathId: string, expectedActivePathId: number | null) {
  const response = await apiClient.post<ApiEnvelope<LearningPathDetail>>(`/paths/${pathId}/approve`, {
    expected_active_path_id: expectedActivePathId
  });
  return response.data;
}

export async function updatePathTask(taskId: number, payload: UpdatePathTaskRequest) {
  const response = await apiClient.patch<ApiEnvelope<LearningPathTask>>(PATH_ENDPOINTS.updateTask(taskId), payload);
  return response.data;
}

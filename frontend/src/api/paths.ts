import { apiClient } from "./client";
import { type ApiEnvelope } from "../types/api";

export const PATH_ENDPOINTS = {
  generate: "/paths/generate",
  current: "/paths/current",
  updateTask: (taskId: number) => `/paths/tasks/${taskId}`
} as const;

export type GeneratePathRequest = {
  course_id: number;
  duration_days: number;
  goal: string;
};

export type UpdatePathTaskRequest = {
  status: "todo" | "doing" | "completed";
};

export async function generatePath(payload: GeneratePathRequest) {
  const response = await apiClient.post<ApiEnvelope<Record<string, unknown>>>(PATH_ENDPOINTS.generate, payload);
  return response.data;
}

export async function getCurrentPath() {
  const response = await apiClient.get<ApiEnvelope<Record<string, unknown>>>(PATH_ENDPOINTS.current);
  return response.data;
}

export async function updatePathTask(taskId: number, payload: UpdatePathTaskRequest) {
  const response = await apiClient.patch<ApiEnvelope<Record<string, unknown>>>(PATH_ENDPOINTS.updateTask(taskId), payload);
  return response.data;
}

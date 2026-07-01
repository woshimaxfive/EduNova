import { apiClient } from "./client";
import { type ApiEnvelope, type ApiListEnvelope } from "../types/api";

export const RESOURCE_ENDPOINTS = {
  generate: "/resources/generate",
  list: "/resources",
  detail: (resourceId: number) => `/resources/${resourceId}`,
  quality: (resourceId: number) => `/resources/${resourceId}/quality`
} as const;

export type GenerateResourcesRequest = {
  course_id: number;
  knowledge_point_id: number;
  resource_types: Array<"doc" | "mindmap" | "quiz" | "code" | "slide">;
  learning_goal: string;
  difficulty: "easy" | "medium" | "hard";
};

export async function generateResources(payload: GenerateResourcesRequest) {
  const response = await apiClient.post<ApiEnvelope<Record<string, unknown>>>(RESOURCE_ENDPOINTS.generate, payload);
  return response.data;
}

export async function listResources() {
  const response = await apiClient.get<ApiListEnvelope<Record<string, unknown>>>(RESOURCE_ENDPOINTS.list);
  return response.data;
}

export async function getResource(resourceId: number) {
  const response = await apiClient.get<ApiEnvelope<Record<string, unknown>>>(RESOURCE_ENDPOINTS.detail(resourceId));
  return response.data;
}

export async function getResourceQuality(resourceId: number) {
  const response = await apiClient.get<ApiEnvelope<Record<string, unknown>>>(RESOURCE_ENDPOINTS.quality(resourceId));
  return response.data;
}

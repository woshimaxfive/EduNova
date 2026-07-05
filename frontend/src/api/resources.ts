import { apiClient } from "./client";
import { type ApiEnvelope, type ApiListEnvelope } from "../types/api";

export const RESOURCE_ENDPOINTS = {
  generate: "/resources/generate",
  list: "/resources",
  detail: (resourceId: number) => `/resources/${resourceId}`,
  quality: (resourceId: number) => `/resources/${resourceId}/quality`
} as const;

export type ResourceType = "doc" | "mindmap" | "quiz" | "code" | "slide";
export type ResourceDifficulty = "easy" | "medium" | "hard";
export type ResourceReviewStatus = "passed" | "low_evidence" | "pending" | "failed" | string;

export type GenerateResourcesRequest = {
  course_id: number;
  knowledge_point_id?: number | null;
  resource_types: ResourceType[];
  learning_goal?: string;
  difficulty?: ResourceDifficulty;
};

export type GeneratedResourceCitation = {
  chunk_id?: number;
  knowledge_point_id?: number | null;
  source_title?: string;
  section_title?: string;
  page_number?: number | null;
};

export type GeneratedResourceContent = {
  markdown?: string;
  format?: string;
  topic?: string;
  course_title?: string;
  citation_summaries?: string[];
  metadata?: {
    agent_trace_id?: string;
    generation_mode?: string;
    difficulty?: ResourceDifficulty;
    has_learning_goal?: boolean;
  };
  [key: string]: unknown;
};

export type GeneratedResource = {
  id: string;
  course_id: string | null;
  knowledge_point_id: string | null;
  resource_type: ResourceType;
  title: string;
  content_json: GeneratedResourceContent;
  citation_json: GeneratedResourceCitation[];
  status: string;
  review_status: ResourceReviewStatus;
  confidence_score: number | null;
  agent_trace_id: string | null;
  created_at: string;
  updated_at: string;
};

export type ResourceQualityScore = {
  id: string;
  resource_id: string;
  score_name: "source_match" | "profile_fit" | "fact_confidence" | "difficulty_fit" | "completeness" | string;
  score_value: number;
  rationale: string | null;
  created_at: string;
};

export type GenerateResourcesResult = {
  agent_trace_id: string;
  resources: GeneratedResource[];
  quality_scores: Record<string, ResourceQualityScore[]>;
};

export async function generateResources(payload: GenerateResourcesRequest) {
  const response = await apiClient.post<ApiEnvelope<GenerateResourcesResult>>(RESOURCE_ENDPOINTS.generate, payload);
  return response.data;
}

export async function listResources(params?: { courseId?: number; resourceType?: ResourceType }) {
  const queryParams: { course_id?: number; resource_type?: ResourceType } = {};

  if (params?.courseId !== undefined) {
    queryParams.course_id = params.courseId;
  }
  if (params?.resourceType !== undefined) {
    queryParams.resource_type = params.resourceType;
  }

  const response = await apiClient.get<ApiListEnvelope<GeneratedResource>>(
    RESOURCE_ENDPOINTS.list,
    Object.keys(queryParams).length > 0 ? { params: queryParams } : undefined
  );
  return response.data;
}

export async function getResource(resourceId: number) {
  const response = await apiClient.get<ApiEnvelope<GeneratedResource>>(RESOURCE_ENDPOINTS.detail(resourceId));
  return response.data;
}

export async function getResourceQuality(resourceId: number) {
  const response = await apiClient.get<ApiEnvelope<ResourceQualityScore[]>>(RESOURCE_ENDPOINTS.quality(resourceId));
  return response.data;
}

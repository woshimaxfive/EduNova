import { apiClient } from "./client";
import { type ApiEnvelope, type ApiListEnvelope } from "../types/api";
import { type ExportJob } from "./exports";
import type { PersonalizationFreshness } from "./personalization";

export const RESOURCE_ENDPOINTS = {
  generate: "/resources/generate",
  generationJobs: "/resources/generation-jobs",
  list: "/resources",
  detail: (resourceId: number) => `/resources/${resourceId}`,
  quality: (resourceId: number) => `/resources/${resourceId}/quality`,
  exports: (resourceId: number) => `/resources/${resourceId}/exports`
} as const;

export type ResourceType = "doc" | "mindmap" | "quiz" | "code" | "slide" | "animation";
export type ResourceDifficulty = "easy" | "medium" | "hard";
export type ResourceReviewStatus = "passed" | "low_evidence" | "pending" | "failed" | string;
export type ResourceGenerationMode = "model_enhanced" | "deterministic_source" | "low_evidence_fallback" | string;

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

export type ResourceDocumentArtifact = {
  kind: "document";
  sections: Array<{ heading: string; body: string }>;
  citation_refs: number[];
};

export type ResourceMindmapNode = {
  id: string;
  title: string;
  children: ResourceMindmapNode[];
};

export type ResourceMindmapArtifact = {
  kind: "mindmap";
  markmap_markdown: string;
  tree: ResourceMindmapNode;
  citation_refs: number[];
};

export type ResourceQuizQuestion = {
  id: string;
  type: "single_choice" | "multiple_choice" | "short_answer";
  prompt: string;
  options: Array<{ key: string; text: string }>;
  answer: string | string[];
  explanation: string;
  citation_refs: number[];
};

export type ResourceQuizArtifact = {
  kind: "quiz";
  questions: ResourceQuizQuestion[];
  citation_refs: number[];
};

export type ResourceCodeArtifact = {
  kind: "code_lab";
  language: "python";
  runtime: "pyodide";
  entry_file: string;
  files: Array<{ path: string; content: string }>;
  instructions: string[];
  expected_output: string;
  tasks: string[];
  citation_refs: number[];
};

export type ResourceSlide = {
  id: string;
  title: string;
  bullets: string[];
  speaker_notes: string;
  layout: string;
  citation_refs: number[];
};

export type ResourceSlideArtifact = {
  kind: "slide_deck";
  theme: { name: string; aspect_ratio: "16:9"; accent: string };
  slides: ResourceSlide[];
  citation_refs: number[];
};

export type ResourceAnimationScene = {
  id: string;
  title: string;
  narration: string;
  duration_ms: number;
  diagram: string;
};

export type ResourceAnimationArtifact = {
  kind: "animation";
  scenes: ResourceAnimationScene[];
  default_scene_duration_ms: number;
  citation_refs: number[];
};

export type ResourceArtifact =
  | ResourceDocumentArtifact
  | ResourceMindmapArtifact
  | ResourceQuizArtifact
  | ResourceCodeArtifact
  | ResourceSlideArtifact
  | ResourceAnimationArtifact;

export type GeneratedResourceContent = {
  schema_version?: 1 | 2;
  markdown?: string;
  format?: string;
  topic?: string;
  course_title?: string;
  summary?: string;
  learning_objectives?: string[];
  artifact?: ResourceArtifact;
  citation_summaries?: string[];
  metadata?: {
    agent_trace_id?: string;
    generation_mode?: ResourceGenerationMode;
    difficulty?: ResourceDifficulty;
    has_learning_goal?: boolean;
    source_excerpt_count?: number;
    model_enhancement_failed?: boolean;
    review_mode?: "model_and_rules" | "rules_only" | string;
    repair_count?: number;
    profile_applied_version?: number;
    course_context_hash?: string;
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
  personalization?: PersonalizationFreshness | null;
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
  warnings: string[];
  failed_resource_types: ResourceType[];
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

export async function createResourceExportJob(resourceId: number, format: "pptx" = "pptx") {
  const response = await apiClient.post<ApiEnvelope<ExportJob<"pptx">>>(RESOURCE_ENDPOINTS.exports(resourceId), { format });
  return response.data;
}

export async function listResourceExportJobs(resourceId: number) {
  const response = await apiClient.get<ApiEnvelope<Array<ExportJob<"pptx">>>>(RESOURCE_ENDPOINTS.exports(resourceId));
  return response.data;
}

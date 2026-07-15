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
  exports: (resourceId: number) => `/resources/${resourceId}/exports`,
  interactions: (resourceId: number) => `/resources/${resourceId}/interactions`,
  learningState: (resourceId: number) => `/resources/${resourceId}/learning-state`
} as const;

export type ResourceType = "doc" | "mindmap" | "quiz" | "code" | "slide" | "animation" | "video";
export type ResourceDifficulty = "easy" | "medium" | "hard";
export type ResourceGenerationAction = "new" | "alternative" | "refine";
export type ResourceReviewStatus = "passed" | "low_evidence" | "pending" | "failed" | string;
export type ResourceGenerationMode = "model_enhanced" | "deterministic_source" | "low_evidence_fallback" | string;

export type GenerateResourcesRequest = {
  course_id: number;
  knowledge_point_id?: number | null;
  resource_types: ResourceType[];
  learning_goal?: string;
  difficulty?: ResourceDifficulty;
  generation_action?: ResourceGenerationAction;
  source_resource_id?: number | null;
  path_task_id?: number | null;
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

export type ResourceExternalVideoArtifact = {
  kind: "external_video";
  platform: "youtube" | "bilibili";
  video_id: string;
  title: string;
  watch_url: string;
  embed_url?: string;
  summary?: string;
  topic?: string;
  fit_reason: string;
  embed_status: "available" | "external_only" | string;
  external_supplement: true;
  citation_refs: [];
};

export type ResourceArtifact =
  | ResourceDocumentArtifact
  | ResourceMindmapArtifact
  | ResourceQuizArtifact
  | ResourceCodeArtifact
  | ResourceSlideArtifact
  | ResourceAnimationArtifact
  | ResourceExternalVideoArtifact;

export type GeneratedResourceContent = {
  schema_version?: 1 | 2 | 3;
  markdown?: string;
  format?: string;
  topic?: string;
  course_title?: string;
  summary?: string;
  learning_objectives?: string[];
  artifact?: ResourceArtifact;
  citation_summaries?: string[];
  quality?: {
    status?: "passed" | "failed" | string;
    risk_flags?: string[];
    prompt_version?: string;
    source_coverage?: number;
    model_delta?: boolean;
    code_verification?: {
      status?: "passed" | "failed" | string;
      code?: string;
      output_length?: number;
    } | null;
    dimensions?: Record<string, {
      status?: "passed" | "failed" | string;
      score?: number;
      rationale?: string;
    }>;
  };
  intent?: {
    resource_type?: ResourceType;
    topic?: string;
    learning_goal?: string;
    learning_need?: string;
    resource_role?: string;
    teaching_strategy?: string;
    cognitive_level?: string;
    example_direction?: string;
    interaction_structure?: string;
    evidence_refs?: number[];
    success_criteria?: string[];
    learner_factors?: string[];
    difference_requirements?: string[];
    personalization_status?: "personalized" | "context_limited" | string;
    generation_action?: ResourceGenerationAction;
  };
  personalization_summary?: {
    status?: "personalized" | "context_limited" | string;
    learning_problem?: string;
    teaching_reason?: string;
    difference?: string;
    factors?: string[];
  };
  diversity?: {
    status?: "passed" | "failed" | string;
    score?: number;
    duplicate_sentence_ratio?: number;
    source_similarity?: number;
    semantic_similarity?: number | null;
    semantic_status?: string;
    changed_intent_dimensions?: number;
    comparison_count?: number;
    batch_duplicate_sentence_ratio?: number;
    batch_comparison_count?: number;
    risk_flags?: string[];
  };
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
    generation_action?: ResourceGenerationAction;
    generation_batch_id?: string;
    source_resource_id?: number | null;
    external_supplement?: boolean;
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
  version_family_id?: string | null;
  revision_of_resource_id?: string | null;
  version_number?: number | null;
  generation_action?: ResourceGenerationAction;
  intent_summary?: GeneratedResourceContent["intent"] | null;
  personalization_summary?: GeneratedResourceContent["personalization_summary"] | null;
  quality_dimensions?: NonNullable<GeneratedResourceContent["quality"]>["dimensions"] | null;
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

export type ResourceInteractionType = "opened" | "started" | "progress" | "completed" | "feedback";
export type ResourceFeedback = "helpful" | "too_easy" | "too_hard" | "not_helpful";
export type ResourceLearningState = {
  resource_id: string;
  path_task_id: string | null;
  opened: boolean;
  started: boolean;
  completed: boolean;
  progress_percent: number;
  feedback: ResourceFeedback | null;
  event_count: number;
  updated_at: string | null;
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

export async function recordResourceInteraction(
  resourceId: number,
  payload: {
    event_id: string;
    event_type: ResourceInteractionType;
    path_task_id?: number | null;
    progress_percent?: number | null;
    feedback?: ResourceFeedback | null;
  }
) {
  const response = await apiClient.post<ApiEnvelope<ResourceLearningState>>(RESOURCE_ENDPOINTS.interactions(resourceId), payload);
  return response.data;
}

export async function getResourceLearningState(resourceId: number) {
  const response = await apiClient.get<ApiEnvelope<ResourceLearningState>>(RESOURCE_ENDPOINTS.learningState(resourceId));
  return response.data;
}

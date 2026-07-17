import { apiClient, MODEL_OPERATION_TIMEOUT_MS } from "./client";
import { type ApiEnvelope } from "../types/api";
import type { PersonalizationFreshness } from "./personalization";

export const REPORT_ENDPOINTS = {
  generate: "/reports/generate",
  latest: "/reports/latest"
} as const;

export type GenerateReportRequest = {
  course_id: number;
  practice_session_id?: number;
};

export type AssessmentReportContent = {
  summary: string;
  mastery_update: {
    weak_count: number;
    mastered_count: number;
    learning_count: number;
  };
  weakness_list: Array<{
    knowledge_point_id: string;
    title: string;
    source_type: string;
  }>;
  evidence_refs: Array<{
    practice_answer_id?: string;
    knowledge_point_id?: string;
    score?: number;
  }>;
  next_step_suggestions: string[];
  review_queue_updates: Array<{
    title: string;
    status: string;
    source_type: string;
  }>;
  profile_changes: string[];
  resource_usage_summary?: Partial<Record<
    "doc" | "mindmap" | "quiz" | "code" | "slide" | "animation" | "video",
    {
      opened: number;
      started: number;
      completed: number;
      helpful: number;
      too_easy: number;
      too_hard: number;
      not_helpful: number;
    }
  >>;
  weakness_progress?: {
    active_count: number;
    resolved_count: number;
    due_review_count: number;
    recent_resolutions: Array<{
      title: string;
      baseline_score: number | null;
      latest_score: number | null;
      improvement: number | null;
      next_review_at: string | null;
    }>;
  };
  trend?: {
    direction: "improved" | "declined" | "stable" | "insufficient";
    score_delta: number;
    sessions_compared: number;
    scores: number[];
  };
  evidence_summary?: {
    practice_count: number;
    answer_count: number;
    correct_answer_count?: number;
    assessed_knowledge_point_count?: number;
    completed_path_task_count?: number;
    weakness_count: number;
    path_status: string;
    resource_count: number;
  };
  deterministic_statistics?: {
    practice_session_count: number;
    answered_question_count: number;
    correct_answer_count: number;
    assessed_knowledge_point_count: number;
    completed_path_task_count: number;
  };
  quality?: {
    prompt_version: string;
    review_prompt_version: string;
    statistics_locked: boolean;
  };
  review_result?: {
    review_status: string;
    confidence: number;
    risk_flags: string[];
    safety_summary: string;
  };
};

export type AssessmentReport = {
  id: string | null;
  course_id: string;
  practice_session_id: string | null;
  status: "empty" | "ready" | string;
  agent_trace_id?: string | null;
  score: number | null;
  report: AssessmentReportContent;
  created_at: string | null;
  personalization?: PersonalizationFreshness | null;
};

export async function generateReport(payload: GenerateReportRequest) {
  const response = await apiClient.post<ApiEnvelope<AssessmentReport>>(REPORT_ENDPOINTS.generate, payload, {
    timeout: MODEL_OPERATION_TIMEOUT_MS
  });
  return response.data;
}

export async function getLatestReport(courseId: number) {
  const response = await apiClient.get<ApiEnvelope<AssessmentReport>>(REPORT_ENDPOINTS.latest, {
    params: { course_id: courseId }
  });
  return response.data;
}

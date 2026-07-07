import { apiClient } from "./client";
import { type ApiEnvelope } from "../types/api";

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
};

export async function generateReport(payload: GenerateReportRequest) {
  const response = await apiClient.post<ApiEnvelope<AssessmentReport>>(REPORT_ENDPOINTS.generate, payload);
  return response.data;
}

export async function getLatestReport(courseId: number) {
  const response = await apiClient.get<ApiEnvelope<AssessmentReport>>(REPORT_ENDPOINTS.latest, {
    params: { course_id: courseId }
  });
  return response.data;
}

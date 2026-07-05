import { apiClient } from "./client";
import { type ApiEnvelope } from "../types/api";

export const EXPORT_ENDPOINTS = {
  learningDossier: "/exports/learning-dossier"
} as const;

export type ExportLearningDossierRequest = {
  course_id: number;
};

export type LearningDossierSourceSummary = {
  has_report: boolean;
  report_id: string | null;
  knowledge_point_count: number;
  weakness_count: number;
  path_task_count: number;
  resource_count: number;
  practice_answer_count: number;
};

export type LearningDossierExport = {
  course_id: string;
  filename: string;
  content_type: "text/markdown; charset=utf-8";
  markdown: string;
  generated_at: string;
  source_summary: LearningDossierSourceSummary;
};

export async function exportLearningDossier(payload: ExportLearningDossierRequest) {
  const response = await apiClient.post<ApiEnvelope<LearningDossierExport>>(EXPORT_ENDPOINTS.learningDossier, payload);
  return response.data;
}

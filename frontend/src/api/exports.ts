import { apiClient } from "./client";
import { type ApiEnvelope } from "../types/api";

export const EXPORT_ENDPOINTS = {
  learningDossier: "/exports/learning-dossier",
  learningDossierJob: "/exports/learning-dossier/jobs",
  job: (jobId: number | string) => `/exports/${jobId}`,
  download: (jobId: number | string) => `/exports/${jobId}/download`
} as const;

export type ExportLearningDossierRequest = {
  course_id: number;
};

export type ExportFormat = "markdown" | "pdf" | "docx";

export type CreateLearningDossierExportJobRequest = ExportLearningDossierRequest & {
  format: ExportFormat;
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
  agent_trace_id?: string | null;
  filename: string;
  content_type: "text/markdown; charset=utf-8";
  markdown: string;
  generated_at: string;
  source_summary: LearningDossierSourceSummary;
};

export type ExportJob = {
  job_id: string;
  status: "queued" | "running" | "completed" | "failed";
  format: ExportFormat;
  filename: string;
  content_type: string;
  agent_trace_id?: string | null;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
  completed_at?: string | null;
};

export async function exportLearningDossier(payload: ExportLearningDossierRequest) {
  const response = await apiClient.post<ApiEnvelope<LearningDossierExport>>(EXPORT_ENDPOINTS.learningDossier, payload);
  return response.data;
}

export async function createLearningDossierExportJob(payload: CreateLearningDossierExportJobRequest) {
  const response = await apiClient.post<ApiEnvelope<ExportJob>>(EXPORT_ENDPOINTS.learningDossierJob, payload);
  return response.data;
}

export async function getExportJob(jobId: number | string) {
  const response = await apiClient.get<ApiEnvelope<ExportJob>>(EXPORT_ENDPOINTS.job(jobId));
  return response.data;
}

export async function downloadExportJob(jobId: number | string) {
  const response = await apiClient.get<Blob>(EXPORT_ENDPOINTS.download(jobId), {
    responseType: "blob"
  });
  return response.data;
}

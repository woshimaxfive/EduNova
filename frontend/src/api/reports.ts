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

export async function generateReport(payload: GenerateReportRequest) {
  const response = await apiClient.post<ApiEnvelope<Record<string, unknown>>>(REPORT_ENDPOINTS.generate, payload);
  return response.data;
}

export async function getLatestReport() {
  const response = await apiClient.get<ApiEnvelope<Record<string, unknown>>>(REPORT_ENDPOINTS.latest);
  return response.data;
}

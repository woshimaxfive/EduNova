import { apiClient } from "./client";
import { type ApiEnvelope } from "../types/api";

export const DASHBOARD_ENDPOINTS = {
  summary: "/dashboard/summary"
} as const;

export type DashboardSummary = Record<string, unknown>;

export async function getDashboardSummary() {
  const response = await apiClient.get<ApiEnvelope<DashboardSummary>>(DASHBOARD_ENDPOINTS.summary);
  return response.data;
}

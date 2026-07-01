import { apiClient } from "./client";
import { type ApiEnvelope } from "../types/api";

export const DEMO_ENDPOINTS = {
  reset: "/demo/reset",
  status: "/demo/status"
} as const;

export type DemoResetResult = {
  email: string;
  password_hint: string;
  reset: boolean;
};

export async function resetDemo() {
  const response = await apiClient.post<ApiEnvelope<DemoResetResult>>(DEMO_ENDPOINTS.reset);
  return response.data;
}

export async function getDemoStatus() {
  const response = await apiClient.get<ApiEnvelope<Record<string, unknown>>>(DEMO_ENDPOINTS.status);
  return response.data;
}

import { apiClient } from "./client";
import { type ApiEnvelope } from "../types/api";

export const AGENT_ENDPOINTS = {
  trace: (traceId: string) => `/agents/traces/${encodeURIComponent(traceId)}`
} as const;

export async function getAgentTrace(traceId: string) {
  const response = await apiClient.get<ApiEnvelope<Record<string, unknown>>>(AGENT_ENDPOINTS.trace(traceId));
  return response.data;
}

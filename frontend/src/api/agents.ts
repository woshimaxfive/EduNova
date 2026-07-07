import { apiClient } from "./client";
import { type AgentTraceEvent, type ApiEnvelope } from "../types/api";

export const AGENT_ENDPOINTS = {
  trace: (traceId: string) => `/agents/traces/${encodeURIComponent(traceId)}`
} as const;

export type AgentTraceStatus = "queued" | "pending" | "running" | "completed" | "warning" | "failed" | "error";

export type AgentTraceStep = {
  id: string;
  agent_name: string;
  step_index: number;
  status: AgentTraceStatus;
  input_summary: string | null;
  output_summary: string | null;
  duration_ms: number | null;
  metadata: Record<string, string | number | boolean | string[] | null>;
  created_at: string;
};

export type AgentTrace = {
  trace_id: string;
  workflow: string | null;
  artifact_type: string | null;
  artifact_id: string | null;
  course_id: string | null;
  status: AgentTraceStatus;
  steps: AgentTraceStep[];
};

export async function getAgentTrace(traceId: string) {
  const response = await apiClient.get<ApiEnvelope<AgentTrace>>(AGENT_ENDPOINTS.trace(traceId));
  return response.data;
}

export function mapAgentTraceStepToEvent(step: AgentTraceStep): AgentTraceEvent {
  return {
    id: step.id,
    agentName: step.agent_name,
    summary: step.output_summary || step.input_summary || "已记录执行步骤",
    status: mapAgentTraceStatus(step.status),
    durationMs: step.duration_ms ?? undefined
  };
}

function mapAgentTraceStatus(status: AgentTraceStatus): AgentTraceEvent["status"] {
  if (status === "completed") {
    return "completed";
  }
  if (status === "failed" || status === "error" || status === "warning") {
    return "warning";
  }
  if (status === "running") {
    return "running";
  }
  return "pending";
}

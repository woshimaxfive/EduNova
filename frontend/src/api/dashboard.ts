import { apiClient } from "./client";
import { type ApiEnvelope } from "../types/api";

export const DASHBOARD_ENDPOINTS = {
  summary: "/dashboard/summary"
} as const;

export type DashboardStarterMode = "blank" | "data_structures";

export type DashboardProfileSummary = {
  display_name: string;
  starter_mode: DashboardStarterMode;
  has_profile: boolean;
  knowledge_foundation: string | null;
  learning_goal: string | null;
};

export type DashboardConversation = {
  id: string;
  title: string;
  meta: string;
  scope: "home";
  updated_at: string;
};

export type DashboardCourse = {
  id: string;
  title: string;
  source_type: string;
  progress_label: string;
  practiced_knowledge_point_count: number;
  knowledge_point_count: number;
  focus: string;
  next: string;
};

export type DashboardMaterial = {
  id: string;
  title: string;
  type: string;
  detail: string;
  modified: string;
  size: string;
};

export type DashboardResource = {
  id: string;
  title: string;
  resource_type: string;
  status: string;
  course_id: string | null;
  updated_at: string;
};

export type DashboardSummary = {
  profile_summary: DashboardProfileSummary;
  recent_conversations: DashboardConversation[];
  recent_courses: DashboardCourse[];
  material_library_summary: {
    material_count: number;
    unassigned_count: number;
  };
  recent_materials: DashboardMaterial[];
  recent_resources: DashboardResource[];
  command_suggestions: string[];
  evidence_summary: {
    citation_count: number;
    latest_trace_id: string | null;
    low_evidence_count: number;
  };
  empty_state: {
    kind: "blank" | "starter" | "active";
    title: string;
    description: string;
    action_label: string;
  };
};

export async function getDashboardSummary() {
  const response = await apiClient.get<ApiEnvelope<DashboardSummary>>(DASHBOARD_ENDPOINTS.summary);
  return response.data;
}

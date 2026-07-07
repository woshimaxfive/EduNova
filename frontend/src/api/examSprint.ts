import { apiClient } from "./client";
import { type ApiEnvelope } from "../types/api";

export const EXAM_SPRINT_ENDPOINTS = {
  generate: "/exam-sprint/plans",
  detail: (planId: string | number) => `/exam-sprint/plans/${planId}`
} as const;

export type ExamSprintDuration = 3 | 7 | 14;

export type GenerateExamSprintPlanRequest = {
  course_id: number;
  duration_days: ExamSprintDuration;
  material_ids?: number[];
  goal?: string;
};

export type ExamSprintResourceBrief = {
  id: string;
  title: string;
  resource_type: string;
  knowledge_point_id: string | null;
};

export type ExamSprintPoint = {
  knowledge_point_id: string | null;
  title: string;
  reason: string;
  score: number;
  recommended_resource_ids: string[];
  recommended_resources: ExamSprintResourceBrief[];
};

export type ExamSprintDailyTask = {
  id: string;
  day_index: number;
  title: string;
  task_type: string;
  status: string;
  due_at: string | null;
  knowledge_point_id: string | null;
  reason: string | null;
  recommended_resource_ids: string[];
  recommended_resources: ExamSprintResourceBrief[];
};

export type ExamSprintQuestion = {
  id: string;
  knowledge_point_id: string | null;
  title: string;
  question_type: string;
  prompt: string;
  reason: string;
};

export type ExamSprintWarning = {
  knowledge_point_id: string | null;
  title: string;
  warning: string;
};

export type ExamSprintEvidenceSummary = {
  knowledge_point_count: number;
  weakness_count: number;
  practice_low_score_count: number;
  resource_count: number;
  report_suggestion_count: number;
  material_filter_count: number;
  basis: string[];
};

export type ExamSprintPlan = {
  id: string;
  course_id: string;
  agent_trace_id?: string | null;
  duration_days: ExamSprintDuration | number;
  goal: string | null;
  status: "sprint_active" | "sprint_archived" | string;
  high_frequency_points: ExamSprintPoint[];
  weak_points: ExamSprintPoint[];
  daily_tasks: ExamSprintDailyTask[];
  must_do_questions: ExamSprintQuestion[];
  easy_mistake_warnings: ExamSprintWarning[];
  recommended_resources: ExamSprintResourceBrief[];
  evidence_summary: ExamSprintEvidenceSummary;
  created_at: string;
  updated_at: string;
};

export async function generateExamSprintPlan(payload: GenerateExamSprintPlanRequest) {
  const response = await apiClient.post<ApiEnvelope<ExamSprintPlan>>(EXAM_SPRINT_ENDPOINTS.generate, payload);
  return response.data;
}

export async function getExamSprintPlan(planId: string | number) {
  const response = await apiClient.get<ApiEnvelope<ExamSprintPlan>>(EXAM_SPRINT_ENDPOINTS.detail(planId));
  return response.data;
}

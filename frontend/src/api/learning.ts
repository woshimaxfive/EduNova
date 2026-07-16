import { apiClient } from "./client";
import { type ApiEnvelope } from "../types/api";

export const LEARNING_ENDPOINTS = {
  nextAction: "/learning/next-action"
} as const;

export type LearningNextActionStatus = "ready" | "waiting" | "blocked";

export type LearningNextAction = {
  kind: string;
  status: LearningNextActionStatus;
  label: string;
  description: string;
  course_id: string | null;
  material_id: string | null;
  knowledge_point_id: string | null;
  path_task_id: string | null;
  resource_id: string | null;
  weakness_item_id?: string | null;
};

export async function getLearningNextAction(courseId?: number | null) {
  const response = await apiClient.get<ApiEnvelope<LearningNextAction>>(LEARNING_ENDPOINTS.nextAction, {
    params: courseId ? { course_id: courseId } : undefined
  });
  return response.data;
}

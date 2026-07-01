import { apiClient } from "./client";
import { type ApiEnvelope } from "../types/api";

export const PRACTICE_ENDPOINTS = {
  sessions: "/practice/sessions",
  detail: (sessionId: number) => `/practice/sessions/${sessionId}`,
  answers: (sessionId: number) => `/practice/sessions/${sessionId}/answers`
} as const;

export type CreatePracticeSessionRequest = {
  course_id: number;
  knowledge_point_ids: number[];
  question_count: number;
  difficulty: "easy" | "medium" | "hard";
};

export type SubmitPracticeAnswersRequest = {
  answers: Array<{
    question_id: string;
    answer_text: string;
  }>;
};

export async function createPracticeSession(payload: CreatePracticeSessionRequest) {
  const response = await apiClient.post<ApiEnvelope<Record<string, unknown>>>(PRACTICE_ENDPOINTS.sessions, payload);
  return response.data;
}

export async function getPracticeSession(sessionId: number) {
  const response = await apiClient.get<ApiEnvelope<Record<string, unknown>>>(PRACTICE_ENDPOINTS.detail(sessionId));
  return response.data;
}

export async function submitPracticeAnswers(sessionId: number, payload: SubmitPracticeAnswersRequest) {
  const response = await apiClient.post<ApiEnvelope<Record<string, unknown>>>(
    PRACTICE_ENDPOINTS.answers(sessionId),
    payload
  );
  return response.data;
}

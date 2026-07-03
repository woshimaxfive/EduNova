import { apiClient } from "./client";
import { type ApiEnvelope } from "../types/api";
import { type RagSearchResultItem } from "./rag";

export const TUTOR_ENDPOINTS = {
  sessions: "/tutor/sessions",
  detail: (sessionId: number | string) => `/tutor/sessions/${sessionId}`,
  message: (sessionId: number | string) => `/tutor/sessions/${sessionId}/messages`,
  stream: (sessionId: number | string) => `/tutor/sessions/${sessionId}/stream`
} as const;

export type TutorSessionScope = "home" | "course";
export type TutorSessionMode = "chat" | "socratic" | "direct";

export type CreateTutorSessionRequest = {
  scope: TutorSessionScope;
  course_id: number | null;
  mode: TutorSessionMode;
  title: string;
};

export type SendTutorMessageRequest = {
  message: string;
};

export type TutorSessionSummary = {
  id: string;
  scope: TutorSessionScope;
  course_id: string | null;
  title: string;
  mode: TutorSessionMode;
  archived_from_home: boolean;
  created_at: string;
  updated_at: string;
};

export type TutorCitation = RagSearchResultItem;

export type TutorMessage = {
  id: string;
  session_id: string;
  role: "user" | "assistant";
  content: string;
  citation_json: TutorCitation[];
  trace_id: string | null;
  created_at: string;
};

export type TutorSessionDetail = {
  session: TutorSessionSummary;
  messages: TutorMessage[];
};

export async function createTutorSession(payload: CreateTutorSessionRequest) {
  const response = await apiClient.post<ApiEnvelope<TutorSessionSummary>>(TUTOR_ENDPOINTS.sessions, payload);
  return response.data;
}

export async function listTutorSessions(scope: TutorSessionScope = "home", courseId?: number | null) {
  const params = courseId === undefined || courseId === null ? { scope } : { scope, course_id: courseId };

  const response = await apiClient.get<ApiEnvelope<TutorSessionSummary[]>>(TUTOR_ENDPOINTS.sessions, {
    params
  });
  return response.data;
}

export async function getTutorSession(sessionId: number | string) {
  const response = await apiClient.get<ApiEnvelope<TutorSessionDetail>>(TUTOR_ENDPOINTS.detail(sessionId));
  return response.data;
}

export async function sendTutorMessage(sessionId: number | string, payload: SendTutorMessageRequest) {
  const response = await apiClient.post<ApiEnvelope<TutorSessionDetail>>(TUTOR_ENDPOINTS.message(sessionId), payload);
  return response.data;
}

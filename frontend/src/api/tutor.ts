import { apiClient } from "./client";
import { type ApiEnvelope, type ApiListEnvelope } from "../types/api";

export const TUTOR_ENDPOINTS = {
  sessions: "/tutor/sessions",
  detail: (sessionId: number) => `/tutor/sessions/${sessionId}`,
  message: (sessionId: number) => `/tutor/sessions/${sessionId}/messages`,
  stream: (sessionId: number) => `/tutor/sessions/${sessionId}/stream`
} as const;

export type CreateTutorSessionRequest = {
  course_id: number;
  mode: "socratic" | "direct";
  title: string;
};

export type SendTutorMessageRequest = {
  message: string;
};

export async function createTutorSession(payload: CreateTutorSessionRequest) {
  const response = await apiClient.post<ApiEnvelope<Record<string, unknown>>>(TUTOR_ENDPOINTS.sessions, payload);
  return response.data;
}

export async function listTutorSessions() {
  const response = await apiClient.get<ApiListEnvelope<Record<string, unknown>>>(TUTOR_ENDPOINTS.sessions);
  return response.data;
}

export async function getTutorSession(sessionId: number) {
  const response = await apiClient.get<ApiEnvelope<Record<string, unknown>>>(TUTOR_ENDPOINTS.detail(sessionId));
  return response.data;
}

export async function sendTutorMessage(sessionId: number, payload: SendTutorMessageRequest) {
  const response = await apiClient.post<ApiEnvelope<Record<string, unknown>>>(
    TUTOR_ENDPOINTS.message(sessionId),
    payload
  );
  return response.data;
}

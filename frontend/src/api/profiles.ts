import { apiClient } from "./client";
import { type ApiEnvelope } from "../types/api";

export const PROFILE_ENDPOINTS = {
  me: "/profiles/me",
  chat: "/profiles/chat",
  events: "/profiles/events"
} as const;

export type ProfileChatRequest = {
  message: string;
};

export async function getMyProfile() {
  const response = await apiClient.get<ApiEnvelope<Record<string, unknown>>>(PROFILE_ENDPOINTS.me);
  return response.data;
}

export async function updateProfileByChat(payload: ProfileChatRequest) {
  const response = await apiClient.post<ApiEnvelope<Record<string, unknown>>>(PROFILE_ENDPOINTS.chat, payload);
  return response.data;
}

export async function listProfileEvents() {
  const response = await apiClient.get<ApiEnvelope<Record<string, unknown>[]>>(PROFILE_ENDPOINTS.events);
  return response.data;
}

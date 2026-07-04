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

export type ProfileJson = {
  major_background: string;
  knowledge_foundation: string;
  learning_goal: string;
  cognitive_style: string;
  learning_preference: string;
  weak_points: string[];
  learning_pace: string;
  motivation_interest: string;
};

export type StudentProfileResponse = {
  id: string | null;
  version: number;
  has_profile: boolean;
  profile_json: ProfileJson;
  confidence_score: number;
  updated_reason: string | null;
  updated_at: string | null;
  next_question: string;
};

export type ProfileEventResponse = {
  id: string;
  dimension: string;
  change_summary: string;
  evidence_json: Record<string, unknown>;
  created_at: string;
};

export type ProfileChatResponse = {
  reply: string;
  profile: StudentProfileResponse;
  event: ProfileEventResponse;
};

export async function getMyProfile() {
  const response = await apiClient.get<ApiEnvelope<StudentProfileResponse>>(PROFILE_ENDPOINTS.me);
  return response.data;
}

export async function updateProfileByChat(payload: ProfileChatRequest) {
  const response = await apiClient.post<ApiEnvelope<ProfileChatResponse>>(PROFILE_ENDPOINTS.chat, payload);
  return response.data;
}

export async function listProfileEvents() {
  const response = await apiClient.get<ApiEnvelope<ProfileEventResponse[]>>(PROFILE_ENDPOINTS.events);
  return response.data;
}

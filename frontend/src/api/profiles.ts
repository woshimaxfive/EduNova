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
  dimension_confidence?: Partial<Record<keyof ProfileJson, number>>;
  evidence_summary?: {
    candidate_count?: number;
    applied_count?: number;
    last_trace_id?: string | null;
  };
  updated_reason: string | null;
  updated_at: string | null;
  next_question: string;
  next_question_dimension?: keyof ProfileJson | null;
};

export type ProfileEventResponse = {
  id: string;
  dimension: string;
  change_summary: string;
  evidence_json: Record<string, unknown>;
  agent_trace_id?: string | null;
  source_type?: string;
  source_ref_type?: string | null;
  source_ref_id?: string | null;
  status?: "candidate" | "applied" | string;
  confidence_score?: number | null;
  created_at: string;
};

export type ProfileChatResponse = {
  reply: string;
  agent_trace_id?: string | null;
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

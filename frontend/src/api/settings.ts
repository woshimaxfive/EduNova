import { apiClient } from "./client";
import { type ApiEnvelope } from "../types/api";

export const SETTINGS_ENDPOINTS = {
  model: "/settings/model",
  testModel: "/settings/model/test"
} as const;

export type ModelSettingsSource = "user" | "system" | "none";

export type ModelSettingsProvider = "openai_compatible";

export type ModelSettingsRequest = {
  provider: ModelSettingsProvider;
  base_url: string;
  api_key?: string;
  chat_model: string;
  embedding_model: string;
};

export type ModelSettingsSummary = {
  source: ModelSettingsSource;
  provider: ModelSettingsProvider;
  base_url: string | null;
  chat_model: string | null;
  embedding_model: string | null;
  has_api_key: boolean;
  api_key_masked: string | null;
  can_use_model: boolean;
};

export type ModelConnectionTestResponse = {
  ok: boolean;
  source: ModelSettingsSource;
  chat_model: string | null;
  message: string;
};

export async function getModelSettings() {
  const response = await apiClient.get<ApiEnvelope<ModelSettingsSummary>>(SETTINGS_ENDPOINTS.model);
  return response.data;
}

export async function saveModelSettings(payload: ModelSettingsRequest) {
  const response = await apiClient.put<ApiEnvelope<ModelSettingsSummary>>(SETTINGS_ENDPOINTS.model, payload);
  return response.data;
}

export async function testModelSettings() {
  const response = await apiClient.post<ApiEnvelope<ModelConnectionTestResponse>>(SETTINGS_ENDPOINTS.testModel);
  return response.data;
}

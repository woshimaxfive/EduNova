import { apiClient } from "./client";
import { type ApiEnvelope } from "../types/api";

export const SETTINGS_ENDPOINTS = {
  model: "/settings/model",
  testModel: "/settings/model/test"
} as const;

export type ModelSettingsRequest = {
  provider: "openai_compatible";
  base_url: string;
  api_key: string;
  chat_model: string;
  embedding_model: string;
};

export async function getModelSettings() {
  const response = await apiClient.get<ApiEnvelope<Record<string, unknown>>>(SETTINGS_ENDPOINTS.model);
  return response.data;
}

export async function saveModelSettings(payload: ModelSettingsRequest) {
  const response = await apiClient.put<ApiEnvelope<Record<string, unknown>>>(SETTINGS_ENDPOINTS.model, payload);
  return response.data;
}

export async function testModelSettings() {
  const response = await apiClient.post<ApiEnvelope<Record<string, unknown>>>(SETTINGS_ENDPOINTS.testModel);
  return response.data;
}

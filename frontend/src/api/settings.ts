import { apiClient } from "./client";
import { type ApiEnvelope } from "../types/api";

export const SETTINGS_ENDPOINTS = {
  model: "/settings/model",
  testModel: "/settings/model/test",
  configs: "/settings/model/configs",
  config: (configId: number) => `/settings/model/configs/${configId}`,
  testConfig: (configId: number) => `/settings/model/configs/${configId}/test`,
  defaultConfig: (configId: number) => `/settings/model/configs/${configId}/default`
} as const;

export type ModelSettingsSource = "user" | "system" | "none";

export type ModelSettingsProvider = "openai_compatible";

export type ModelSettingsRequest = {
  provider: ModelSettingsProvider;
  base_url: string;
  api_key?: string;
  chat_model: string;
  embedding_model?: string;
};

export type ModelConfigRequest = ModelSettingsRequest & {
  display_name: string;
  preset_id?: string | null;
  make_default?: boolean;
};

export type ModelConfigUpdateRequest = Partial<ModelSettingsRequest> & {
  display_name?: string;
  preset_id?: string | null;
  is_default?: boolean;
  make_default?: boolean;
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

export type ModelConfigSummary = ModelSettingsSummary & {
  id: number;
  display_name: string;
  preset_id: string | null;
  is_default: boolean;
  last_test_ok: boolean | null;
  last_test_message: string | null;
  last_tested_at: string | null;
};

export type ModelSettingsListResponse = {
  configs: ModelConfigSummary[];
  default_config_id: number | null;
  system_summary: ModelSettingsSummary;
};

export type ModelConnectionTestResponse = {
  ok: boolean;
  source: ModelSettingsSource;
  chat_model: string | null;
  message: string;
  config_id?: number | null;
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

export async function listModelConfigs() {
  const response = await apiClient.get<ApiEnvelope<ModelSettingsListResponse>>(SETTINGS_ENDPOINTS.configs);
  return response.data;
}

export async function createModelConfig(payload: ModelConfigRequest) {
  const response = await apiClient.post<ApiEnvelope<ModelConfigSummary>>(SETTINGS_ENDPOINTS.configs, payload);
  return response.data;
}

export async function updateModelConfig(configId: number, payload: ModelConfigUpdateRequest) {
  const response = await apiClient.patch<ApiEnvelope<ModelConfigSummary>>(SETTINGS_ENDPOINTS.config(configId), payload);
  return response.data;
}

export async function deleteModelConfig(configId: number) {
  const response = await apiClient.delete<ApiEnvelope<ModelSettingsListResponse>>(SETTINGS_ENDPOINTS.config(configId));
  return response.data;
}

export async function setDefaultModelConfig(configId: number) {
  const response = await apiClient.post<ApiEnvelope<ModelSettingsListResponse>>(SETTINGS_ENDPOINTS.defaultConfig(configId));
  return response.data;
}

export async function testModelConfig(configId: number) {
  const response = await apiClient.post<ApiEnvelope<ModelConnectionTestResponse>>(SETTINGS_ENDPOINTS.testConfig(configId));
  return response.data;
}

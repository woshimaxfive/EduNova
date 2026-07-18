import { apiClient } from "./client";
import { type ApiEnvelope } from "../types/api";
import { type AiJob } from "./aiJobs";

export const SETTINGS_ENDPOINTS = {
  model: "/settings/model",
  testModel: "/settings/model/test",
  configs: "/settings/model/configs",
  config: (configId: number) => `/settings/model/configs/${configId}`,
  testConfig: (configId: number) => `/settings/model/configs/${configId}/test`,
  defaultConfig: (configId: number) => `/settings/model/configs/${configId}/default`,
  generationDefaultConfig: (configId: number) => `/settings/model/configs/${configId}/generation-default`,
  embeddingDefaultConfig: (configId: number) => `/settings/model/configs/${configId}/embedding-default`,
  rerankDefaultConfig: (configId: number) => `/settings/model/configs/${configId}/rerank-default`,
  visionDefaultConfig: (configId: number) => `/settings/model/configs/${configId}/vision-default`,
  embeddingReindexJobs: "/settings/model/embedding/reindex-jobs",
  privacy: "/settings/privacy",
  conversationMemory: "/settings/privacy/conversation-memory"
} as const;

export type ModelSettingsSource = "user" | "system" | "none";

export type ModelSettingsProvider = "openai_compatible" | "xfyun_embedding" | "siliconflow_rerank" | "bailian_rerank";

export type ModelConnectionOperation = "chat" | "structured" | "embedding" | "rerank" | "vision";

export type ModelSettingsRequest = {
  provider: ModelSettingsProvider;
  base_url: string;
  api_key?: string;
  chat_model?: string;
  vision_app_id?: string;
  vision_api_key?: string;
  vision_api_secret?: string;
  embedding_provider?: ModelSettingsProvider;
  embedding_base_url?: string;
  embedding_api_key?: string;
  embedding_app_id?: string;
  embedding_api_secret?: string;
  embedding_model?: string;
  embedding_dimension?: number | null;
  rerank_provider?: ModelSettingsProvider;
  rerank_base_url?: string;
  rerank_api_key?: string;
  rerank_model?: string;
  rerank_workspace_id?: string;
};

export type ModelConfigRequest = ModelSettingsRequest & {
  display_name: string;
  preset_id?: string | null;
  embedding_preset_id?: string | null;
  rerank_preset_id?: string | null;
  make_default?: boolean;
  make_generation_default?: boolean;
  make_embedding_default?: boolean;
  make_rerank_default?: boolean;
  make_vision_default?: boolean;
};

export type ModelConfigUpdateRequest = Partial<ModelSettingsRequest> & {
  display_name?: string;
  preset_id?: string | null;
  embedding_preset_id?: string | null;
  rerank_preset_id?: string | null;
  is_default?: boolean;
  make_default?: boolean;
  make_generation_default?: boolean;
  make_vision_default?: boolean;
};

export type ModelSettingsSummary = {
  source: ModelSettingsSource;
  provider: ModelSettingsProvider;
  base_url: string | null;
  chat_model: string | null;
  embedding_model: string | null;
  embedding_provider?: ModelSettingsProvider | null;
  embedding_base_url?: string | null;
  embedding_dimension?: number | null;
  has_api_key: boolean;
  api_key_masked: string | null;
  has_vision_app_id?: boolean;
  vision_app_id_masked?: string | null;
  has_vision_api_key?: boolean;
  vision_api_key_masked?: string | null;
  has_vision_api_secret?: boolean;
  has_embedding_api_key?: boolean;
  embedding_api_key_masked?: string | null;
  has_embedding_app_id?: boolean;
  embedding_app_id_masked?: string | null;
  has_embedding_api_secret?: boolean;
  rerank_model?: string | null;
  rerank_provider?: ModelSettingsProvider | null;
  rerank_base_url?: string | null;
  rerank_workspace_id?: string | null;
  has_rerank_api_key?: boolean;
  rerank_api_key_masked?: string | null;
  can_use_model: boolean;
  can_use_embedding_model: boolean;
  can_use_rerank_model?: boolean;
  vision_model?: string | null;
  vision_provider?: string | null;
  vision_base_url?: string | null;
  can_use_vision_model?: boolean;
  supports_structured_output?: boolean;
  supports_reasoning_control?: boolean;
};

export type ModelConfigSummary = ModelSettingsSummary & {
  id: number;
  display_name: string;
  preset_id: string | null;
  embedding_preset_id?: string | null;
  rerank_preset_id?: string | null;
  is_default: boolean;
  is_generation_default?: boolean;
  is_embedding_default: boolean;
  is_rerank_default?: boolean;
  is_vision_default?: boolean;
  last_test_ok: boolean | null;
  last_test_message: string | null;
  last_tested_at: string | null;
  connection_tests?: Partial<Record<ModelConnectionOperation, ModelConnectionTestSnapshot>>;
  structured_output_verified?: boolean;
};

export type ModelConnectionTestSnapshot = {
  operation: ModelConnectionOperation;
  ok: boolean;
  model: string | null;
  message: string;
  code: string | null;
  retryable: boolean;
  tested_at: string;
  dimension?: number | null;
  latency_ms?: number | null;
  reasoning_tokens?: number | null;
};

export type ModelSettingsListResponse = {
  configs: ModelConfigSummary[];
  default_config_id: number | null;
  default_chat_config_id: number | null;
  default_generation_config_id?: number | null;
  default_embedding_config_id: number | null;
  default_rerank_config_id?: number | null;
  default_vision_config_id?: number | null;
  system_summary: ModelSettingsSummary;
};

export type ModelConnectionTestResponse = {
  ok: boolean;
  source: ModelSettingsSource;
  chat_model: string | null;
  message: string;
  config_id?: number | null;
  operation: ModelConnectionOperation;
  model: string | null;
  code: string | null;
  retryable: boolean;
  tested_at: string;
  dimension?: number | null;
  latency_ms?: number | null;
  reasoning_tokens?: number | null;
};

export type PrivacySettings = {
  conversation_memory_enabled: boolean;
  indexed_memory_count: number;
};

export type ClearConversationMemoryResponse = {
  deleted_count: number;
  raw_chat_history_preserved: boolean;
};

export async function getModelSettings() {
  const response = await apiClient.get<ApiEnvelope<ModelSettingsSummary>>(SETTINGS_ENDPOINTS.model);
  return response.data;
}

export async function saveModelSettings(payload: ModelSettingsRequest) {
  const response = await apiClient.put<ApiEnvelope<ModelSettingsSummary>>(SETTINGS_ENDPOINTS.model, payload);
  return response.data;
}

export async function testModelSettings(operation: ModelConnectionOperation = "chat") {
  const response = await apiClient.post<ApiEnvelope<ModelConnectionTestResponse>>(SETTINGS_ENDPOINTS.testModel, { operation });
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

export async function setDefaultGenerationConfig(configId: number) {
  const response = await apiClient.post<ApiEnvelope<ModelSettingsListResponse>>(
    SETTINGS_ENDPOINTS.generationDefaultConfig(configId)
  );
  return response.data;
}

export async function setDefaultEmbeddingConfig(configId: number) {
  const response = await apiClient.post<ApiEnvelope<ModelSettingsListResponse>>(
    SETTINGS_ENDPOINTS.embeddingDefaultConfig(configId)
  );
  return response.data;
}

export async function setDefaultRerankConfig(configId: number) {
  const response = await apiClient.post<ApiEnvelope<ModelSettingsListResponse>>(
    SETTINGS_ENDPOINTS.rerankDefaultConfig(configId)
  );
  return response.data;
}

export async function setDefaultVisionConfig(configId: number) {
  const response = await apiClient.post<ApiEnvelope<ModelSettingsListResponse>>(
    SETTINGS_ENDPOINTS.visionDefaultConfig(configId)
  );
  return response.data;
}

export async function testModelConfig(configId: number, operation: ModelConnectionOperation = "chat") {
  const response = await apiClient.post<ApiEnvelope<ModelConnectionTestResponse>>(
    SETTINGS_ENDPOINTS.testConfig(configId),
    { operation }
  );
  return response.data;
}

export async function createEmbeddingReindexJob(configId: number, idempotencyKey: string) {
  const response = await apiClient.post<ApiEnvelope<AiJob>>(
    SETTINGS_ENDPOINTS.embeddingReindexJobs,
    { config_id: configId },
    { headers: { "Idempotency-Key": idempotencyKey } }
  );
  return response.data.data;
}

export async function getPrivacySettings() {
  const response = await apiClient.get<ApiEnvelope<PrivacySettings>>(SETTINGS_ENDPOINTS.privacy);
  return response.data;
}

export async function updatePrivacySettings(conversationMemoryEnabled: boolean) {
  const response = await apiClient.put<ApiEnvelope<PrivacySettings>>(SETTINGS_ENDPOINTS.privacy, {
    conversation_memory_enabled: conversationMemoryEnabled
  });
  return response.data;
}

export async function clearConversationMemory() {
  const response = await apiClient.delete<ApiEnvelope<ClearConversationMemoryResponse>>(
    SETTINGS_ENDPOINTS.conversationMemory
  );
  return response.data;
}

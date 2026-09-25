import { apiClient } from "./client";
import type { ApiEnvelope } from "../types/api";
import type { components } from "../types/openapi.generated";

export type ModelUsageReport = components["schemas"]["ModelUsageReport"];

export async function getModelUsage(days: number) {
  const response = await apiClient.get<ApiEnvelope<ModelUsageReport>>("/settings/model/usage", { params: { days } });
  return response.data.data;
}

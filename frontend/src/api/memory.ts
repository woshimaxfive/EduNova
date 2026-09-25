import { apiClient } from "./client";
import type { ApiEnvelope } from "../types/api";
import type { components } from "../types/openapi.generated";

export type MemoryItem = components["schemas"]["MemoryItem"];
export type MemoryLayer = MemoryItem["layer"];
export type MemoryPage = components["schemas"]["MemoryPage"];
export type MemoryFactInput = components["schemas"]["ConfirmedMemoryRequest"];
const root = "/settings/privacy";

export async function listMemories(layer: MemoryLayer, page: number) {
  return (await apiClient.get<ApiEnvelope<MemoryPage>>(`${root}/memories`, { params: { layer, page, page_size: 20 } })).data.data;
}
export async function createMemory(payload: MemoryFactInput) {
  return (await apiClient.post<ApiEnvelope<MemoryItem>>(`${root}/memories/facts`, payload)).data.data;
}
export async function correctMemory(item: MemoryItem, content: string) {
  return (await apiClient.patch<ApiEnvelope<MemoryItem>>(`${root}/memories/${item.layer}/${item.id}`, {
    content, revision: item.revision, confirmed: true
  })).data.data;
}
export async function deleteMemory(item: MemoryItem) {
  return (await apiClient.delete(`${root}/memories/${item.layer}/${item.id}`, { params: { revision: item.revision } })).data;
}
export async function clearMemoryIndexes() {
  return (await apiClient.delete(`${root}/memory-indexes`)).data;
}
export async function rebuildMemoryIndexes() {
  return (await apiClient.post(`${root}/memory-indexes/rebuild`)).data;
}
export async function exportMemories() {
  return (await apiClient.get<ApiEnvelope<components["schemas"]["MemoryExport"]>>(`${root}/memories/export`)).data.data;
}

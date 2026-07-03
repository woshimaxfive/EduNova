import { apiClient } from "./client";
import { type ApiEnvelope } from "../types/api";

export const RAG_ENDPOINTS = {
  search: "/rag/search"
} as const;

export type RagSearchRequest = {
  course_id: number;
  query: string;
  top_k: number;
};

export type RagSearchResultItem = {
  chunk_id: number;
  course_id: number;
  material_id: number;
  knowledge_point_id: number | null;
  content: string;
  source_title: string;
  page_number: number | null;
  section_title: string | null;
  score: number;
};

export type RagSearchResponse = {
  course_id: number;
  query: string;
  top_k: number;
  results: RagSearchResultItem[];
};

export async function searchRag(payload: RagSearchRequest) {
  const response = await apiClient.post<ApiEnvelope<RagSearchResponse>>(RAG_ENDPOINTS.search, payload);
  return response.data;
}

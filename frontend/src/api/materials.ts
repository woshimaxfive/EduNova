import { apiClient } from "./client";
import { type ApiEnvelope, type MaterialProgressStatus } from "../types/api";

export const MATERIAL_ENDPOINTS = {
  upload: "/materials/upload",
  detail: (materialId: number) => `/materials/${materialId}`,
  progress: (materialId: number) => `/materials/${materialId}/progress`,
  compare: "/materials/compare"
} as const;

export type UploadMaterialRequest = {
  courseId?: number;
  file: File;
};

export type UploadMaterialResult = {
  material_id: number;
  course_id: number;
  filename: string;
  parse_status: MaterialProgressStatus;
};

export type MaterialProgress = {
  status: MaterialProgressStatus;
  progress_percent: number;
  message: string;
};

export type CompareMaterialsRequest = {
  course_id: number;
  material_ids: number[];
};

export async function uploadMaterial(payload: UploadMaterialRequest) {
  const formData = new FormData();
  formData.append("file", payload.file);
  if (payload.courseId) {
    formData.append("course_id", String(payload.courseId));
  }

  const response = await apiClient.post<ApiEnvelope<UploadMaterialResult>>(MATERIAL_ENDPOINTS.upload, formData);
  return response.data;
}

export async function getMaterial(materialId: number) {
  const response = await apiClient.get<ApiEnvelope<Record<string, unknown>>>(MATERIAL_ENDPOINTS.detail(materialId));
  return response.data;
}

export async function getMaterialProgress(materialId: number) {
  const response = await apiClient.get<ApiEnvelope<MaterialProgress>>(MATERIAL_ENDPOINTS.progress(materialId));
  return response.data;
}

export async function compareMaterials(payload: CompareMaterialsRequest) {
  const response = await apiClient.post<ApiEnvelope<Record<string, unknown>>>(MATERIAL_ENDPOINTS.compare, payload);
  return response.data;
}

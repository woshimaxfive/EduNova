import { apiClient } from "./client";
import { type ApiEnvelope, type MaterialProgressStatus } from "../types/api";

export const MATERIAL_ENDPOINTS = {
  upload: "/materials/upload",
  list: "/materials",
  detail: (materialId: number) => `/materials/${materialId}`,
  progress: (materialId: number) => `/materials/${materialId}/progress`,
  compare: "/materials/compare",
  latestComparison: "/materials/comparisons/latest",
  comparisonDetail: (comparisonId: number) => `/materials/comparisons/${comparisonId}`,
  attachToCourse: (courseId: number) => `/courses/${courseId}/materials`
} as const;

export type UploadMaterialRequest = {
  courseId?: number;
  file: File;
};

export type UploadMaterialResult = {
  id: string;
  material_id: number;
  course_id: number | null;
  agent_trace_id?: string | null;
  filename: string;
  title: string;
  type: string;
  detail: string;
  modified: string;
  size: string;
  parse_status: MaterialProgressStatus;
};

export type MaterialListItem = {
  id: string;
  title: string;
  type: string;
  detail: string;
  modified: string;
  size: string;
  category: "document" | "image";
  extension: string;
  parse_status: MaterialProgressStatus;
  course_ids: string[];
};

export type MaterialDetail = MaterialListItem & {
  filename: string;
  content_type: string;
  extracted_text_preview: string | null;
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

export type MaterialComparisonSummary = {
  compared_material_count: number;
  comparable_material_count: number;
  matched_concept_count: number;
  citation_count: number;
  message: string;
};

export type MaterialComparisonPoint = {
  title: string;
  material_ids: string[];
  source_titles: string[];
  reason: string;
  confidence: "high" | "medium" | "low" | string;
  support_count: number;
  knowledge_point_id: string | null;
};

export type MaterialComparisonCitation = {
  id: string;
  material_id: string;
  source_title: string;
  section_title: string | null;
  page_number: number | null;
  excerpt: string;
  confidence: "high" | "medium" | "low" | string;
};

export type MaterialComparisonResult = {
  id?: string | null;
  course_id: string;
  material_ids: string[];
  agent_trace_id?: string | null;
  generation_mode?: "model_enhanced" | "deterministic_source" | string;
  review_mode?: "model_and_rules" | "rules_only" | string;
  review_result?: {
    review_status: string;
    confidence: number;
    risk_flags: string[];
    safety_summary: string;
  } | null;
  warnings?: string[];
  created_at?: string | null;
  summary: MaterialComparisonSummary;
  repeated_concepts: MaterialComparisonPoint[];
  exam_likely_points: MaterialComparisonPoint[];
  materials_only_points: MaterialComparisonPoint[];
  questions_only_points: MaterialComparisonPoint[];
  missing_review_points: MaterialComparisonPoint[];
  priority_order: MaterialComparisonPoint[];
  citations: MaterialComparisonCitation[];
};

export type AttachCourseMaterialsRequest = {
  material_ids: number[];
};

export type AttachCourseMaterialsResult = {
  course_id: string;
  material_ids: string[];
  attached_count: number;
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

export async function listMaterials(params?: { courseId?: number; unassigned?: boolean }) {
  const response = await apiClient.get<ApiEnvelope<MaterialListItem[]>>(MATERIAL_ENDPOINTS.list, {
    params: {
      course_id: params?.courseId,
      unassigned: params?.unassigned
    }
  });
  return response.data;
}

export async function getMaterial(materialId: number) {
  const response = await apiClient.get<ApiEnvelope<MaterialDetail>>(MATERIAL_ENDPOINTS.detail(materialId));
  return response.data;
}

export async function getMaterialProgress(materialId: number) {
  const response = await apiClient.get<ApiEnvelope<MaterialProgress>>(MATERIAL_ENDPOINTS.progress(materialId));
  return response.data;
}

export async function compareMaterials(payload: CompareMaterialsRequest) {
  const response = await apiClient.post<ApiEnvelope<MaterialComparisonResult>>(MATERIAL_ENDPOINTS.compare, payload);
  return response.data;
}

export async function getLatestMaterialComparison(courseId: number) {
  const response = await apiClient.get<ApiEnvelope<MaterialComparisonResult | null>>(MATERIAL_ENDPOINTS.latestComparison, {
    params: { course_id: courseId }
  });
  return response.data;
}

export async function getMaterialComparison(comparisonId: number) {
  const response = await apiClient.get<ApiEnvelope<MaterialComparisonResult>>(MATERIAL_ENDPOINTS.comparisonDetail(comparisonId));
  return response.data;
}

export async function attachCourseMaterials(courseId: number, payload: AttachCourseMaterialsRequest) {
  const response = await apiClient.post<ApiEnvelope<AttachCourseMaterialsResult>>(MATERIAL_ENDPOINTS.attachToCourse(courseId), payload);
  return response.data;
}

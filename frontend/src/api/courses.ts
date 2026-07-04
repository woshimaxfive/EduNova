import { apiClient } from "./client";
import { type ApiEnvelope, type ApiListEnvelope } from "../types/api";

export const COURSE_ENDPOINTS = {
  list: "/courses",
  detail: (courseId: number) => `/courses/${courseId}`,
  overview: (courseId: number) => `/courses/${courseId}/overview`,
  knowledgePoints: (courseId: number) => `/courses/${courseId}/knowledge-points`,
  masteryMap: (courseId: number) => `/courses/${courseId}/mastery-map`,
  fromMaterials: "/courses/from-materials"
} as const;

export type CreateCourseFromMaterialsRequest = {
  material_ids: number[];
  course_title: string;
};

export type ApiCourseSummary = {
  id: string;
  title: string;
  description: string;
  subject: string;
  source_type: "builtin" | "uploaded" | "generated";
  status: string;
  progress_percent: number;
  material_count: number;
  knowledge_point_count: number;
  chunk_count: number;
};

export type ApiCourseKnowledgePoint = {
  id: string;
  title: string;
  summary: string | null;
  chapter: string | null;
  order_index: number;
  difficulty: string | null;
};

export type ApiCourseOverview = {
  course: ApiCourseSummary;
  materials: string[];
  knowledge_points: ApiCourseKnowledgePoint[];
  chunk_count: number;
};

export type CreateCourseFromMaterialsResult = {
  course: ApiCourseSummary;
  knowledge_points: ApiCourseKnowledgePoint[];
};

export async function listCourses(sourceType?: "builtin" | "uploaded") {
  const response = await apiClient.get<ApiListEnvelope<ApiCourseSummary>>(COURSE_ENDPOINTS.list, {
    params: sourceType ? { source_type: sourceType } : undefined
  });
  return response.data;
}

export async function getCourse(courseId: number) {
  const response = await apiClient.get<ApiEnvelope<ApiCourseSummary>>(COURSE_ENDPOINTS.detail(courseId));
  return response.data;
}

export async function getCourseOverview(courseId: number) {
  const response = await apiClient.get<ApiEnvelope<ApiCourseOverview>>(COURSE_ENDPOINTS.overview(courseId));
  return response.data;
}

export async function getKnowledgePoints(courseId: number) {
  const response = await apiClient.get<ApiEnvelope<ApiCourseKnowledgePoint[]>>(COURSE_ENDPOINTS.knowledgePoints(courseId));
  return response.data;
}

export async function getMasteryMap(courseId: number) {
  const response = await apiClient.get<ApiEnvelope<{ course_id: string; points: ApiCourseKnowledgePoint[] }>>(
    COURSE_ENDPOINTS.masteryMap(courseId)
  );
  return response.data;
}

export async function createCourseFromMaterials(payload: CreateCourseFromMaterialsRequest) {
  const response = await apiClient.post<ApiEnvelope<CreateCourseFromMaterialsResult>>(COURSE_ENDPOINTS.fromMaterials, payload);
  return response.data;
}

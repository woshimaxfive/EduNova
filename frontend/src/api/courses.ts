import { apiClient } from "./client";
import { type ApiEnvelope, type ApiListEnvelope, type CourseSummary } from "../types/api";

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

export async function listCourses(sourceType?: "builtin" | "uploaded") {
  const response = await apiClient.get<ApiListEnvelope<CourseSummary>>(COURSE_ENDPOINTS.list, {
    params: sourceType ? { source_type: sourceType } : undefined
  });
  return response.data;
}

export async function getCourse(courseId: number) {
  const response = await apiClient.get<ApiEnvelope<CourseSummary>>(COURSE_ENDPOINTS.detail(courseId));
  return response.data;
}

export async function getCourseOverview(courseId: number) {
  const response = await apiClient.get<ApiEnvelope<Record<string, unknown>>>(COURSE_ENDPOINTS.overview(courseId));
  return response.data;
}

export async function getKnowledgePoints(courseId: number) {
  const response = await apiClient.get<ApiEnvelope<Record<string, unknown>[]>>(
    COURSE_ENDPOINTS.knowledgePoints(courseId)
  );
  return response.data;
}

export async function getMasteryMap(courseId: number) {
  const response = await apiClient.get<ApiEnvelope<Record<string, unknown>>>(COURSE_ENDPOINTS.masteryMap(courseId));
  return response.data;
}

export async function createCourseFromMaterials(payload: CreateCourseFromMaterialsRequest) {
  const response = await apiClient.post<ApiEnvelope<Record<string, unknown>>>(COURSE_ENDPOINTS.fromMaterials, payload);
  return response.data;
}

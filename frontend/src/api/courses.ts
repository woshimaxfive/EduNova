import { apiClient } from "./client";
import { type ApiEnvelope, type ApiListEnvelope } from "../types/api";

export const COURSE_ENDPOINTS = {
  list: "/courses",
  detail: (courseId: number) => `/courses/${courseId}`,
  overview: (courseId: number) => `/courses/${courseId}/overview`,
  knowledgePoints: (courseId: number) => `/courses/${courseId}/knowledge-points`,
  knowledgePointContent: (courseId: number, knowledgePointId: number) =>
    `/courses/${courseId}/knowledge-points/${knowledgePointId}/content`,
  masteryMap: (courseId: number) => `/courses/${courseId}/mastery-map`,
  learningState: (courseId: number) => `/courses/${courseId}/learning-state`,
  activate: (courseId: number) => `/courses/${courseId}/activate`,
  complete: (courseId: number) => `/courses/${courseId}/complete`,
  resume: (courseId: number) => `/courses/${courseId}/resume`,
  learnerProfile: (courseId: number) => `/courses/${courseId}/learner-profile`,
  weaknessReviewAction: (courseId: number, itemId: string, action: CourseWeaknessReviewAction) =>
    `/courses/${courseId}/weakness-review-items/${itemId}/${action}`,
  fromMaterials: "/courses/from-materials",
  fromMaterialsJobs: "/courses/from-materials/jobs"
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
  agent_trace_id?: string | null;
  progress_percent: number;
  practiced_knowledge_point_count?: number;
  material_count: number;
  knowledge_point_count: number;
  chunk_count: number;
  learning_status?: "active" | "archived";
  last_accessed_at?: string | null;
  completed_at?: string | null;
  is_current?: boolean;
  profile_ready?: boolean;
};

export type CourseProfileReadiness = {
  ready: boolean;
  goal_ready: boolean;
  foundation_ready: boolean;
  global_preference_ready: boolean;
  missing_fields: string[];
};

export type CourseLearnerProfile = {
  course_id: string;
  learning_goal: string;
  knowledge_foundation: string;
  weak_points: string[];
  dimension_confidence: Record<string, number>;
  readiness: CourseProfileReadiness;
  legacy_suggestions: Record<string, unknown>;
};

export type CourseStageCompletion = {
  eligible: boolean;
  path_completed: boolean;
  assessed_point_count: number;
  required_point_count: number;
  below_threshold_count: number;
  active_weakness_count: number;
  due_review_count: number;
  report_fresh: boolean;
  blocking_reasons: string[];
};

export type ApiCourseKnowledgePoint = {
  id: string;
  title: string;
  summary: string | null;
  chapter: string | null;
  order_index: number;
  difficulty: string | null;
  prerequisite_ids: string[];
};

export type CourseKnowledgeSection = {
  chunk_id: string;
  title: string;
  content: string;
  source_title: string;
  page_number: number | null;
};

export type CourseKnowledgePointContent = {
  knowledge_point: ApiCourseKnowledgePoint;
  sections: CourseKnowledgeSection[];
  related_resources: CourseResourceBrief[];
  previous_knowledge_point_id: string | null;
  next_knowledge_point_id: string | null;
};

export type ApiCourseStructure = {
  schema_version: number;
  learning_objectives: string[];
  chapters: Array<{
    title: string;
    knowledge_point_ids: string[];
  }>;
  supplemental_refs: Array<Record<string, unknown>>;
  generation_mode: string;
  review_result: Record<string, unknown>;
};

export type ApiCourseOverview = {
  course: ApiCourseSummary;
  materials: string[];
  knowledge_points: ApiCourseKnowledgePoint[];
  chunk_count: number;
  structure?: ApiCourseStructure | null;
};

export type CreateCourseFromMaterialsResult = {
  course: ApiCourseSummary;
  knowledge_points: ApiCourseKnowledgePoint[];
};

export type CourseProfileOverlay = {
  learning_goal: string;
  knowledge_foundation: string;
  weak_points: string[];
};

export type CourseWeaknessSummary = {
  candidate_event_count: number;
  pending_count: number;
  confirmed_count: number;
  reviewing_count: number;
  completed_count: number;
  dismissed_count: number;
  latest_evidence_at: string | null;
};

export type CourseWeaknessReviewAction = "confirm" | "start" | "complete" | "dismiss";

export type CourseWeaknessReviewStatus = "pending" | "confirmed" | "reviewing" | "completed" | "dismissed";

export type CourseResourceBrief = {
  id: string;
  title: string;
  resource_type: string;
};

export type CourseWeaknessReviewItem = {
  id: string;
  title: string;
  status: CourseWeaknessReviewStatus;
  source_type: string;
  course_id: string;
  knowledge_point_id: string | null;
  recommended_resource_ids: string[];
  recommended_resources: CourseResourceBrief[];
  diagnosis?: {
    misconception: string;
    missing_concepts: string[];
    recommended_action: string;
    confidence: number;
    evidence_count: number;
    baseline_score: number | null;
    latest_score: number | null;
    improvement: number | null;
    attempt_count: number;
    last_practice_session_id: string | null;
  };
  next_review_at: string | null;
  created_at: string;
  updated_at: string;
};

export type CoursePathSummary = {
  status: string;
  message: string;
  path_id: string | null;
  current_task_title: string | null;
  task_count: number;
  completed_task_count: number;
};

export type CourseMasterySummary = {
  total_count: number;
  weak_count: number;
  learning_count: number;
  mastered_count: number;
  recommended_review_count: number;
  not_started_count: number;
  assessed_count?: number;
  unassessed_count?: number;
  average_score?: number | null;
};

export type CourseMasteryStatus = "not_started" | "learning" | "mastered" | "weak" | "recommended_review";

export type CourseMasteryPoint = {
  id: string;
  title: string;
  chapter: string | null;
  order_index: number;
  status: CourseMasteryStatus;
  score: number | null;
  evidence_count?: number;
  confidence?: number | null;
  last_assessed_at?: string | null;
  prerequisite_ids: string[];
  weakness_item_ids: string[];
  recommended_resource_ids: string[];
};

export type CourseMasteryMap = {
  course_id: string;
  summary: CourseMasterySummary;
  points: CourseMasteryPoint[];
};

export type CourseEvidenceSummary = {
  candidate_event_count: number;
  latest_trace_id: string | null;
  latest_source_title: string | null;
  latest_section_title: string | null;
};

export type CourseLearnerContext = {
  profile_applied_version: number;
  context_hash: string;
  completeness_score: number;
  evidence_confidence_score: number;
  trusted_dimensions: string[];
  advisory_dimensions: string[];
  course_goal: string;
  foundation_summary: string;
  active_weaknesses: string[];
  mastery_average: number | null;
  current_task_title: string | null;
  recent_practice_score: number | null;
  learning_preference: string;
  cognitive_style: string;
  learning_pace: string;
  motivation_interest: string;
};

export type CourseLearningState = {
  course_id: string;
  profile_overlay: CourseProfileOverlay;
  learner_context?: CourseLearnerContext;
  weakness_summary: CourseWeaknessSummary;
  weakness_review_queue: CourseWeaknessReviewItem[];
  path_summary: CoursePathSummary;
  mastery_summary: CourseMasterySummary;
  evidence_summary: CourseEvidenceSummary;
  course_profile_readiness?: CourseProfileReadiness;
  stage_completion?: CourseStageCompletion;
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

export async function getKnowledgePointContent(courseId: number, knowledgePointId: number) {
  const response = await apiClient.get<ApiEnvelope<CourseKnowledgePointContent>>(
    COURSE_ENDPOINTS.knowledgePointContent(courseId, knowledgePointId)
  );
  return response.data;
}

export async function getMasteryMap(courseId: number) {
  const response = await apiClient.get<ApiEnvelope<CourseMasteryMap>>(COURSE_ENDPOINTS.masteryMap(courseId));
  return response.data;
}

export async function getCourseLearningState(courseId: number) {
  const response = await apiClient.get<ApiEnvelope<CourseLearningState>>(COURSE_ENDPOINTS.learningState(courseId));
  return response.data;
}

export async function activateCourse(courseId: number) {
  const response = await apiClient.post<ApiEnvelope<ApiCourseSummary>>(COURSE_ENDPOINTS.activate(courseId));
  return response.data;
}

export async function completeCourse(courseId: number) {
  const response = await apiClient.post<ApiEnvelope<ApiCourseSummary>>(COURSE_ENDPOINTS.complete(courseId));
  return response.data;
}

export async function resumeCourse(courseId: number) {
  const response = await apiClient.post<ApiEnvelope<ApiCourseSummary>>(COURSE_ENDPOINTS.resume(courseId));
  return response.data;
}

export async function getCourseLearnerProfile(courseId: number) {
  const response = await apiClient.get<ApiEnvelope<CourseLearnerProfile>>(COURSE_ENDPOINTS.learnerProfile(courseId));
  return response.data;
}

export async function updateCourseLearnerProfile(courseId: number, payload: { learning_goal: string; knowledge_foundation: string; weak_points: string[] }) {
  const response = await apiClient.put<ApiEnvelope<CourseLearnerProfile>>(COURSE_ENDPOINTS.learnerProfile(courseId), payload);
  return response.data;
}

export async function updateCourseWeaknessReviewItem(
  courseId: number,
  itemId: string,
  action: CourseWeaknessReviewAction
) {
  const response = await apiClient.post<ApiEnvelope<CourseWeaknessReviewItem>>(
    COURSE_ENDPOINTS.weaknessReviewAction(courseId, itemId, action)
  );
  return response.data;
}

export async function createCourseFromMaterials(payload: CreateCourseFromMaterialsRequest) {
  const response = await apiClient.post<ApiEnvelope<CreateCourseFromMaterialsResult>>(COURSE_ENDPOINTS.fromMaterials, payload);
  return response.data;
}

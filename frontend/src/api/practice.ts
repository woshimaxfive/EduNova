import { apiClient, MODEL_OPERATION_TIMEOUT_MS } from "./client";
import { type ApiEnvelope } from "../types/api";

export const PRACTICE_ENDPOINTS = {
  sessions: "/practice/sessions",
  latest: "/practice/sessions/latest",
  recent: "/practice/sessions/recent",
  detail: (sessionId: number) => `/practice/sessions/${sessionId}`,
  draft: (sessionId: number) => `/practice/sessions/${sessionId}/draft`,
  answers: (sessionId: number) => `/practice/sessions/${sessionId}/answers`,
  regrade: (sessionId: number) => `/practice/sessions/${sessionId}/regrade`
} as const;

export type CreatePracticeSessionRequest = {
  course_id: number;
  knowledge_point_ids: number[];
  weakness_item_id?: number | null;
  question_count: number;
  difficulty: "adaptive" | "easy" | "medium" | "hard";
};

export type SubmitPracticeAnswersRequest = {
  answers: Array<{
    question_id: string;
    answer_text: string;
    answered?: boolean;
  }>;
};

export type PracticeQuestion = {
  id: string;
  question_type: "single_choice" | "multiple_choice" | "short_answer";
  knowledge_point_id: string | null;
  knowledge_point_title: string;
  prompt: string;
  options: string[];
  option_ids?: string[];
  correct_answer: string | string[] | null;
  keywords: string[];
  explanation: string;
  unanswered?: boolean;
  difficulty: string;
  citation_refs?: string[];
  generation_mode?: string;
  prompt_version?: string;
  quality?: Record<string, unknown>;
};

export type PracticeAnswerFeedback = {
  score: number | null;
  grading_status: "deterministic" | "model" | "ungraded";
  message: string;
  matched_concepts: string[];
  missing_concepts: string[];
  confidence: number | null;
  matched_keywords: string[];
  missing_keywords: string[];
  explanation: string;
  unanswered?: boolean;
  diagnosis?: {
    misconception: string;
    missing_concepts: string[];
    recommended_action: string;
    confidence: number;
    evidence_ref: {
      type: "practice_answer";
      id: string;
    };
  } | null;
};

export type PracticeAnswerResult = {
  question_id: string;
  answer_text: string | null;
  is_correct: boolean | null;
  feedback: PracticeAnswerFeedback;
};

export type PracticeSessionDetail = {
  id: string;
  course_id: string;
  title: string;
  status: "in_progress" | "completed" | string;
  agent_trace_id?: string | null;
  score: number | null;
  grading_status: "complete" | "partial" | "ungraded";
  requested_difficulty: "adaptive" | "easy" | "medium" | "hard";
  effective_difficulty: "easy" | "medium" | "hard";
  draft_saved_at?: string | null;
  draft_revision?: number;
  questions: PracticeQuestion[];
  answers: PracticeAnswerResult[];
  closure_update?: {
    weaknesses_added: number;
    weaknesses_updated: number;
    path_update_status: "not_started" | "replanned" | "unchanged" | "failed";
    path_agent_trace_id?: string | null;
    recommended_resource_ids: string[];
    targeted_weakness_id?: string | null;
    targeted_weakness_status?: "confirmed" | "reviewing" | "completed" | null;
    targeted_weakness_improvement?: number | null;
    targeted_weakness_passed?: boolean | null;
  } | null;
  targeted_weakness_id?: string | null;
  targeted_weakness_title?: string | null;
  created_at: string;
  updated_at: string;
};

export type PracticeSessionSummary = Pick<
  PracticeSessionDetail,
  "id" | "course_id" | "title" | "status" | "score" | "effective_difficulty" | "created_at" | "updated_at"
>;

export async function createPracticeSession(payload: CreatePracticeSessionRequest) {
  const response = await apiClient.post<ApiEnvelope<PracticeSessionDetail>>(PRACTICE_ENDPOINTS.sessions, payload, {
    timeout: MODEL_OPERATION_TIMEOUT_MS
  });
  return response.data;
}

export async function getPracticeSession(sessionId: number) {
  const response = await apiClient.get<ApiEnvelope<PracticeSessionDetail>>(PRACTICE_ENDPOINTS.detail(sessionId));
  return response.data;
}

export async function getLatestPracticeSession(courseId: number) {
  const response = await apiClient.get<ApiEnvelope<PracticeSessionDetail | null>>(PRACTICE_ENDPOINTS.latest, {
    params: { course_id: courseId }
  });
  return response.data;
}

export async function listRecentCompletedPracticeSessions(courseId: number, limit = 5) {
  const response = await apiClient.get<ApiEnvelope<PracticeSessionSummary[]>>(PRACTICE_ENDPOINTS.recent, {
    params: { course_id: courseId, limit }
  });
  return response.data;
}

export async function savePracticeDraft(
  sessionId: number,
  payload: SubmitPracticeAnswersRequest & { revision: number },
  options: { signal?: AbortSignal } = {}
) {
  const response = await apiClient.patch<ApiEnvelope<PracticeSessionDetail>>(PRACTICE_ENDPOINTS.draft(sessionId), payload, options);
  return response.data;
}

export async function submitPracticeAnswers(sessionId: number, payload: SubmitPracticeAnswersRequest) {
  const response = await apiClient.post<ApiEnvelope<PracticeSessionDetail>>(
    PRACTICE_ENDPOINTS.answers(sessionId),
    payload,
    { timeout: MODEL_OPERATION_TIMEOUT_MS }
  );
  return response.data;
}

export async function regradePracticeAnswers(sessionId: number) {
  const response = await apiClient.post<ApiEnvelope<PracticeSessionDetail>>(PRACTICE_ENDPOINTS.regrade(sessionId), undefined, {
    timeout: MODEL_OPERATION_TIMEOUT_MS
  });
  return response.data;
}

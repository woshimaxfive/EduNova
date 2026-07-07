import { apiClient } from "./client";
import { type ApiEnvelope } from "../types/api";

export const PRACTICE_ENDPOINTS = {
  sessions: "/practice/sessions",
  detail: (sessionId: number) => `/practice/sessions/${sessionId}`,
  answers: (sessionId: number) => `/practice/sessions/${sessionId}/answers`
} as const;

export type CreatePracticeSessionRequest = {
  course_id: number;
  knowledge_point_ids: number[];
  question_count: number;
  difficulty: "easy" | "medium" | "hard";
};

export type SubmitPracticeAnswersRequest = {
  answers: Array<{
    question_id: string;
    answer_text: string;
  }>;
};

export type PracticeQuestion = {
  id: string;
  question_type: "single_choice" | "multiple_choice" | "short_answer";
  knowledge_point_id: string | null;
  knowledge_point_title: string;
  prompt: string;
  options: string[];
  correct_answer: string | string[] | null;
  keywords: string[];
  explanation: string;
  difficulty: string;
};

export type PracticeAnswerFeedback = {
  score: number;
  message: string;
  matched_keywords: string[];
  missing_keywords: string[];
  explanation: string;
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
  questions: PracticeQuestion[];
  answers: PracticeAnswerResult[];
  created_at: string;
  updated_at: string;
};

export async function createPracticeSession(payload: CreatePracticeSessionRequest) {
  const response = await apiClient.post<ApiEnvelope<PracticeSessionDetail>>(PRACTICE_ENDPOINTS.sessions, payload);
  return response.data;
}

export async function getPracticeSession(sessionId: number) {
  const response = await apiClient.get<ApiEnvelope<PracticeSessionDetail>>(PRACTICE_ENDPOINTS.detail(sessionId));
  return response.data;
}

export async function submitPracticeAnswers(sessionId: number, payload: SubmitPracticeAnswersRequest) {
  const response = await apiClient.post<ApiEnvelope<PracticeSessionDetail>>(
    PRACTICE_ENDPOINTS.answers(sessionId),
    payload
  );
  return response.data;
}

import { apiClient } from "./client";
import { PATHS } from "../app/routePaths";
import { useAuthStore } from "../features/auth/authStore";
import { type ApiEnvelope } from "../types/api";
import { type RagSearchResultItem } from "./rag";

export const TUTOR_ENDPOINTS = {
  sessions: "/tutor/sessions",
  history: "/tutor/sessions/history",
  detail: (sessionId: number | string) => `/tutor/sessions/${sessionId}`,
  message: (sessionId: number | string) => `/tutor/sessions/${sessionId}/messages`,
  stream: (sessionId: number | string) => `/tutor/sessions/${sessionId}/messages/stream`
} as const;

export type TutorSessionScope = "home" | "course";
export type TutorSessionMode = "chat" | "socratic" | "direct";

export type CreateTutorSessionRequest = {
  scope: TutorSessionScope;
  course_id: number | null;
  mode: TutorSessionMode;
  title: string;
  selected_material_ids?: number[];
};

export type UpdateTutorSessionRequest = {
  title?: string;
  selected_material_ids?: number[];
};

export type DeleteTutorSessionResponse = {
  session_id: string;
  deleted: boolean;
};

export type SendTutorMessageRequest = {
  message: string;
  use_web_search?: boolean;
  deep_thinking?: boolean;
  selected_material_ids?: number[];
};

export type TutorSessionSummary = {
  id: string;
  scope: TutorSessionScope;
  course_id: string | null;
  title: string;
  mode: TutorSessionMode;
  archived_from_home: boolean;
  selected_material_ids: number[];
  created_at: string;
  updated_at: string;
};

export type TutorSessionHistoryItem = TutorSessionSummary & {
  match_snippet?: string | null;
};

export type TutorSessionHistoryPage = {
  items: TutorSessionHistoryItem[];
  page: number;
  page_size: number;
  total: number;
  has_more: boolean;
};

export type TutorCitation = Partial<RagSearchResultItem> & {
  source_type?: "course" | "material" | "web" | string;
  title?: string;
  url?: string;
  snippet?: string;
  material_id?: string | number;
  section_title?: string | null;
  page_number?: number | null;
  score?: number;
  retrieval_source?: "keyword" | "vector" | "hybrid" | string | null;
  embedding_status?: string | null;
  warning?: string;
};

export type TutorMessage = {
  id: string;
  session_id: string;
  role: "user" | "assistant";
  content: string;
  citation_json: TutorCitation[];
  trace_id: string | null;
  created_at: string;
};

export type TutorSessionDetail = {
  session: TutorSessionSummary;
  messages: TutorMessage[];
};

export type TutorStreamMetadata = {
  session_id: string;
  trace_id: string | null;
  citation_count: number;
  used_model: boolean;
  workflow?: string;
  artifact_type?: string;
  steps?: string[];
  context_message_count?: number;
  context_summary_used?: boolean;
  retrieval_query_mode?: string;
};

export type TutorStreamStatus = {
  stage: string;
  label: string;
};

export type TutorStreamSources = {
  citations: TutorCitation[];
  warnings: string[];
};

export type TutorStreamReplace = {
  content: string;
  reason: "review_repair";
};

export type TutorStreamError = {
  code: string;
  message: string;
  retryable?: boolean;
  retry_after_seconds?: number;
};

export class TutorStreamRequestError extends Error {
  code: string;
  retryable: boolean;
  retryAfterSeconds?: number;

  constructor(error: TutorStreamError) {
    super(error.message || "模型暂不可用，请检查设置或稍后重试。");
    this.name = "TutorStreamRequestError";
    this.code = error.code;
    this.retryable = error.retryable ?? true;
    this.retryAfterSeconds = error.retry_after_seconds;
  }
}

export type StreamTutorMessageHandlers = {
  onMetadata?: (metadata: TutorStreamMetadata) => void;
  onStatus?: (status: TutorStreamStatus) => void;
  onSources?: (sources: TutorStreamSources) => void;
  onToken?: (content: string) => void;
  onReplace?: (replacement: TutorStreamReplace) => void;
  onDone?: (detail: TutorSessionDetail) => void;
  onError?: (error: TutorStreamError) => void;
};

export async function createTutorSession(payload: CreateTutorSessionRequest) {
  const response = await apiClient.post<ApiEnvelope<TutorSessionSummary>>(TUTOR_ENDPOINTS.sessions, payload);
  return response.data;
}

export async function listTutorSessions(scope: TutorSessionScope = "home", courseId?: number | null) {
  const params = courseId === undefined || courseId === null ? { scope } : { scope, course_id: courseId };

  const response = await apiClient.get<ApiEnvelope<TutorSessionSummary[]>>(TUTOR_ENDPOINTS.sessions, {
    params
  });
  return response.data;
}

export async function listHomeTutorHistory(params: { page?: number; pageSize?: number; query?: string } = {}) {
  const response = await apiClient.get<ApiEnvelope<TutorSessionHistoryPage>>(TUTOR_ENDPOINTS.history, {
    params: {
      page: params.page ?? 1,
      page_size: params.pageSize ?? 30,
      ...(params.query?.trim() ? { q: params.query.trim() } : {})
    }
  });
  return response.data;
}

export async function getTutorSession(sessionId: number | string) {
  const response = await apiClient.get<ApiEnvelope<TutorSessionDetail>>(TUTOR_ENDPOINTS.detail(sessionId));
  return response.data;
}

export async function renameTutorSession(sessionId: number | string, payload: UpdateTutorSessionRequest) {
  const response = await apiClient.patch<ApiEnvelope<TutorSessionSummary>>(TUTOR_ENDPOINTS.detail(sessionId), payload);
  return response.data;
}

export async function deleteTutorSession(sessionId: number | string) {
  const response = await apiClient.delete<ApiEnvelope<DeleteTutorSessionResponse>>(TUTOR_ENDPOINTS.detail(sessionId));
  return response.data;
}

export async function sendTutorMessage(sessionId: number | string, payload: SendTutorMessageRequest) {
  const response = await apiClient.post<ApiEnvelope<TutorSessionDetail>>(TUTOR_ENDPOINTS.message(sessionId), payload);
  return response.data;
}

export async function streamTutorMessage(
  sessionId: number | string,
  payload: SendTutorMessageRequest,
  handlers: StreamTutorMessageHandlers = {}
): Promise<TutorSessionDetail> {
  const token = useAuthStore.getState().token;
  const baseURL = String(apiClient.defaults.baseURL ?? "/api/v1").replace(/\/$/, "");
  const response = await fetch(`${baseURL}${TUTOR_ENDPOINTS.stream(sessionId)}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {})
    },
    body: JSON.stringify(payload)
  });

  if (response.status === 401) {
    useAuthStore.getState().clearSession();
    if (typeof window !== "undefined" && window.location.pathname.startsWith(PATHS.app)) {
      window.location.assign(PATHS.login);
    }
  }
  if (!response.ok) {
    throw new Error("模型暂不可用，请检查设置或稍后重试。");
  }
  if (!response.body) {
    throw new Error("当前浏览器不支持流式回答。");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";
  const streamState: {
    finalDetail: TutorSessionDetail | null;
    terminalEvent: "done" | "error" | null;
  } = { finalDetail: null, terminalEvent: null };

  const dispatchEvent = (event: { event: string; data: unknown } | null) => {
    if (event === null || streamState.terminalEvent !== null) {
      return;
    }
    if (event.event === "metadata") {
      handlers.onMetadata?.(event.data as TutorStreamMetadata);
    } else if (event.event === "status") {
      handlers.onStatus?.(event.data as TutorStreamStatus);
    } else if (event.event === "sources") {
      handlers.onSources?.(event.data as TutorStreamSources);
    } else if (event.event === "token") {
      const tokenData = event.data as { content?: unknown };
      handlers.onToken?.(typeof tokenData.content === "string" ? tokenData.content : "");
    } else if (event.event === "replace") {
      handlers.onReplace?.(event.data as TutorStreamReplace);
    } else if (event.event === "done") {
      streamState.finalDetail = event.data as TutorSessionDetail;
      streamState.terminalEvent = "done";
      handlers.onDone?.(streamState.finalDetail);
    } else if (event.event === "error") {
      const error = event.data as TutorStreamError;
      streamState.terminalEvent = "error";
      handlers.onError?.(error);
      throw new TutorStreamRequestError(error);
    }
  };

  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split(/\r?\n\r?\n/);
    buffer = parts.pop() ?? "";
    for (const part of parts) {
      dispatchEvent(parseSseEvent(part));
    }
  }

  buffer += decoder.decode();
  if (buffer.trim()) {
    dispatchEvent(parseSseEvent(buffer));
  }

  if (streamState.finalDetail === null) {
    throw new Error("模型暂不可用，请检查设置或稍后重试。");
  }
  return streamState.finalDetail;
}

function parseSseEvent(raw: string): { event: string; data: unknown } | null {
  const lines = raw.split(/\r?\n/);
  const eventLine = lines.find((line) => line.startsWith("event:"));
  const dataLines = lines.filter((line) => line.startsWith("data:"));
  if (dataLines.length === 0) {
    return null;
  }

  const event = eventLine?.replace("event:", "").trim() || "message";
  const rawData = dataLines.map((line) => line.replace("data:", "").trimStart()).join("\n");
  try {
    return { event, data: JSON.parse(rawData) };
  } catch {
    return null;
  }
}

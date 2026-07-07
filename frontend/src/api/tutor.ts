import { apiClient } from "./client";
import { PATHS } from "../app/routePaths";
import { useAuthStore } from "../features/auth/authStore";
import { type ApiEnvelope } from "../types/api";
import { type RagSearchResultItem } from "./rag";

export const TUTOR_ENDPOINTS = {
  sessions: "/tutor/sessions",
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
};

export type UpdateTutorSessionRequest = {
  title: string;
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
  created_at: string;
  updated_at: string;
};

export type TutorCitation = Partial<RagSearchResultItem> & {
  source_type?: "course" | "material" | "web" | string;
  title?: string;
  url?: string;
  snippet?: string;
  material_id?: string | number;
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
};

export type TutorStreamError = {
  code: string;
  message: string;
};

export type StreamTutorMessageHandlers = {
  onMetadata?: (metadata: TutorStreamMetadata) => void;
  onToken?: (content: string) => void;
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
) {
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
  let finalDetail: TutorSessionDetail | null = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split(/\n\n/);
    buffer = parts.pop() ?? "";
    for (const part of parts) {
      const event = parseSseEvent(part);
      if (event === null) {
        continue;
      }
      if (event.event === "metadata") {
        handlers.onMetadata?.(event.data as TutorStreamMetadata);
      } else if (event.event === "token") {
        const tokenData = event.data as { content?: unknown };
        handlers.onToken?.(typeof tokenData.content === "string" ? tokenData.content : "");
      } else if (event.event === "done") {
        finalDetail = event.data as TutorSessionDetail;
        handlers.onDone?.(finalDetail);
      } else if (event.event === "error") {
        const error = event.data as TutorStreamError;
        handlers.onError?.(error);
        throw new Error(error.message || "模型暂不可用，请检查设置或稍后重试。");
      }
    }
  }

  buffer += decoder.decode();
  if (buffer.trim()) {
    const event = parseSseEvent(buffer);
    if (event?.event === "done") {
      finalDetail = event.data as TutorSessionDetail;
      handlers.onDone?.(finalDetail);
    }
  }

  if (finalDetail === null) {
    throw new Error("模型暂不可用，请检查设置或稍后重试。");
  }
  return finalDetail;
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

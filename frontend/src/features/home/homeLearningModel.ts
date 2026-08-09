import type { TutorCitation, TutorImageAttachment, TutorMessage } from "../../api/tutor";
import type { getDashboardSummary } from "../../api/dashboard";
export type LibraryMaterial = {
  id: string;
  title: string;
  type: string;
  detail: string;
  modified: string;
  size: string;
  ingestion_status?: "legacy" | "stored" | "pending" | "queued" | "running" | "awaiting_confirmation" | "confirmed" | "failed";
  category?: "document" | "image";
};

export type HomeMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  citation_json: TutorCitation[];
  trace_id: string | null;
  attachments: TutorImageAttachment[];
  resource_jobs?: TutorMessage["resource_jobs"];
  resource_proposal?: TutorMessage["resource_proposal"];
  streaming?: boolean;
};

export type LearningSpaceNavigationState = {
  selectedHomeThreadId?: string;
  selectedMaterialIds?: string[];
};

export type PendingHomeResourceGeneration = { sessionId: string; messageId: string };

export type DashboardSummaryResponse = Awaited<ReturnType<typeof getDashboardSummary>>;

export type DashboardSummaryThread = {
  id: string;
  title: string;
  meta: string;
};

export type HomeAnswerPanel = "sources" | "why" | "trace";

export const HOME_COMPOSER_MAX_HEIGHT = 154;

export function mapTutorMessages(apiMessages: TutorMessage[]) {
  return apiMessages.map((message) => ({
    id: message.id,
    role: message.role,
    content: message.role === "assistant" ? sanitizeHomeAnswerContent(message.content) : message.content,
    citation_json: message.citation_json ?? [],
    trace_id: message.trace_id ?? null,
    attachments: message.attachments ?? []
    ,resource_jobs: message.resource_jobs ?? [],
    resource_proposal: message.resource_proposal ?? null
  }));
}

export function sanitizeHomeAnswerContent(content: string) {
  const normalized = content.trim();
  const internalMarkers = ["学生问题：", "工具状态：", "可用来源摘要：", "工具提示："];
  if (!internalMarkers.some((marker) => normalized.includes(marker))) {
    return normalized;
  }

  const finalBoundary = normalized.match(/(?:最终回答|给学生的回答|以下是针对学生[^：:]*的[^：:]*回答)[：:]\s*([\s\S]+)/);
  if (finalBoundary?.[1]?.trim()) {
    return finalBoundary[1].trim();
  }

  return "这条历史回答包含旧版内部处理信息，已停止展示。请重新提问以获得正常回答。";
}

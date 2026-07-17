import { useQueries } from "@tanstack/react-query";

import { getAgentTrace, type AgentTrace } from "../../api/agents";
import { type TutorResponseProgressState } from "./tutorResponseProgress";

export type TutorCompletedResponseProgress = TutorResponseProgressState & {
  durationMs: number;
};

type TutorAnswerTrace = {
  messageId: string;
  traceId: string | null | undefined;
};

export function toCompletedTutorResponseProgress(trace: AgentTrace): TutorCompletedResponseProgress | null {
  const steps = Array.isArray(trace.steps) ? trace.steps : [];
  const stages = steps
    .map((step) => (step.input_summary || step.output_summary || "").trim())
    .filter(Boolean);
  if (stages.length === 0) return null;

  const startedAt = Date.parse(steps[0]?.created_at ?? "") || 0;
  const stepDurationMs = steps.reduce((total, step) => total + Math.max(0, step.duration_ms ?? 0), 0);
  const durationMs = Math.max(1_000, trace.summary?.duration_ms ?? stepDurationMs);

  return { startedAt, stages, durationMs };
}

export function useTutorPersistedResponseProgress(answerTraces: TutorAnswerTrace[]) {
  const queries = useQueries({
    queries: answerTraces.map(({ traceId }) => ({
      queryKey: ["agents", "trace", traceId],
      queryFn: () => getAgentTrace(traceId ?? ""),
      enabled: Boolean(traceId),
      staleTime: 5 * 60_000,
      retry: false
    }))
  });

  return answerTraces.reduce<Record<string, TutorCompletedResponseProgress>>((progressByMessageId, answerTrace, index) => {
    const trace = queries[index]?.data?.data;
    const progress = trace ? toCompletedTutorResponseProgress(trace) : null;
    if (progress) progressByMessageId[answerTrace.messageId] = progress;
    return progressByMessageId;
  }, {});
}

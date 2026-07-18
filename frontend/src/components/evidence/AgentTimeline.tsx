import type { AgentTrace } from "../../api/agents";
import { type AgentTraceEvent } from "../../types/api";
import { AiCollaborationPanel } from "./AiCollaborationPanel";

type AgentTimelineProps = {
  events: AgentTraceEvent[];
  staggered?: boolean;
  summary?: AgentTrace["summary"];
};

export function AgentTimeline({ events, summary }: AgentTimelineProps) {
  return (
    <AiCollaborationPanel
      completed
      events={events}
      defaultExpanded
      summary={summary ? {
        durationMs: summary.duration_ms,
        courseSourceCount: summary.course_source_count,
        webSourceCount: summary.web_source_count,
        historySourceCount: summary.history_source_count,
        personalizationFactorCount: summary.personalization_factors?.length,
        reviewStatus: summary.review_status,
        safetySummary: summary.safety_summary
      } : undefined}
      storageKey={undefined}
    />
  );
}

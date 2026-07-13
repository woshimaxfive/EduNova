import { CheckCircle, Robot, WarningCircle } from "@phosphor-icons/react";
import type { CSSProperties } from "react";

import { type AgentTraceEvent } from "../../types/api";

type AgentTimelineProps = {
  events: AgentTraceEvent[];
  staggered?: boolean;
};

export function AgentTimeline({ events, staggered = false }: AgentTimelineProps) {
  return (
    <ol className={staggered ? "agent-timeline agent-timeline-staggered" : "agent-timeline"} aria-label="Agent 执行轨迹">
      {events.map((event, index) => (
        <li key={event.id} className={event.status} style={staggered ? { "--trace-step-index": index } as CSSProperties : undefined}>
          <span className="timeline-icon" aria-hidden="true">
            {event.status === "warning" ? (
              <WarningCircle size={18} weight="duotone" />
            ) : event.status === "completed" ? (
              <CheckCircle size={18} weight="duotone" />
            ) : (
              <Robot size={18} weight="duotone" />
            )}
          </span>
          <span>
            <strong>{event.agentName}</strong>
            <small>{event.summary}</small>
            {event.contextMessageCount ? (
              <small className="timeline-context">
                {`已参考最近 ${event.contextMessageCount} 条会话${event.contextSummaryUsed ? "，并使用历史摘要" : ""}`}
              </small>
            ) : null}
            {event.modelCallCount ? (
              <small className="timeline-context">
                {`模型调用 ${event.modelCallCount} 次${event.modelRetryCount ? `，重试 ${event.modelRetryCount} 次` : ""}${event.modelOutcome === "degraded" ? "，已安全降级" : ""}`}
              </small>
            ) : null}
          </span>
          {event.modelLatencyMs ? <em>{event.modelLatencyMs} ms</em> : event.durationMs ? <em>{event.durationMs} ms</em> : null}
        </li>
      ))}
    </ol>
  );
}

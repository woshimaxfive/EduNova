import { CheckCircle, Robot, WarningCircle } from "@phosphor-icons/react";

import { type AgentTraceEvent } from "../../types/api";

type AgentTimelineProps = {
  events: AgentTraceEvent[];
};

export function AgentTimeline({ events }: AgentTimelineProps) {
  return (
    <ol className="agent-timeline" aria-label="Agent 执行轨迹">
      {events.map((event) => (
        <li key={event.id} className={event.status}>
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
          </span>
          {event.durationMs ? <em>{event.durationMs} ms</em> : null}
        </li>
      ))}
    </ol>
  );
}

import { CaretDown, CaretUp, CirclesThreePlus } from "@phosphor-icons/react";
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import { getAgentTrace, mapAgentTraceStepToEvent } from "../../api/agents";
import { AgentTimeline } from "./AgentTimeline";

type AgentTraceDisclosureProps = {
  traceId: string | null | undefined;
  label: string;
  staggered?: boolean;
};

export function AgentTraceDisclosure({ traceId, label, staggered = false }: AgentTraceDisclosureProps) {
  const [open, setOpen] = useState(false);
  const traceQuery = useQuery({
    queryKey: ["agents", "trace", traceId],
    queryFn: () => getAgentTrace(traceId ?? ""),
    enabled: open && Boolean(traceId),
    staleTime: 30_000
  });
  const events = useMemo(
    () => traceQuery.data?.data.steps.map(mapAgentTraceStepToEvent) ?? [],
    [traceQuery.data?.data.steps]
  );

  if (!traceId) {
    return null;
  }

  return (
    <div className="agent-trace-disclosure">
      <button
        className="agent-trace-disclosure-trigger"
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((current) => !current)}
      >
        <CirclesThreePlus size={17} weight="duotone" aria-hidden="true" />
        <span>{label}</span>
        {open ? <CaretUp size={15} aria-hidden="true" /> : <CaretDown size={15} aria-hidden="true" />}
      </button>
      {open ? (
        <div className="agent-trace-disclosure-content" role="region" aria-label={`${label}执行轨迹`}>
          {traceQuery.isPending ? <p className="empty-inline-note">正在读取协作轨迹。</p> : null}
          {traceQuery.isError ? <p className="form-error">协作轨迹读取失败，请稍后重试。</p> : null}
          {events.length > 0 ? <AgentTimeline events={events} staggered={staggered} /> : null}
        </div>
      ) : null}
    </div>
  );
}

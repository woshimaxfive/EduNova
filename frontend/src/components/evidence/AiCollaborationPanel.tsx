import { CaretDown, CaretUp, CheckCircle, CircleNotch, WarningCircle } from "@phosphor-icons/react";
import { useEffect, useMemo, useState } from "react";

import type { AgentTraceEvent } from "../../types/api";

export type CollaborationSummary = {
  durationMs?: number;
  courseSourceCount?: number;
  webSourceCount?: number;
  historySourceCount?: number;
  personalizationFactorCount?: number;
  reviewStatus?: string | null;
  safetySummary?: string | null;
};

type Props = {
  running?: boolean;
  completed?: boolean;
  stages?: string[];
  events?: AgentTraceEvent[];
  startedAt?: number;
  durationMs?: number;
  summary?: CollaborationSummary;
  storageKey?: string;
  defaultExpanded?: boolean;
};

export function AiCollaborationPanel({ running = false, completed = false, stages = [], events = [], startedAt, durationMs, summary, storageKey, defaultExpanded = false }: Props) {
  const [now, setNow] = useState(() => Date.now());
  const [open, setOpen] = useState(() => readExpanded(storageKey, defaultExpanded));
  const normalizedStages = useMemo(() => stages.filter((stage, index, all) => all.indexOf(stage) === index), [stages]);
  const elapsed = durationMs ?? summary?.durationMs ?? (startedAt ? now - startedAt : 0);
  const currentStage = normalizedStages.at(-1) ?? events.find((event) => event.status === "running")?.summary ?? "正在组织学习协作";
  const hasWarning = events.some((event) => event.status === "warning");

  useEffect(() => {
    if (!running || !startedAt) return undefined;
    const interval = window.setInterval(() => setNow(Date.now()), 500);
    return () => window.clearInterval(interval);
  }, [running, startedAt]);

  function toggle() {
    const next = !open;
    setOpen(next);
    if (!storageKey) return;
    try { sessionStorage.setItem(`edunova.collaboration.v1:${storageKey}`, next ? "open" : "closed"); } catch { /* no-op */ }
  }

  if (running) {
    return (
      <section className="ai-collaboration-panel is-running" role="status" aria-live="polite" aria-label="AI 正在完成这一步">
        <header><CircleNotch className="tutor-response-progress-spinner" size={17} weight="bold" aria-hidden="true" /><div><strong>AI 正在完成这一步</strong><span>{formatDuration(elapsed)}</span></div></header>
        <p>{currentStage}</p>
        {normalizedStages.length > 1 ? <CollaborationSteps stages={normalizedStages} events={[]} /> : null}
      </section>
    );
  }

  const sourceCount = (summary?.courseSourceCount ?? 0) + (summary?.webSourceCount ?? 0) + (summary?.historySourceCount ?? 0);
  return (
    <section className="ai-collaboration-panel is-completed" aria-label="AI 如何完成这一步">
      <button type="button" className="ai-collaboration-summary" aria-expanded={open} onClick={toggle}>
        {hasWarning ? <WarningCircle size={17} weight="fill" /> : <CheckCircle size={17} weight="fill" />}
        <span>{completed ? "协作完成" : "协作过程"}</span>
        {elapsed > 0 ? <small>{formatDuration(elapsed)}</small> : null}
        {sourceCount > 0 ? <small>{sourceCount} 个来源</small> : null}
        {(summary?.personalizationFactorCount ?? 0) > 0 ? <small>{summary?.personalizationFactorCount} 个个性化因素</small> : null}
        {open ? <CaretUp size={15} weight="bold" /> : <CaretDown size={15} weight="bold" />}
      </button>
      {open ? <div className="ai-collaboration-detail"><CollaborationSteps stages={normalizedStages} events={events} />{summary?.safetySummary ? <p className="ai-collaboration-safety">安全审核：{summary.safetySummary}</p> : null}{summary?.reviewStatus ? <small>审核状态：{summary.reviewStatus}</small> : null}</div> : null}
    </section>
  );
}

function CollaborationSteps({ stages, events }: { stages: string[]; events: AgentTraceEvent[] }) {
  const steps = events.length > 0
    ? events.map((event) => ({ id: event.id, label: event.agentName, detail: event.summary, status: event.status, durationMs: event.modelLatencyMs ?? event.durationMs }))
    : stages.map((stage, index) => ({ id: `${stage}-${index}`, label: safeStageLabel(stage), detail: stage, status: "completed" as const, durationMs: undefined }));
  return <ol className="ai-collaboration-steps">{steps.map((step) => <li key={step.id} data-status={step.status}><span aria-hidden="true" /><div><strong>{step.label}</strong>{step.detail !== step.label ? <small>{step.detail}</small> : null}</div>{step.durationMs ? <em>{step.durationMs} ms</em> : null}</li>)}</ol>;
}

function safeStageLabel(stage: string) {
  if (/检索|课程/.test(stage)) return "检索课程依据";
  if (/联网|搜索/.test(stage)) return "联网核实";
  if (/画像|个性/.test(stage)) return "个性化组织";
  if (/审核|安全|质量/.test(stage)) return "质量与安全审核";
  if (/历史|会话|上下文/.test(stage)) return "参考会话上下文";
  if (/回答|生成|组织/.test(stage)) return "形成学习回应";
  return "理解学习问题";
}

function formatDuration(durationMs: number) {
  return durationMs < 1000 ? `${Math.max(0, Math.round(durationMs))} ms` : `${Math.max(1, Math.round(durationMs / 1000))} 秒`;
}

function readExpanded(key: string | undefined, fallback: boolean) {
  if (!key) return fallback;
  try {
    const stored = sessionStorage.getItem(`edunova.collaboration.v1:${key}`);
    return stored ? stored === "open" : fallback;
  } catch { return fallback; }
}

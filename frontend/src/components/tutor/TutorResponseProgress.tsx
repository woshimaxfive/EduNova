import { CaretDown, CaretUp, CheckCircle, CircleNotch } from "@phosphor-icons/react";
import { useEffect, useMemo, useState } from "react";

import { type TutorResponseProgressState } from "../../features/tutor/tutorResponseProgress";

type TutorResponseProgressProps = {
  state: TutorResponseProgressState;
  completed?: boolean;
  durationMs?: number;
};

function formatDuration(durationMs: number) {
  const seconds = Math.max(1, Math.round(durationMs / 1000));
  return `${seconds} 秒`;
}

export function TutorResponseProgress({ state, completed = false, durationMs }: TutorResponseProgressProps) {
  const [now, setNow] = useState<number | null>(null);
  const [open, setOpen] = useState(false);
  const stages = useMemo(() => state.stages.filter((stage, index, all) => all.indexOf(stage) === index), [state.stages]);
  const elapsed = durationMs ?? (now ?? state.startedAt) - state.startedAt;
  const currentStage = stages.at(-1) ?? "正在组织回答";

  useEffect(() => {
    if (completed) return undefined;
    const interval = window.setInterval(() => setNow(Date.now()), 500);
    return () => window.clearInterval(interval);
  }, [completed]);

  if (!completed) {
    return (
      <section className="tutor-response-progress is-running" role="status" aria-live="polite" aria-label="正在协作回答">
        <div className="tutor-response-progress-summary">
          <CircleNotch className="tutor-response-progress-spinner" size={17} weight="bold" aria-hidden="true" />
          <strong>{`正在协作回答 · ${formatDuration(elapsed)}`}</strong>
        </div>
        <p>{currentStage}</p>
        {stages.length > 1 ? (
          <ol className="tutor-response-progress-stages" aria-label="当前协作步骤">
            {stages.map((stage, index) => <li key={`${stage}-${index}`}>{stage}</li>)}
          </ol>
        ) : null}
      </section>
    );
  }

  return (
    <section className="tutor-response-progress is-completed" aria-label="协作过程">
      <button type="button" aria-expanded={open} onClick={() => setOpen((current) => !current)}>
        <CheckCircle size={17} weight="fill" aria-hidden="true" />
        <span>{`协作完成 · 用时 ${formatDuration(elapsed)}`}</span>
        {open ? <CaretUp size={15} weight="bold" aria-hidden="true" /> : <CaretDown size={15} weight="bold" aria-hidden="true" />}
      </button>
      {open ? (
        <ol className="tutor-response-progress-stages" aria-label="本次协作步骤">
          {stages.map((stage, index) => <li key={`${stage}-${index}`}>{stage}</li>)}
        </ol>
      ) : null}
    </section>
  );
}

import { ArrowClockwise, CircleNotch, Stop } from "@phosphor-icons/react";
import { Link } from "react-router-dom";

import { type AiJob } from "../../api/aiJobs";
import { PATHS } from "../../app/routePaths";

type Props = {
  job: AiJob;
  compact?: boolean;
  onCancel?: () => void;
  onRetry?: () => void;
};

const workflowLabels = { course_builder: "智能建课", resource_generation: "资源生成" } as const;

export function AiJobProgress({ job, compact = false, onCancel, onRetry }: Props) {
  return (
    <section className={`ai-job-progress${compact ? " ai-job-progress--compact" : ""}`} aria-live="polite">
      <div className="ai-job-progress__heading">
        <div>
          <strong>{workflowLabels[job.workflow]}</strong>
          <span>{job.label}</span>
        </div>
        <b>{job.progress_percent}%</b>
      </div>
      <div className="ai-job-progress__bar" aria-label={`任务进度 ${job.progress_percent}%`}>
        <span style={{ width: `${job.progress_percent}%` }} />
      </div>
      {!compact && job.steps.length > 0 ? (
        <div className="ai-job-progress__steps">
          {job.steps.slice(-6).map((step) => (
            <span key={`${step.name}-${step.resource_type ?? "common"}`} data-status={step.status}>{step.label}</span>
          ))}
        </div>
      ) : null}
      {job.error_message ? <p className="ai-job-progress__error">{job.error_message}</p> : null}
      <div className="ai-job-progress__actions">
        {job.error_code === "authentication_failed" || job.error_code === "not_configured" ? (
          <Link className="icon-text-button" to={PATHS.settings}>检查模型设置</Link>
        ) : null}
        {job.can_cancel && onCancel ? (
          <button type="button" className="icon-text-button" onClick={onCancel}>
            {job.status === "cancelling" ? <CircleNotch className="spin" size={15} /> : <Stop size={14} />}
            <span>{job.status === "cancelling" ? "停止中" : "取消"}</span>
          </button>
        ) : null}
        {job.can_retry && onRetry ? (
          <button type="button" className="icon-text-button" onClick={onRetry}>
            <ArrowClockwise size={15} />
            <span>重试</span>
          </button>
        ) : null}
      </div>
    </section>
  );
}

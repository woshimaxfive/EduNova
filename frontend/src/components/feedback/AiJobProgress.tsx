import { ArrowClockwise, CircleNotch, Stop, X } from "@phosphor-icons/react";
import { Link } from "react-router-dom";

import { type AiJob } from "../../api/aiJobs";
import { PATHS } from "../../app/routePaths";

type Props = {
  job: AiJob;
  compact?: boolean;
  onCancel?: () => void;
  onRetry?: () => void;
  onDismiss?: () => void;
};

const workflowLabels = {
  course_builder: "智能建课",
  resource_generation: "资源生成",
  embedding_reindex: "向量索引重建",
  material_ingestion: "资料解析"
} as const;

function resultHref(job: AiJob) {
  if (job.workflow === "course_builder" && job.result.course_id) return `/app/courses/${job.result.course_id}`;
  if (job.workflow === "resource_generation" && job.course_id) {
    const resourceIds = Array.isArray(job.result.resource_ids) ? job.result.resource_ids : [];
    const resource = resourceIds[0] ? `&resource_id=${resourceIds[0]}` : "";
    return `${PATHS.studio}?course_id=${job.course_id}${resource}`;
  }
  if (job.workflow === "material_ingestion" && job.request.material_id) return `${PATHS.library}?material_id=${job.request.material_id}`;
  return null;
}

export function AiJobProgress({ job, compact = false, onCancel, onRetry, onDismiss }: Props) {
  const completedHref = job.status === "completed" ? resultHref(job) : null;
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
        {completedHref ? <Link className="icon-text-button" to={completedHref}>查看结果</Link> : null}
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
        {job.status === "completed" && onDismiss ? <button type="button" className="icon-text-button" onClick={onDismiss}><X size={14} /><span>收起</span></button> : null}
      </div>
    </section>
  );
}

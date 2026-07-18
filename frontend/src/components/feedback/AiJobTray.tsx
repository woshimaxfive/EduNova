import { CaretDown, CaretUp, CircleNotch } from "@phosphor-icons/react";
import { useState } from "react";

import { useAuthStore } from "../../features/auth/authStore";
import { useAiJobs } from "../../features/aiJobs/AiJobProvider";
import { AiJobProgress } from "./AiJobProgress";

export function AiJobTray() {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const { jobs, cancelJob, retryJob, deleteJob, dismissJob } = useAiJobs();
  const [expandedManually, setExpandedManually] = useState(false);
  const visible = jobs.filter((job) => ["queued", "running", "cancelling", "failed", "completed"].includes(job.status)).slice(0, 4);
  const hasActiveJob = visible.some((job) => ["queued", "running", "cancelling"].includes(job.status));
  const expanded = hasActiveJob || expandedManually;
  if (!isAuthenticated || visible.length === 0) return null;

  return (
    <aside className={`ai-job-tray${expanded ? " ai-job-tray--expanded" : ""}`} aria-label="后台 AI 任务">
      <button type="button" className="ai-job-tray__toggle" onClick={() => setExpandedManually((value) => !value)} aria-expanded={expanded}>
        <CircleNotch className={visible.some((job) => job.status === "running") ? "spin" : ""} size={17} />
        <span>{visible.length} 个后台任务</span>
        {expanded ? <CaretDown size={16} /> : <CaretUp size={16} />}
      </button>
      {expanded ? (
        <div className="ai-job-tray__list">
          {visible.map((job) => (
            <AiJobProgress
              key={job.job_id}
              job={job}
              compact
              onCancel={() => void cancelJob(job.job_id)}
              onRetry={() => void retryJob(job.job_id)}
              onDelete={() => void deleteJob(job.job_id)}
              onDismiss={() => dismissJob(job.job_id)}
            />
          ))}
        </div>
      ) : null}
    </aside>
  );
}

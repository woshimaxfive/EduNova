import { CheckCircle, CircleNotch, Clock, WarningCircle } from "@phosphor-icons/react";

import { type WorkflowStage } from "../../types/api";

type WorkflowStatusRailProps = {
  title: string;
  description: string;
  stages: WorkflowStage[];
};

export function WorkflowStatusRail({ title, description, stages }: WorkflowStatusRailProps) {
  return (
    <section className="workflow-rail" role="region" aria-label="上传建课状态">
      <div className="workflow-rail-copy">
        <p className="section-kicker">上传建课</p>
        <h2>{title}</h2>
        <p>{description}</p>
      </div>
      <ol className="workflow-steps">
        {stages.map((stage) => (
          <li className={`workflow-step ${stage.status}`} key={stage.id}>
            <span className="workflow-icon" aria-hidden="true">
              {stage.status === "completed" ? (
                <CheckCircle size={18} weight="duotone" />
              ) : stage.status === "failed" ? (
                <WarningCircle size={18} weight="duotone" />
              ) : stage.status === "active" ? (
                <CircleNotch size={18} weight="duotone" />
              ) : (
                <Clock size={18} weight="duotone" />
              )}
            </span>
            <span className="workflow-step-body">
              <strong>{stage.label}</strong>
              <small>{stage.nextAction ?? stage.message}</small>
            </span>
            <span className="workflow-progress" aria-label={`${stage.label} ${stage.progressPercent}%`}>
              <span style={{ width: `${stage.progressPercent}%` }} />
            </span>
          </li>
        ))}
      </ol>
    </section>
  );
}

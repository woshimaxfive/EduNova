import { ArrowRight, CircleNotch, WarningCircle } from "@phosphor-icons/react";
import { Link } from "react-router-dom";

import { type LearningNextAction } from "../../api/learning";
import { learningActionButtonLabel, learningActionHref } from "../../features/learning-actions/learningActions";

type NextLearningActionProps = {
  action: LearningNextAction | null | undefined;
  isLoading?: boolean;
  error?: boolean;
  compact?: boolean;
  presentation?: "default" | "home";
  onAction?: (action: LearningNextAction) => void;
};

export function NextLearningAction({ action, isLoading = false, error = false, compact = false, presentation = "default", onAction }: NextLearningActionProps) {
  const className = `next-learning-action${presentation === "home" ? " home" : ""}${compact ? " compact" : ""}`;
  if (isLoading) {
    return <section className={className} role="status"><CircleNotch className="spin" size={19} /><div><span>下一步学习</span><strong>正在同步学习状态</strong></div></section>;
  }
  if (error || !action) return null;
  const href = learningActionHref(action);
  const content = <>{action.status === "blocked" ? <WarningCircle size={19} weight="duotone" /> : action.status === "waiting" ? <CircleNotch className="spin" size={19} /> : null}<span>{learningActionButtonLabel(action)}</span><ArrowRight size={17} weight="bold" /></>;
  return (
    <section className={`${className} ${action.status}`} aria-label="下一步学习">
      <div><span>下一步学习</span><strong>{action.label}</strong><p>{action.description}</p></div>
      {onAction ? <button type="button" onClick={() => onAction(action)}>{content}</button> : <Link to={href}>{content}</Link>}
    </section>
  );
}

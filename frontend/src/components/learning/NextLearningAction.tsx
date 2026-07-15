import { ArrowRight, CircleNotch, WarningCircle } from "@phosphor-icons/react";
import { Link } from "react-router-dom";

import { type LearningNextAction } from "../../api/learning";
import { learningActionButtonLabel, learningActionHref } from "../../features/learning-actions/learningActions";

type NextLearningActionProps = {
  action: LearningNextAction | null | undefined;
  isLoading?: boolean;
  error?: boolean;
  compact?: boolean;
  onAction?: (action: LearningNextAction) => void;
};

export function NextLearningAction({ action, isLoading = false, error = false, compact = false, onAction }: NextLearningActionProps) {
  if (isLoading) {
    return <section className={`next-learning-action${compact ? " compact" : ""}`} role="status"><CircleNotch className="spin" size={19} /><div><span>下一步学习</span><strong>正在同步学习状态</strong></div></section>;
  }
  if (error || !action) return null;
  const href = learningActionHref(action);
  const content = <>{action.status === "blocked" ? <WarningCircle size={19} weight="duotone" /> : action.status === "waiting" ? <CircleNotch className="spin" size={19} /> : null}<span>{learningActionButtonLabel(action)}</span><ArrowRight size={17} weight="bold" /></>;
  return (
    <section className={`next-learning-action ${action.status}${compact ? " compact" : ""}`} aria-label="下一步学习">
      <div><span>下一步学习</span><strong>{action.label}</strong><p>{action.description}</p></div>
      {onAction ? <button type="button" onClick={() => onAction(action)}>{content}</button> : <Link to={href}>{content}</Link>}
    </section>
  );
}

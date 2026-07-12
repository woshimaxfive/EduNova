import { ArrowRight, ChartLineUp, CheckCircle, Target } from "@phosphor-icons/react";
import { Link } from "react-router-dom";

import { type PracticeNextAction, difficultyLabel } from "../../features/practice/practiceViewModel";

type PracticeResultSummaryProps = {
  score: number;
  correctCount: number;
  totalCount: number;
  effectiveDifficulty: string;
  nextAction: PracticeNextAction;
  onStartNew: () => void;
  onOpenResults: () => void;
};

export function PracticeResultSummary({
  score,
  correctCount,
  totalCount,
  effectiveDifficulty,
  nextAction,
  onStartNew,
  onOpenResults
}: PracticeResultSummaryProps) {
  const summary = score >= 80
    ? "核心概念掌握较稳，可以继续推进下一项学习任务。"
    : score >= 60
      ? "基础已经建立，先补齐错题暴露的概念再继续。"
      : "当前知识点仍需巩固，建议先回到课程内容完成针对性复习。";

  const primaryAction = nextAction.href ? (
    <Link className="practice-result-primary" to={nextAction.href}>
      {nextAction.label}
      <ArrowRight size={17} weight="bold" aria-hidden="true" />
    </Link>
  ) : (
    <button className="practice-result-primary" type="button" onClick={onStartNew}>
      {nextAction.label}
      <ArrowRight size={17} weight="bold" aria-hidden="true" />
    </button>
  );

  return (
    <section className="practice-result-summary" aria-label="练习结果摘要">
      <div className="practice-result-score">
        <span>本次得分</span>
        <strong>{score}</strong>
      </div>
      <div className="practice-result-copy">
        <span>练习完成</span>
        <h2>{summary}</h2>
        <div>
          <span><CheckCircle size={16} weight="duotone" aria-hidden="true" />答对 {correctCount} / {totalCount}</span>
          <span><Target size={16} weight="duotone" aria-hidden="true" />{difficultyLabel(effectiveDifficulty)}难度</span>
        </div>
      </div>
      <div className="practice-result-actions">
        {primaryAction}
        <button type="button" onClick={onOpenResults}>
          <ChartLineUp size={17} weight="duotone" aria-hidden="true" />
          查看学习更新
        </button>
      </div>
    </section>
  );
}

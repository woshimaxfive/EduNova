import { ArrowRight, ChartLineUp, CheckCircle, Target } from "@phosphor-icons/react";
import { Link } from "react-router-dom";

import { type LearningNextAction } from "../../api/learning";
import { learningActionHref } from "../../features/learning-actions/learningActions";
import { difficultyLabel } from "../../features/practice/practiceViewModel";

type PracticeResultSummaryProps = {
  score: number | null;
  gradingStatus: "complete" | "partial" | "ungraded";
  correctCount: number;
  gradedCount: number;
  totalCount: number;
  effectiveDifficulty: string;
  nextAction: LearningNextAction | null;
  onStartNew: () => void;
  onOpenResults: () => void;
  onRegrade: () => void;
  isRegrading: boolean;
};

export function PracticeResultSummary({
  score,
  gradingStatus,
  correctCount,
  gradedCount,
  totalCount,
  effectiveDifficulty,
  nextAction,
  onStartNew,
  onOpenResults,
  onRegrade,
  isRegrading
}: PracticeResultSummaryProps) {
  const summary = score === null
    ? "简答题暂未评分，当前结果不会影响掌握度、弱点或学习路径。"
    : score >= 80
    ? "核心概念掌握较稳，可以继续推进下一项学习任务。"
    : score >= 60
      ? "基础已经建立，先补齐错题暴露的概念再继续。"
      : "当前知识点仍需巩固，建议先回到课程内容完成针对性复习。";

  const primaryAction = nextAction ? (
    <Link className="practice-result-primary" to={learningActionHref(nextAction)}>
      {nextAction.label}
      <ArrowRight size={17} weight="bold" aria-hidden="true" />
    </Link>
  ) : (
    <button className="practice-result-primary" type="button" onClick={onStartNew}>
      开始新练习
      <ArrowRight size={17} weight="bold" aria-hidden="true" />
    </button>
  );

  return (
    <section className="practice-result-summary" aria-label="练习结果摘要">
      <div className="practice-result-score">
        <span>本次得分</span>
        <strong>{score ?? "—"}</strong>
      </div>
      <div className="practice-result-copy">
        <span>{gradingStatus === "complete" ? "练习完成" : gradingStatus === "partial" ? "部分评分" : "暂未评分"}</span>
        <h2>{summary}</h2>
        <div>
          <span><CheckCircle size={16} weight="duotone" aria-hidden="true" />
            {gradingStatus === "complete" ? `答对 ${correctCount} / ${totalCount}` : `已评分 ${gradedCount} / ${totalCount}`}
          </span>
          <span><Target size={16} weight="duotone" aria-hidden="true" />{difficultyLabel(effectiveDifficulty)}难度</span>
        </div>
      </div>
      <div className="practice-result-actions">
        {gradingStatus !== "complete" ? (
          <button type="button" onClick={onRegrade} disabled={isRegrading}>
            {isRegrading ? "正在重评" : "重试简答题评分"}
          </button>
        ) : null}
        {primaryAction}
        <button type="button" onClick={onOpenResults}>
          <ChartLineUp size={17} weight="duotone" aria-hidden="true" />
          查看学习更新
        </button>
      </div>
    </section>
  );
}

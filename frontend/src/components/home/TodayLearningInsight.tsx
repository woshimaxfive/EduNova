import { ArrowRight, Brain, ChartDonut, Target, WarningCircle } from "@phosphor-icons/react";
import { Link } from "react-router-dom";

import type { CourseLearningState, CourseMasteryMap } from "../../api/courses";
import type { DashboardCourse } from "../../api/dashboard";
import type { LearningNextAction } from "../../api/learning";
import { learningActionButtonLabel, learningActionHref } from "../../features/learning-actions/learningActions";

type Props = {
  course: DashboardCourse | null;
  action: LearningNextAction | null | undefined;
  mastery: CourseMasteryMap | null;
  learningState: CourseLearningState | null;
  loading?: boolean;
};

export function TodayLearningInsight({ course, action, mastery, learningState, loading = false }: Props) {
  if (loading) return <section className="today-learning-insight loading" role="status"><span>今日学习洞察</span><strong>正在汇总真实学习状态</strong></section>;
  if (!course || !action) return null;
  const summary = mastery?.summary;
  const weakness = learningState?.weakness_summary;
  const averageScore = summary?.average_score;
  const activeWeaknesses = (weakness?.confirmed_count ?? 0) + (weakness?.reviewing_count ?? 0);
  const pendingWeaknesses = weakness?.pending_count ?? 0;
  const masteryPoints = Array.isArray(mastery?.points) ? mastery.points : [];
  const focusPoint = masteryPoints.find((point) => point.id === action.knowledge_point_id)
    ?? masteryPoints.filter((point) => point.score !== null).sort((left, right) => (left.score ?? 101) - (right.score ?? 101))[0];

  return (
    <section className="today-learning-insight" aria-label="今日学习洞察">
      <header><h2>今日学习洞察</h2><strong>{course.title}</strong></header>
      <div className="today-learning-insight-grid">
        <article><Target size={20} weight="duotone" /><span>当前重点</span><strong>{focusPoint?.title ?? action.label}</strong><small>{action.description}</small></article>
        <article><ChartDonut size={20} weight="duotone" /><span>真实平均掌握度</span><strong>{averageScore == null ? "尚未评估" : `${Math.round(averageScore)} 分`}</strong><small>{summary?.assessed_count ? `来自 ${summary.assessed_count} 个已评估知识点` : "完成练习后形成可靠数据"}</small></article>
        <article><WarningCircle size={20} weight="duotone" /><span>薄弱点</span><strong>{activeWeaknesses} 个已确认 · {pendingWeaknesses} 个待确认</strong><small>{weakness?.latest_evidence_at ? "依据最近一次真实学习证据更新" : "目前没有足够证据，不做推测"}</small></article>
      </div>
      <footer><div><Brain size={18} weight="duotone" /><span>系统依据当前课程、掌握度、弱点和任务状态确定下一步</span></div><Link to={learningActionHref(action)}><span>{learningActionButtonLabel(action)}</span><ArrowRight size={17} weight="bold" /></Link></footer>
    </section>
  );
}

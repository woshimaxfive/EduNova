import { ArrowRight, BookOpenText, ChartLineUp, CheckCircle, Target, WarningCircle } from "@phosphor-icons/react";
import { Link } from "react-router-dom";

import type { CourseMasteryMap, CourseMasteryPoint } from "../../api/courses";
import type { PracticeSessionSummary } from "../../api/practice";
import type { AssessmentReport } from "../../api/reports";
import type { ReportFreshness } from "../../features/reports/reportViewModel";
import type { LearningNextAction } from "../../api/learning";
import { learningActionHref } from "../../features/learning-actions/learningActions";
import { MasteryOverviewChart, PracticeTrendChart } from "../visualization/LearningCharts";

type ReportDashboardProps = {
  report: AssessmentReport | null | undefined;
  masteryMap: CourseMasteryMap | null | undefined;
  latestPractice: PracticeSessionSummary | null | undefined;
  freshness: ReportFreshness;
  averageMastery: number | null;
  trendScores: number[];
  trendDelta: number | null;
  trendLabel: string;
  weakestPoints: CourseMasteryPoint[];
  primaryAction: LearningNextAction | null;
  buildPracticeHref: (knowledgePointId: string) => string;
  dataWarning: string;
  reportError: string;
  isLoading: boolean;
  onGenerate: () => void;
  onRetryReport: () => void;
};

function scoreLabel(score: number | null | undefined) {
  return typeof score === "number" ? `${Math.round(score)} 分` : "暂无";
}

const RESOURCE_LABELS: Record<string, string> = {
  doc: "文档",
  mindmap: "导图",
  quiz: "练习",
  code: "代码",
  slide: "幻灯片",
  animation: "动画",
  video: "外部视频"
};

export function ReportDashboard({
  report,
  masteryMap,
  latestPractice,
  freshness,
  averageMastery,
  trendScores,
  trendDelta,
  trendLabel,
  weakestPoints,
  primaryAction,
  buildPracticeHref,
  dataWarning,
  reportError,
  isLoading,
  onGenerate,
  onRetryReport
}: ReportDashboardProps) {
  const summary = masteryMap?.summary;
  const masteryPoints = Array.isArray(masteryMap?.points) ? masteryMap.points : [];
  const weaknessProgress = report?.report.weakness_progress;
  const snapshotTitle = freshness === "unavailable"
    ? "报告快照暂时无法读取"
    : report?.status === "ready"
      ? "最近报告快照"
      : "还没有真实学习报告";
  const snapshotSummary = freshness === "unavailable"
    ? "实时学习数据仍可查看，重新读取后会恢复报告总结与建议。"
    : report?.status === "ready"
    ? report.report.summary
    : "完成一次课程练习后可生成报告";

  return (
    <main className="report-dashboard" aria-label="学习数据仪表盘">
      {freshness === "stale" ? (
        <div className="report-freshness-note" role="status">
          <WarningCircle size={18} weight="duotone" aria-hidden="true" />
          <span>实时数据已包含新的练习结果，下面的报告文字仍是上一次生成的快照。</span>
          <button type="button" onClick={onGenerate}>更新报告</button>
        </div>
      ) : null}
      {report?.personalization?.status === "stale" ? (
        <div className="report-freshness-note" role="status">
          <WarningCircle size={18} weight="duotone" aria-hidden="true" />
          <span>学习画像已变化，实时数据不受影响；更新报告后会应用新的个性化依据。</span>
          <button type="button" onClick={onGenerate}>更新报告</button>
        </div>
      ) : null}
      {dataWarning ? <p className="report-data-warning">{dataWarning}</p> : null}
      {reportError ? (
        <div className="form-error report-workspace-error" role="alert">
          <span>{reportError}</span>
          {freshness === "unavailable" ? <button type="button" onClick={onRetryReport}>重新读取</button> : null}
        </div>
      ) : null}

      <section className="report-metric-strip" aria-label="实时学习指标">
        <article>
          <span>最新练习</span>
          <strong>{scoreLabel(latestPractice?.score ?? report?.score)}</strong>
          <small>{latestPractice?.status === "completed" ? "最近一次已完成练习" : "等待完成练习"}</small>
        </article>
        <article>
          <span>平均掌握度</span>
          <strong>{averageMastery === null ? "未评估" : `${averageMastery}%`}</strong>
          <small>{summary?.assessed_count ?? 0} 个知识点有有效证据</small>
        </article>
        <article>
          <span>已掌握</span>
          <strong>{summary?.mastered_count ?? 0}</strong>
          <small>{summary?.learning_count ?? 0} 个正在学习</small>
        </article>
        <article>
          <span>薄弱知识点</span>
          <strong>{summary?.weak_count ?? 0}</strong>
          <small>{summary?.recommended_review_count ?? 0} 个建议复习</small>
        </article>
        <article>
          <span>练习趋势</span>
          <strong>{trendDelta === null ? "--" : trendDelta > 0 ? `+${trendDelta}` : trendDelta}</strong>
          <small>{trendLabel}</small>
        </article>
      </section>

      <div className="report-dashboard-grid">
        <section className="report-chart-section" aria-labelledby="report-trend-heading">
          <header>
            <div>
              <span>最近学习表现</span>
              <h2 id="report-trend-heading">练习得分趋势</h2>
            </div>
            <ChartLineUp size={22} weight="duotone" aria-hidden="true" />
          </header>
          {trendScores.length > 0 ? (
            <>
              <PracticeTrendChart scores={trendScores} />
              <ol className="report-chart-fallback" aria-label="练习得分文本列表">
                {trendScores.map((score, index) => <li key={`${index}-${score}`}><span>第 {index + 1} 次</span><strong>{score} 分</strong></li>)}
              </ol>
            </>
          ) : (
            <div className="report-chart-empty"><ChartLineUp size={30} weight="duotone" /><p>完成练习后，这里会显示真实得分趋势。</p></div>
          )}
        </section>

        <section className="report-chart-section report-mastery-section" aria-labelledby="report-mastery-heading">
          <header>
            <div>
              <span>当前学习状态</span>
              <h2 id="report-mastery-heading">知识点掌握度</h2>
            </div>
            <Target size={22} weight="duotone" aria-hidden="true" />
          </header>
          {(summary?.assessed_count ?? 0) > 0 ? (
            <>
              <MasteryOverviewChart points={masteryPoints} />
              <ol className="report-mastery-fallback" aria-label="知识点掌握度文本列表">
                {masteryPoints.map((point) => <li key={point.id}><span>{point.title}</span><strong>{point.score === null ? "未评估" : `${point.score} 分`}</strong></li>)}
              </ol>
            </>
          ) : (
            <div className="report-chart-empty"><BookOpenText size={30} weight="duotone" /><p>课程还没有可计算掌握度的知识点。</p></div>
          )}
        </section>
      </div>

      <section className="report-snapshot-strip" aria-label="最近报告快照">
        <div>
          <span>{snapshotTitle}</span>
          <p>{snapshotSummary}</p>
        </div>
        <small>{freshness === "unavailable" ? "报告读取失败，未判定为空报告" : report?.created_at ? `生成于 ${new Intl.DateTimeFormat("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }).format(new Date(report.created_at))}` : "等待真实练习证据"}</small>
      </section>

      <section className="report-resource-usage" aria-labelledby="report-weakness-progress-heading">
        <header>
          <div><span>阶段晋级</span><h2 id="report-weakness-progress-heading">薄弱点进展</h2></div>
          <small>{weaknessProgress?.resolved_count ?? 0} 项已攻克</small>
        </header>
        {weaknessProgress?.recent_resolutions?.length ? (
          <ul>
            {weaknessProgress.recent_resolutions.map((item) => (
              <li key={`${item.title}-${item.next_review_at ?? "resolved"}`}>
                <strong>{item.title}</strong>
                <span>{item.latest_score === null ? "已通过再测" : `再测 ${item.latest_score} 分`}</span>
                {item.improvement === null ? null : <span>提升 {item.improvement} 分</span>}
                <span>{item.next_review_at ? `下次复习 ${new Intl.DateTimeFormat("zh-CN", { month: "2-digit", day: "2-digit" }).format(new Date(item.next_review_at))}` : "等待复习安排"}</span>
              </li>
            ))}
          </ul>
        ) : <p>完成针对性再测后，这里会展示从发现薄弱点到攻克的真实进展。</p>}
        {(weaknessProgress?.due_review_count ?? 0) > 0 ? <p>{weaknessProgress?.due_review_count} 项已到间隔复习时间。</p> : null}
      </section>

      <section className="report-resource-usage" aria-labelledby="report-resource-usage-heading">
        <header>
          <div><span>课程级反馈</span><h2 id="report-resource-usage-heading">资源使用概览</h2></div>
          <small>只影响本课程后续资源与路径策略，不写入长期画像</small>
        </header>
        {Object.entries(report?.report.resource_usage_summary ?? {}).length > 0 ? (
          <ul>
            {Object.entries(report?.report.resource_usage_summary ?? {}).map(([resourceType, counts]) => (
              <li key={resourceType}>
                <strong>{RESOURCE_LABELS[resourceType] ?? resourceType}</strong>
                <span>打开 {counts?.opened ?? 0}</span>
                <span>完成 {counts?.completed ?? 0}</span>
                <span>有帮助 {counts?.helpful ?? 0}</span>
                <span>偏难 {counts?.too_hard ?? 0}</span>
                <span>偏简单 {counts?.too_easy ?? 0}</span>
                <span>没帮助 {counts?.not_helpful ?? 0}</span>
              </li>
            ))}
          </ul>
        ) : <p>完成资源学习并提交反馈后，这里会显示按模态去重的真实使用情况。</p>}
      </section>

      <section className="report-lower-grid">
        <div className="report-weakness-section" aria-labelledby="report-weakness-heading">
          <header>
            <div><span>实时排序</span><h2 id="report-weakness-heading">优先巩固</h2></div>
            <strong>{weakestPoints.length} 项</strong>
          </header>
          {weakestPoints.length > 0 ? (
            <ol>
              {weakestPoints.map((point, index) => (
                <li key={point.id}>
                  <span>{String(index + 1).padStart(2, "0")}</span>
                  <div><strong>{point.title}</strong><small>{point.chapter || "课程知识点"} · {point.status === "weak" ? "薄弱" : "建议复习"}</small></div>
                  <b>{point.score === null ? "未评估" : point.score}</b>
                  <Link to={buildPracticeHref(point.id)} aria-label={`针对练习${point.title}`}>
                    <ArrowRight size={16} weight="bold" aria-hidden="true" />
                  </Link>
                </li>
              ))}
            </ol>
          ) : (
            <div className="report-list-empty"><CheckCircle size={22} weight="duotone" /><span>当前没有需要优先处理的薄弱知识点。</span></div>
          )}
        </div>

        <aside className="report-next-action" aria-label="建议下一步">
          <span>建议下一步</span>
          <h2>{primaryAction?.label ?? "继续积累学习证据"}</h2>
          <p>{primaryAction?.description ?? "完成课程学习或练习后，这里会给出明确的下一步。"}</p>
          {primaryAction?.kind === "update_report" ? (
            <button type="button" onClick={onGenerate}>更新学习报告<ArrowRight size={17} weight="bold" /></button>
          ) : primaryAction ? (
            <Link to={learningActionHref(primaryAction)}>{primaryAction.label}<ArrowRight size={17} weight="bold" /></Link>
          ) : null}
        </aside>
      </section>

      {isLoading ? <div className="report-loading-overlay" role="status">正在同步学习数据</div> : null}
    </main>
  );
}

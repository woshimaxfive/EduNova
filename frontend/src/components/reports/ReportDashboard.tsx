import { ArrowRight, BookOpenText, ChartLineUp, CheckCircle, Target, WarningCircle } from "@phosphor-icons/react";
import { Link } from "react-router-dom";

import type { CourseMasteryMap, CourseMasteryPoint } from "../../api/courses";
import type { PracticeSessionDetail } from "../../api/practice";
import type { AssessmentReport } from "../../api/reports";
import type { ReportFreshness, ReportPrimaryAction } from "../../features/reports/reportViewModel";
import { MasteryOverviewChart, PracticeTrendChart } from "../visualization/LearningCharts";

type ReportDashboardProps = {
  report: AssessmentReport | null | undefined;
  masteryMap: CourseMasteryMap | null | undefined;
  latestPractice: PracticeSessionDetail | null | undefined;
  freshness: ReportFreshness;
  averageMastery: number;
  trendScores: number[];
  trendDelta: number | null;
  trendLabel: string;
  weakestPoints: CourseMasteryPoint[];
  primaryAction: ReportPrimaryAction;
  primaryActionHref: string | null;
  buildPracticeHref: (knowledgePointId: string) => string;
  dataWarning: string;
  reportError: string;
  isLoading: boolean;
  onGenerate: () => void;
};

function scoreLabel(score: number | null | undefined) {
  return typeof score === "number" ? `${Math.round(score)} 分` : "暂无";
}

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
  primaryActionHref,
  buildPracticeHref,
  dataWarning,
  reportError,
  isLoading,
  onGenerate
}: ReportDashboardProps) {
  const summary = masteryMap?.summary;
  const masteryPoints = Array.isArray(masteryMap?.points) ? masteryMap.points : [];
  const snapshotTitle = report?.status === "ready" ? "最近报告快照" : "还没有真实学习报告";
  const snapshotSummary = report?.status === "ready"
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
      {dataWarning ? <p className="report-data-warning">{dataWarning}</p> : null}
      {reportError ? <p className="form-error report-workspace-error">{reportError}</p> : null}

      <section className="report-metric-strip" aria-label="实时学习指标">
        <article>
          <span>最新练习</span>
          <strong>{scoreLabel(latestPractice?.score ?? report?.score)}</strong>
          <small>{latestPractice?.status === "completed" ? "最近一次已完成练习" : "等待完成练习"}</small>
        </article>
        <article>
          <span>平均掌握度</span>
          <strong>{averageMastery}%</strong>
          <small>{summary?.total_count ?? 0} 个知识点实时均值</small>
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
          {masteryPoints.length > 0 ? (
            <>
              <MasteryOverviewChart points={masteryPoints} />
              <ol className="report-mastery-fallback" aria-label="知识点掌握度文本列表">
                {masteryPoints.map((point) => <li key={point.id}><span>{point.title}</span><strong>{point.score} 分</strong></li>)}
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
        <small>{report?.created_at ? `生成于 ${new Intl.DateTimeFormat("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }).format(new Date(report.created_at))}` : "等待真实练习证据"}</small>
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
                  <b>{point.score}</b>
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
          <h2>{primaryAction.label}</h2>
          <p>{primaryAction.description}</p>
          {primaryAction.type === "update_report" ? (
            <button type="button" onClick={onGenerate}>更新学习报告<ArrowRight size={17} weight="bold" /></button>
          ) : primaryActionHref ? (
            <Link to={primaryActionHref}>{primaryAction.label}<ArrowRight size={17} weight="bold" /></Link>
          ) : null}
        </aside>
      </section>

      {isLoading ? <div className="report-loading-overlay" role="status">正在同步学习数据</div> : null}
    </main>
  );
}

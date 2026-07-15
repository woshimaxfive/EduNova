import type { CourseMasteryPoint } from "../../api/courses";
import type { PracticeSessionSummary } from "../../api/practice";
import type { AssessmentReport } from "../../api/reports";

export type ReportFreshness = "empty" | "current" | "stale" | "unknown" | "unavailable";

export function calculateAverageMastery(points: CourseMasteryPoint[]) {
  const assessed = points.filter((point): point is CourseMasteryPoint & { score: number } => point.score !== null);
  if (assessed.length === 0) return null;
  const average = assessed.reduce((total, point) => total + point.score, 0) / assessed.length;
  return Math.min(100, Math.max(0, Math.round(average)));
}

export function getReportFreshness(
  report: AssessmentReport | null | undefined,
  latestPractice: PracticeSessionSummary | null | undefined
): ReportFreshness {
  if (!report || report.status !== "ready") return "empty";
  if (!latestPractice || latestPractice.status !== "completed") return "current";
  if (!report.practice_session_id || report.practice_session_id !== latestPractice.id) return "stale";
  if (!report.created_at) return "stale";
  return new Date(latestPractice.updated_at).getTime() > new Date(report.created_at).getTime() ? "stale" : "current";
}

export function buildCurrentTrendScores(
  report: AssessmentReport | null | undefined,
  recentPractices: PracticeSessionSummary[] | null | undefined
) {
  const liveScores = (Array.isArray(recentPractices) ? recentPractices : [])
    .filter((practice) => practice.status === "completed" && typeof practice.score === "number")
    .slice(0, 5)
    .reverse()
    .map((practice) => practice.score as number);
  return liveScores.length > 0 ? liveScores : [...(report?.report.trend?.scores ?? [])].slice(-5);
}

export function sortMasteryPoints(points: CourseMasteryPoint[]) {
  return [...points].sort((left, right) => {
    if (left.score === null) return right.score === null ? left.order_index - right.order_index : 1;
    if (right.score === null) return -1;
    return left.score - right.score || left.order_index - right.order_index;
  });
}

export function calculateCurrentTrend(scores: number[]) {
  if (scores.length < 2) {
    return { direction: "insufficient" as const, delta: null, label: "至少完成两次练习后显示趋势" };
  }
  const delta = Math.round(scores[scores.length - 1] - scores[0]);
  if (delta > 0) return { direction: "improved" as const, delta, label: `较早期提升 ${delta} 分` };
  if (delta < 0) return { direction: "declined" as const, delta, label: `较早期下降 ${Math.abs(delta)} 分` };
  return { direction: "stable" as const, delta, label: "近期表现稳定" };
}

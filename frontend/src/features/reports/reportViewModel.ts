import type { CourseMasteryMap, CourseMasteryPoint } from "../../api/courses";
import type { LearningPathDetail } from "../../api/paths";
import type { PracticeSessionDetail } from "../../api/practice";
import type { AssessmentReport } from "../../api/reports";

export type ReportFreshness = "empty" | "current" | "stale";

export type ReportPrimaryAction =
  | { type: "update_report"; label: string; description: string }
  | { type: "practice"; label: string; description: string; knowledgePoint: CourseMasteryPoint }
  | { type: "path"; label: string; description: string }
  | { type: "course"; label: string; description: string };

export function calculateAverageMastery(points: CourseMasteryPoint[]) {
  if (points.length === 0) return 0;
  const average = points.reduce((total, point) => total + point.score, 0) / points.length;
  return Math.min(100, Math.max(0, Math.round(average)));
}

export function getReportFreshness(
  report: AssessmentReport | null | undefined,
  latestPractice: PracticeSessionDetail | null | undefined
): ReportFreshness {
  if (!report || report.status !== "ready") return "empty";
  if (!latestPractice || latestPractice.status !== "completed") return "current";
  if (!report.practice_session_id || report.practice_session_id !== latestPractice.id) return "stale";
  if (!report.created_at) return "stale";
  return new Date(latestPractice.updated_at).getTime() > new Date(report.created_at).getTime() ? "stale" : "current";
}

export function buildCurrentTrendScores(
  report: AssessmentReport | null | undefined,
  latestPractice: PracticeSessionDetail | null | undefined
) {
  const scores = [...(report?.report.trend?.scores ?? [])];
  if (
    latestPractice?.status === "completed"
    && typeof latestPractice.score === "number"
    && report?.practice_session_id !== latestPractice.id
  ) {
    scores.push(latestPractice.score);
  }
  return scores.slice(-5);
}

export function sortMasteryPoints(points: CourseMasteryPoint[]) {
  return [...points].sort((left, right) => left.score - right.score || left.order_index - right.order_index);
}

export function buildReportPrimaryAction(input: {
  freshness: ReportFreshness;
  masteryMap: CourseMasteryMap | null | undefined;
  currentPath: LearningPathDetail | null | undefined;
}): ReportPrimaryAction {
  if (input.freshness === "stale") {
    return {
      type: "update_report",
      label: "更新学习报告",
      description: "新的练习结果尚未写入报告快照。"
    };
  }

  const weakPoint = sortMasteryPoints(input.masteryMap?.points ?? []).find((point) => point.status === "weak");
  if (weakPoint) {
    return {
      type: "practice",
      label: `练习 ${weakPoint.title}`,
      description: `当前掌握度 ${weakPoint.score} 分，优先通过针对性练习巩固。`,
      knowledgePoint: weakPoint
    };
  }

  if (input.currentPath?.status === "active" && input.currentPath.path) {
    return {
      type: "path",
      label: "继续学习路径",
      description: "沿当前学习安排继续推进。"
    };
  }

  return {
    type: "course",
    label: "返回课程空间",
    description: "继续学习课程内容并积累新的学习证据。"
  };
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

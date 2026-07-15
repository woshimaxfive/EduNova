import { describe, expect, it } from "vitest";

import type { CourseMasteryPoint } from "../../api/courses";
import type { PracticeSessionSummary } from "../../api/practice";
import type { AssessmentReport } from "../../api/reports";
import {
  buildCurrentTrendScores,
  calculateCurrentTrend,
  calculateAverageMastery,
  getReportFreshness
} from "./reportViewModel";

const point = (id: string, score: number | null, status: CourseMasteryPoint["status"]): CourseMasteryPoint => ({
  id,
  title: `知识点 ${id}`,
  chapter: null,
  order_index: Number(id),
  status,
  score,
  prerequisite_ids: [],
  weakness_item_ids: [],
  recommended_resource_ids: []
});

const report = {
  id: "1",
  course_id: "808",
  practice_session_id: "501",
  status: "ready",
  score: 70,
  report: {
    summary: "学习总结",
    mastery_update: { weak_count: 1, mastered_count: 1, learning_count: 1 },
    weakness_list: [],
    evidence_refs: [],
    next_step_suggestions: [],
    review_queue_updates: [],
    profile_changes: [],
    trend: { direction: "improved", score_delta: 10, sessions_compared: 2, scores: [60, 70] }
  },
  created_at: "2026-07-10T10:00:00Z"
} satisfies AssessmentReport;

const practice = {
  id: "502",
  course_id: "808",
  title: "练习",
  status: "completed",
  score: 82,
  effective_difficulty: "medium",
  created_at: "2026-07-11T10:00:00Z",
  updated_at: "2026-07-11T10:00:00Z"
} satisfies PracticeSessionSummary;

describe("reportViewModel", () => {
  it("calculates rounded and clamped current mastery", () => {
    expect(calculateAverageMastery([])).toBeNull();
    expect(calculateAverageMastery([point("1", null, "not_started")])).toBeNull();
    expect(calculateAverageMastery([point("1", 44, "weak"), point("2", 75, "mastered")])).toBe(60);
    expect(calculateAverageMastery([point("1", -20, "weak"), point("2", 240, "mastered")])).toBe(100);
  });

  it("marks a report stale when a newer completed practice exists", () => {
    expect(getReportFreshness(report, practice)).toBe("stale");
    expect(buildCurrentTrendScores(report, [practice, { ...practice, id: "501", score: 70, updated_at: "2026-07-10T10:00:00Z" }])).toEqual([70, 82]);
    expect(calculateCurrentTrend([70, 82])).toEqual({ direction: "improved", delta: 12, label: "较早期提升 12 分" });
  });

  it("uses the latest five completed practice summaries before snapshot fallback", () => {
    const recent = [82, 76, 70, 64, 58, 52].map((score, index) => ({
      ...practice,
      id: String(506 - index),
      score,
      updated_at: `2026-07-${String(12 - index).padStart(2, "0")}T10:00:00Z`
    }));
    expect(buildCurrentTrendScores(report, recent)).toEqual([58, 64, 70, 76, 82]);
    expect(buildCurrentTrendScores(report, [])).toEqual([60, 70]);
  });
  it("keeps empty reports honest", () => {
    expect(getReportFreshness({ ...report, status: "empty" }, null)).toBe("empty");
  });
});

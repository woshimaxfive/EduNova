import { describe, expect, it } from "vitest";

import type { CourseMasteryPoint } from "../../api/courses";
import type { PracticeSessionDetail } from "../../api/practice";
import type { AssessmentReport } from "../../api/reports";
import {
  buildCurrentTrendScores,
  buildReportPrimaryAction,
  calculateCurrentTrend,
  calculateAverageMastery,
  getReportFreshness
} from "./reportViewModel";

const point = (id: string, score: number, status: CourseMasteryPoint["status"]): CourseMasteryPoint => ({
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
  requested_difficulty: "adaptive",
  effective_difficulty: "medium",
  questions: [],
  answers: [],
  created_at: "2026-07-11T10:00:00Z",
  updated_at: "2026-07-11T10:00:00Z"
} satisfies PracticeSessionDetail;

describe("reportViewModel", () => {
  it("calculates rounded and clamped current mastery", () => {
    expect(calculateAverageMastery([])).toBe(0);
    expect(calculateAverageMastery([point("1", 44, "weak"), point("2", 75, "mastered")])).toBe(60);
    expect(calculateAverageMastery([point("1", -20, "weak"), point("2", 240, "mastered")])).toBe(100);
  });

  it("marks a report stale when a newer completed practice exists", () => {
    expect(getReportFreshness(report, practice)).toBe("stale");
    expect(buildCurrentTrendScores(report, practice)).toEqual([60, 70, 82]);
    expect(calculateCurrentTrend([60, 70, 82])).toEqual({ direction: "improved", delta: 22, label: "较早期提升 22 分" });
  });

  it("keeps empty reports honest and prioritizes the weakest point otherwise", () => {
    expect(getReportFreshness({ ...report, status: "empty" }, null)).toBe("empty");
    const action = buildReportPrimaryAction({
      freshness: "current",
      masteryMap: {
        course_id: "808",
        summary: { total_count: 2, weak_count: 1, learning_count: 1, mastered_count: 0, recommended_review_count: 0, not_started_count: 0 },
        points: [point("1", 54, "learning"), point("2", 31, "weak")]
      },
      currentPath: null
    });
    expect(action.type).toBe("practice");
    expect(action.label).toContain("知识点 2");
  });
});

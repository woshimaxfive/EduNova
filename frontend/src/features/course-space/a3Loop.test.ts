import { describe, expect, it } from "vitest";

import { buildCourseLoopSummary, buildStudySteps, calculateMasteryPercent, type CourseLoopInput } from "./a3Loop";

const baseInput: CourseLoopInput = {
  courseTitle: "人工智能导论",
  materialCount: 3,
  knowledgePointCount: 8,
  progressPercent: 42,
  latestQuestion: "为什么 RAG 能减少幻觉？",
  citationCount: 4,
  pendingWeaknessCount: 2,
  confirmedWeaknessCount: 1,
  resourceCount: 5,
  hasActivePath: true,
  latestTraceWorkflow: "course_tutor",
  latestTraceId: "trace_course_001",
  hasLatestReport: true
};

describe("course-space A3 loop view model", () => {
  it("calculates knowledge mastery from the deterministic point scores", () => {
    expect(calculateMasteryPercent([])).toBe(0);
    expect(calculateMasteryPercent([{ score: 35 }, { score: 60 }, { score: 90 }])).toBe(62);
    expect(calculateMasteryPercent([{ score: -20 }, { score: 130 }])).toBe(50);
    expect(calculateMasteryPercent([{ score: Number.NaN }, { score: 75 }])).toBe(38);
  });

  it("builds a course goal from weakness and latest question evidence", () => {
    const summary = buildCourseLoopSummary(baseInput);

    expect(summary.title).toBe("人工智能导论");
    expect(summary.currentGoal).toBe("围绕最新问题处理 3 个待处理弱点");
    expect(summary.evidenceLine).toBe("3 份资料 · 8 个知识点 · 4 条引用 · 5 个资源");
    expect(summary.nextAction).toBe("先确认薄弱点，再生成针对性资源并进入路径任务");
    expect(summary.traceLabel).toBe("course_tutor · trace_course_001");
  });

  it("falls back to course progress when there is no latest question", () => {
    const summary = buildCourseLoopSummary({
      ...baseInput,
      latestQuestion: null,
      citationCount: 0,
      pendingWeaknessCount: 0,
      confirmedWeaknessCount: 0,
      resourceCount: 0,
      hasActivePath: false,
      latestTraceWorkflow: null,
      latestTraceId: null
    });

    expect(summary.currentGoal).toBe("从课程资料和知识点开始建立学习闭环");
    expect(summary.nextAction).toBe("先提问或选择知识点，生成第一批个性化学习依据");
    expect(summary.traceLabel).toBeNull();
  });

  it("moves the next action forward after resources already exist", () => {
    const summary = buildCourseLoopSummary({
      ...baseInput,
      latestQuestion: "这门课最适合先复习哪些知识点？",
      pendingWeaknessCount: 0,
      confirmedWeaknessCount: 0,
      hasActivePath: false,
      hasLatestReport: false
    });

    expect(summary.nextAction).toBe("基于已生成资源进入路径或练习，形成评估回流");
  });

  it("orders study steps according to the A3 learning loop", () => {
    const steps = buildStudySteps(baseInput);

    expect(steps.map((step) => step.key)).toEqual([
      "profile",
      "retrieval",
      "tutor",
      "weakness",
      "resource",
      "path",
      "assessment",
      "report"
    ]);
    expect(steps.find((step) => step.key === "resource")?.status).toBe("ready");
    expect(steps.find((step) => step.key === "assessment")?.status).toBe("next");
  });
});

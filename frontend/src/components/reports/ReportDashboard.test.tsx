import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import type { AssessmentReport } from "../../api/reports";
import { ReportDashboard } from "./ReportDashboard";

const baseReport: AssessmentReport = {
  id: "1",
  course_id: "2",
  practice_session_id: "3",
  status: "ready",
  score: 80,
  created_at: "2026-07-18T10:00:00Z",
  report: {
    summary: "基于真实学习证据生成。",
    mastery_update: { weak_count: 1, mastered_count: 1, learning_count: 1 },
    weakness_list: [],
    evidence_refs: [],
    next_step_suggestions: [],
    review_queue_updates: [],
    profile_changes: [],
    evidence_summary: {
      practice_count: 2,
      answer_count: 10,
      weakness_count: 1,
      path_status: "active",
      resource_count: 3
    }
  }
};

function renderDashboard(report: AssessmentReport) {
  render(
    <MemoryRouter>
      <ReportDashboard
        report={report}
        masteryMap={undefined}
        latestPractice={undefined}
        freshness="current"
        averageMastery={null}
        trendScores={[]}
        trendDelta={null}
        trendLabel="证据不足"
        weakestPoints={[]}
        primaryAction={null}
        buildPracticeHref={() => "/app/practice"}
        dataWarning=""
        reportError=""
        isLoading={false}
        onGenerate={() => undefined}
        onRetryReport={() => undefined}
      />
    </MemoryRouter>
  );
}

describe("ReportDashboard trust summary", () => {
  it.each([
    ["passed", "审核通过"],
    ["warning", "审核有警告"],
    ["failed", "审核未通过"]
  ])("shows the real %s review state", (reviewStatus, expectedLabel) => {
    renderDashboard({
      ...baseReport,
      report: {
        ...baseReport.report,
        review_result: {
          review_status: reviewStatus,
          confidence: 0.86,
          risk_flags: [],
          safety_summary: "安全审核摘要"
        }
      }
    });

    const summary = screen.getByLabelText("报告证据与审核状态");
    expect(summary).toHaveTextContent("练习 2 次 · 作答 10 题 · 资源 3 项");
    expect(summary).toHaveTextContent(expectedLabel);
    expect(summary).toHaveTextContent("置信度 86%");
  });

  it("states when review data is not provided without inventing confidence", () => {
    renderDashboard(baseReport);

    const summary = screen.getByLabelText("报告证据与审核状态");
    expect(summary).toHaveTextContent("审核未提供");
    expect(summary).not.toHaveTextContent("置信度");
  });
});

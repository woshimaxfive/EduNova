import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, it } from "vitest";

import { TodayLearningInsight } from "./TodayLearningInsight";

it("shows only evidence-backed mastery, weakness and next action values", () => {
  render(
    <MemoryRouter>
      <TodayLearningInsight
        course={{ id: "8", title: "算法基础", source_type: "uploaded", progress_label: "学习中", practiced_knowledge_point_count: 2, knowledge_point_count: 6, focus: "排序", next: "继续" }}
        action={{ kind: "study_knowledge_point", status: "ready", label: "学习归并排序", description: "这是当前最低掌握度知识点。", course_id: "8", material_id: null, knowledge_point_id: "2", path_task_id: null, resource_id: null }}
        mastery={{ course_id: "8", summary: { total_count: 2, weak_count: 1, learning_count: 0, mastered_count: 1, recommended_review_count: 0, not_started_count: 0, assessed_count: 2, average_score: 61 }, points: [
          { id: "1", title: "冒泡排序", chapter: "排序", order_index: 0, status: "mastered", score: 82, prerequisite_ids: [], weakness_item_ids: [], recommended_resource_ids: [] },
          { id: "2", title: "归并排序", chapter: "排序", order_index: 1, status: "weak", score: 40, prerequisite_ids: ["1"], weakness_item_ids: [], recommended_resource_ids: [] }
        ] }}
        learningState={{ weakness_summary: { candidate_event_count: 2, pending_count: 1, confirmed_count: 1, reviewing_count: 0, completed_count: 0, dismissed_count: 0, latest_evidence_at: "2026-07-18T08:00:00Z" } } as never}
      />
    </MemoryRouter>
  );
  expect(screen.getByRole("region", { name: "今日学习洞察" })).toHaveTextContent("61 分");
  expect(screen.getByRole("region", { name: "今日学习洞察" })).toHaveTextContent("1 个已确认 · 1 个待确认");
  expect(screen.getByRole("link", { name: /开始学习/ })).toHaveAttribute("href", "/app/courses/8?mode=study&view=overview&knowledge_point_id=2&guided=1");
});

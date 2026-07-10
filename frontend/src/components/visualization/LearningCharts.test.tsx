import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";

import { MasteryOverviewChart, PracticeTrendChart } from "./LearningCharts";

it("keeps accessible chart descriptions when canvas rendering is unavailable", () => {
  render(
    <>
      <MasteryOverviewChart
        points={[
          {
            id: "401",
            title: "启发式搜索",
            chapter: "搜索问题",
            order_index: 0,
            status: "weak",
            score: 38,
            prerequisite_ids: [],
            weakness_item_ids: ["701"],
            recommended_resource_ids: []
          }
        ]}
      />
      <PracticeTrendChart scores={[52, 68, 84]} />
    </>
  );

  expect(screen.getByRole("img", { name: "知识点掌握度柱状图" })).toBeInTheDocument();
  expect(screen.getByRole("img", { name: "最近练习得分趋势图" })).toBeInTheDocument();
});

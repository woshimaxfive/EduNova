import { fireEvent, render, screen } from "@testing-library/react";
import { beforeAll, expect, it, vi } from "vitest";

import { CourseKnowledgeGraph } from "./CourseKnowledgeGraph";

beforeAll(() => {
  vi.stubGlobal(
    "ResizeObserver",
    class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  );
});

it("renders prerequisite knowledge points and keeps node selection interactive", () => {
  const onSelect = vi.fn();
  render(
    <CourseKnowledgeGraph
      points={[
        {
          id: "401",
          title: "状态空间",
          chapter: "搜索问题",
          order_index: 0,
          status: "mastered",
          score: 82,
          prerequisite_ids: [],
          weakness_item_ids: [],
          recommended_resource_ids: []
        },
        {
          id: "402",
          title: "启发式搜索",
          chapter: "搜索问题",
          order_index: 1,
          status: "weak",
          score: 36,
          prerequisite_ids: ["401"],
          weakness_item_ids: ["701"],
          recommended_resource_ids: ["801"]
        }
      ]}
      selectedId="402"
      onSelect={onSelect}
    />
  );

  expect(screen.getByRole("region", { name: "课程知识图谱" })).toBeInTheDocument();
  expect(screen.getByText("当前知识点关系")).toBeInTheDocument();
  expect(screen.getByLabelText("当前图谱范围")).toHaveTextContent("先修 1");
  expect(screen.getByLabelText("当前图谱范围")).toHaveTextContent("启发式搜索");
  expect(screen.getByLabelText("当前图谱范围")).toHaveTextContent("后续 0");
  expect(screen.getByText("先修")).toBeInTheDocument();
  expect(screen.getByText("当前")).toBeInTheDocument();
  fireEvent.click(screen.getByTestId("rf__node-402"));
  expect(onSelect).toHaveBeenCalledWith("402");
});

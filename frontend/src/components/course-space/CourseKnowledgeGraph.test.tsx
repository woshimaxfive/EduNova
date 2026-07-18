import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";

import type { CourseMasteryPoint } from "../../api/courses";
import { CourseKnowledgeGraph } from "./CourseKnowledgeGraph";

const points: CourseMasteryPoint[] = [
  {
    id: "401",
    title: "状态空间",
    chapter: "搜索基础",
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
    chapter: "搜索方法",
    order_index: 1,
    status: "weak",
    score: 36,
    prerequisite_ids: ["401"],
    weakness_item_ids: ["701"],
    recommended_resource_ids: ["801"]
  },
  {
    id: "403",
    title: "A* 搜索",
    chapter: "搜索方法",
    order_index: 2,
    status: "not_started",
    score: null,
    prerequisite_ids: ["402"],
    weakness_item_ids: [],
    recommended_resource_ids: []
  }
];

it("renders a focused learning chain and keeps related knowledge points interactive", () => {
  const onSelect = vi.fn();
  render(<CourseKnowledgeGraph points={points} selectedId="402" onSelect={onSelect} />);

  expect(screen.getByRole("region", { name: "课程知识图谱" })).toBeInTheDocument();
  expect(screen.getAllByText("聚焦链路").length).toBeGreaterThan(0);
  expect(screen.getAllByRole("button", { name: /启发式搜索/ })[0]).toHaveTextContent("36");

  fireEvent.click(screen.getAllByRole("button", { name: /状态空间/ })[0]);
  expect(onSelect).toHaveBeenCalledWith("401");
});

it("shows every chapter in the course overview and enters a focused chain when a point is selected", () => {
  const onSelect = vi.fn();
  render(<CourseKnowledgeGraph points={points} selectedId="402" scope="course" chapter="" onSelect={onSelect} />);

  expect(screen.getAllByText("课程全景").length).toBeGreaterThan(0);
  expect(screen.getByLabelText("课程全景画布")).toBeInTheDocument();
  expect(screen.getAllByRole("button", { name: /状态空间/ }).length).toBeGreaterThan(0);
  expect(screen.getAllByRole("button", { name: /A\* 搜索/ }).length).toBeGreaterThan(0);

  fireEvent.click(screen.getAllByRole("button", { name: /状态空间/ })[0]);
  expect(onSelect).toHaveBeenCalledWith("401");
});

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
  expect(screen.getByText("学习链路")).toBeInTheDocument();
  expect(screen.getByLabelText("当前知识点：启发式搜索")).toHaveTextContent("36 分");
  expect(screen.getByText("直接先修").parentElement).toHaveTextContent("1");
  expect(screen.getByText("即将解锁").parentElement).toHaveTextContent("1");

  fireEvent.click(screen.getByRole("button", { name: /状态空间/ }));
  expect(onSelect).toHaveBeenCalledWith("401");
});

it("shows every chapter in the course overview and enters a focused chain when a point is selected", () => {
  const onSelect = vi.fn();
  render(<CourseKnowledgeGraph points={points} selectedId="402" onSelect={onSelect} />);

  fireEvent.change(screen.getByLabelText("章节"), { target: { value: "" } });

  expect(onSelect).not.toHaveBeenCalled();
  expect(screen.getByText("课程全景")).toBeInTheDocument();
  expect(screen.getByLabelText("课程全部知识点")).toHaveTextContent("搜索基础");
  expect(screen.getByLabelText("课程全部知识点")).toHaveTextContent("搜索方法");
  expect(screen.getByRole("button", { name: /A\* 搜索/ })).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: /状态空间/ }));
  expect(onSelect).toHaveBeenCalledWith("401");
});

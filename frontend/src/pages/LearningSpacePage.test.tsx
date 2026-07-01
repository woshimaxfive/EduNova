import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { LearningSpacePage } from "./LearningSpacePage";

describe("LearningSpacePage", () => {
  it("renders the required Phase 3A learning-space regions", () => {
    render(
      <MemoryRouter>
        <LearningSpacePage />
      </MemoryRouter>
    );

    expect(screen.getByRole("heading", { name: "今天的 AI 学习空间" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "知识学习画布" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Studio 生成区" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "证据与 Agent 轨迹" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "AI 命令栏" })).toBeInTheDocument();
  });

  it("shows Phase 3D workflow and fallback states on the learning-space surface", () => {
    render(
      <MemoryRouter>
        <LearningSpacePage />
      </MemoryRouter>
    );

    expect(screen.getByRole("region", { name: "上传建课状态" })).toBeInTheDocument();
    expect(screen.getByText("资料正在变成课程")).toBeInTheDocument();
    expect(screen.getByText("低依据提示")).toBeInTheDocument();
    expect(screen.getByText("演示兜底内容")).toBeInTheDocument();
  });
});

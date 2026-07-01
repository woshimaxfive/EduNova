import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { LearningSpacePage } from "./LearningSpacePage";

describe("LearningSpacePage", () => {
  it("renders the Phase 3R AI conversation-first home", () => {
    render(
      <MemoryRouter>
        <LearningSpacePage />
      </MemoryRouter>
    );

    expect(screen.getByRole("heading", { name: "上传资料，开始和你的课程对话" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "主页历史" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "AI 学习对话" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "资料库轻入口" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "最近课程" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "学习问题输入" })).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "知识学习画布" })).not.toBeInTheDocument();
  });

  it("opens the course generation overlay from the home input", async () => {
    const user = userEvent.setup();

    render(
      <MemoryRouter>
        <LearningSpacePage />
      </MemoryRouter>
    );

    await user.click(screen.getByRole("button", { name: "生成课程" }));

    const dialog = screen.getByRole("dialog", { name: "生成课程" });

    expect(dialog).toBeInTheDocument();
    expect(within(dialog).getByRole("textbox", { name: "课程名称" })).toHaveValue("人工智能导论期末复习");
    expect(within(dialog).getByText("已选择 3 份资料")).toBeInTheDocument();
  });
});

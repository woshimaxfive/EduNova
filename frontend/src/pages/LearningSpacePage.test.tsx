import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { LearningSpacePage } from "./LearningSpacePage";

describe("LearningSpacePage", () => {
  it("renders a calm ChatGPT-style learning home without dashboard rails", () => {
    render(
      <MemoryRouter>
        <LearningSpacePage />
      </MemoryRouter>
    );

    expect(screen.getByRole("heading", { name: "嗨，同学，准备好一起学习了吗？" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "历史对话" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "AI 学习入口" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "最近学习" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "学习问题输入" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "打开资料库" })).toBeInTheDocument();
    expect(screen.getByRole("list", { name: "最近学习列表" })).toBeInTheDocument();
    expect(screen.getAllByRole("listitem")).toHaveLength(3);
    expect(screen.getByRole("link", { name: /人工智能导论/ })).toHaveAttribute("href", "/app/courses/course-ai");
    expect(screen.queryByRole("region", { name: "资料库轻入口" })).not.toBeInTheDocument();
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

import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it } from "vitest";

import { useAuthStore } from "../features/auth/authStore";
import { LearningSpacePage } from "./LearningSpacePage";

describe("LearningSpacePage", () => {
  beforeEach(() => {
    localStorage.clear();
    useAuthStore.getState().clearSession();
  });

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

    const dialog = screen.getByRole("dialog", { name: "从资料生成课程" });

    expect(dialog).toBeInTheDocument();
    expect(within(dialog).getByRole("textbox", { name: "课程名称" })).toHaveValue("人工智能导论期末复习");
    expect(within(dialog).getByRole("button", { name: /人工智能导论课件/ })).toHaveAttribute("aria-pressed", "false");
    expect(within(dialog).getByText("先选择要生成课程的资料")).toBeInTheDocument();
  });

  it("keeps the edge rail focused on chat history and account actions", () => {
    render(
      <MemoryRouter>
        <LearningSpacePage />
      </MemoryRouter>
    );

    const historyRail = screen.getByRole("region", { name: "历史对话" });

    expect(within(historyRail).queryByRole("link", { name: /学习空间/ })).not.toBeInTheDocument();
    expect(within(historyRail).getByRole("link", { name: "资料库" })).toHaveAttribute("href", "/app/library");
    expect(within(historyRail).getByRole("link", { name: "资源工坊" })).toHaveAttribute("href", "/app/studio");
    expect(within(historyRail).getByRole("link", { name: "个人资料" })).toHaveAttribute("href", "/app/profile");
    expect(within(historyRail).getByRole("link", { name: "设置" })).toHaveAttribute("href", "/app/settings");
    expect(within(historyRail).getByRole("button", { name: "退出登录" })).toBeInTheDocument();
  });

  it("collapses the edge history sidebar without leaving the learning home", async () => {
    const user = userEvent.setup();

    render(
      <MemoryRouter>
        <LearningSpacePage />
      </MemoryRouter>
    );

    const historyRail = screen.getByRole("region", { name: "历史对话" });

    expect(historyRail).toHaveAttribute("data-collapsed", "false");

    await user.click(screen.getByRole("button", { name: "收起侧栏" }));

    expect(historyRail).toHaveAttribute("data-collapsed", "true");
    expect(screen.getByRole("button", { name: "展开侧栏" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "AI 学习入口" })).toBeInTheDocument();
  });

  it("moves into a chat thread after the first home question", async () => {
    const user = userEvent.setup();

    render(
      <MemoryRouter>
        <LearningSpacePage />
      </MemoryRouter>
    );

    await user.type(screen.getByRole("textbox", { name: "学习问题输入" }), "期末复习怎么安排？");
    await user.click(screen.getByRole("button", { name: "发送" }));

    const thread = screen.getByRole("region", { name: "主页对话" });

    expect(within(thread).getByText("期末复习怎么安排？")).toBeInTheDocument();
    expect(within(thread).getByText(/可以先把资料按章节和题型拆开/)).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "底部学习输入" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "嗨，同学，准备好一起学习了吗？" })).not.toBeInTheDocument();
  });

  it("keeps blank starter accounts empty until they upload their own material", async () => {
    const user = userEvent.setup();

    useAuthStore.getState().setSession({
      token: "blank-token",
      user: {
        id: 3,
        email: "blank@edunova.local",
        displayName: "空白学习者",
        role: "student",
        starterMode: "blank"
      }
    });

    render(
      <MemoryRouter>
        <LearningSpacePage />
      </MemoryRouter>
    );

    expect(screen.getByText("还没有课程")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /人工智能导论/ })).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "打开资料库" }));

    expect(screen.getByRole("dialog", { name: "资料库" })).toHaveTextContent("资料库还是空的");
  });

  it("sends with Enter and keeps Shift Enter as a line break", async () => {
    const user = userEvent.setup();

    render(
      <MemoryRouter>
        <LearningSpacePage />
      </MemoryRouter>
    );

    const input = screen.getByRole("textbox", { name: "学习问题输入" });

    await user.type(input, "第一行{Shift>}{Enter}{/Shift}第二行");

    expect(input).toHaveValue("第一行\n第二行");

    await user.keyboard("{Enter}");

    expect(screen.getByRole("region", { name: "主页对话" })).toHaveTextContent("第一行 第二行");
    expect(input).toHaveValue("");
  });
});

import { render, screen, within } from "@testing-library/react";
import { type ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { LibraryPage } from "./LibraryPage";
import { PracticePage } from "./PracticePage";
import { ProfilePage } from "./ProfilePage";
import { ReportsPage } from "./ReportsPage";
import { SettingsPage } from "./SettingsPage";
import { StudioPage } from "./StudioPage";
import { TutorPage } from "./TutorPage";

function renderPage(page: ReactNode) {
  render(<MemoryRouter>{page}</MemoryRouter>);
}

function renderRoutePage(page: ReactNode, path: string) {
  render(<MemoryRouter initialEntries={[path]}>{page}</MemoryRouter>);
}

describe("student core pages", () => {
  it("renders the material library as a source workspace", () => {
    renderPage(<LibraryPage />);

    expect(screen.getByRole("region", { name: "历史对话" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "资料库" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "文件库" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "搜索资料" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "上传资料" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "生成课程" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "文档" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "图片" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "课程内置" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /AI 导论讲义/ })).toBeInTheDocument();
  });

  it("renders studio as a generated-resource workspace", () => {
    renderPage(<StudioPage />);

    expect(screen.getByRole("heading", { name: "资源工坊" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "资源生成工作台" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "生成队列" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "资源生成区" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "代码实操" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "复盘报告" })).not.toBeInTheDocument();
  });

  it("renders the learning profile workspace", () => {
    renderPage(<ProfilePage />);

    expect(screen.getByRole("heading", { name: "学习画像" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "学习画像" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "画像证据" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "画像对话入口" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "更新目标" })).toBeInTheDocument();
  });

  it("renders the AI tutor workspace with citations and mode controls", () => {
    renderPage(<TutorPage />);

    expect(screen.getByRole("heading", { name: "AI 辅导" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "AI 辅导对话" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "引用来源" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "辅导模式" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "追问输入" })).toBeInTheDocument();
  });

  it("renders practice as an answer, feedback, and review loop", () => {
    renderPage(<PracticePage />);

    expect(screen.getByRole("heading", { name: "练习" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "练习作答" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "批改反馈" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "薄弱点复习队列" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "提交答案" })).toBeInTheDocument();
  });

  it("renders reports as an explainable learning record", () => {
    renderPage(<ReportsPage />);

    expect(screen.getByRole("heading", { name: "学习报告" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "掌握度地图" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "学习报告" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "导出学习档案" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "导出档案" })).toBeInTheDocument();
  });

  it("renders settings with model, privacy, and account boundaries", () => {
    renderPage(<SettingsPage />);

    expect(screen.getByRole("heading", { name: "设置" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "模型设置" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "隐私与数据" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "账号设置" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "保存设置" })).toBeInTheDocument();
  });

  it("keeps secondary routes inside the same edge workspace shell as the home page", () => {
    renderRoutePage(<SettingsPage />, "/app/settings");

    const historyRail = screen.getByRole("region", { name: "历史对话" });

    expect(within(historyRail).getByRole("link", { name: "资料库" })).toHaveAttribute("href", "/app/library");
    expect(within(historyRail).getByRole("link", { name: "个人资料" })).toHaveAttribute("href", "/app/profile");
    expect(within(historyRail).getByRole("link", { name: "设置" })).toHaveAttribute("href", "/app/settings");
    expect(within(historyRail).getByRole("link", { name: "设置" })).toHaveAttribute("aria-current", "page");
    expect(within(historyRail).getByRole("button", { name: /神经网络反向传播怎么复习/ })).toBeInTheDocument();
    expect(within(historyRail).queryByText("还没有历史对话")).not.toBeInTheDocument();
    expect(screen.queryByRole("navigation", { name: "应用导航" })).not.toBeInTheDocument();
  });
});

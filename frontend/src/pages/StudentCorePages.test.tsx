import { render, screen } from "@testing-library/react";
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

describe("student core pages", () => {
  it("renders the material library as a source workspace", () => {
    renderPage(<LibraryPage />);

    expect(screen.getByRole("heading", { name: "课程资料进入学习空间" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "资料列表" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "资料操作" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "课程归属" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "上传资料" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "生成课程" })).toBeInTheDocument();
  });

  it("renders studio as a generated-resource workspace", () => {
    renderPage(<StudioPage />);

    expect(screen.getByRole("heading", { name: "把知识点生成可学习资源" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "资源生成工作台" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "生成队列" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Studio 生成区" })).toBeInTheDocument();
  });

  it("renders the learning profile workspace", () => {
    renderPage(<ProfilePage />);

    expect(screen.getByRole("heading", { name: "用聊天建立学习画像" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "学习画像" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "画像证据" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "画像对话入口" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "更新目标" })).toBeInTheDocument();
  });

  it("renders the AI tutor workspace with citations and mode controls", () => {
    renderPage(<TutorPage />);

    expect(screen.getByRole("heading", { name: "围绕课程资料追问" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "AI 辅导对话" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "引用来源" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "辅导模式" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "追问输入" })).toBeInTheDocument();
  });

  it("renders practice as an answer, feedback, and review loop", () => {
    renderPage(<PracticePage />);

    expect(screen.getByRole("heading", { name: "用题目反推薄弱点" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "练习作答" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "批改反馈" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "薄弱点复习队列" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "提交答案" })).toBeInTheDocument();
  });

  it("renders reports as an explainable learning record", () => {
    renderPage(<ReportsPage />);

    expect(screen.getByRole("heading", { name: "让推荐原因可解释" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "掌握度地图" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "学习报告" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "导出学习档案" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "导出档案" })).toBeInTheDocument();
  });

  it("renders settings with model, privacy, and account boundaries", () => {
    renderPage(<SettingsPage />);

    expect(screen.getByRole("heading", { name: "轻量系统设置" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "模型设置" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "隐私与数据" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "账号设置" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "保存设置" })).toBeInTheDocument();
  });
});

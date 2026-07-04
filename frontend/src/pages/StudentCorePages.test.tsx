import { render, screen, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { type ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { buildCoursePath } from "../app/routePaths";
import { apiClient } from "../api/client";
import { COURSE_ENDPOINTS, type ApiCourseSummary } from "../api/courses";
import { MATERIAL_ENDPOINTS, type MaterialListItem } from "../api/materials";
import { LibraryPage } from "./LibraryPage";
import { PracticePage } from "./PracticePage";
import { ProfilePage } from "./ProfilePage";
import { ReportsPage } from "./ReportsPage";
import { SettingsPage } from "./SettingsPage";
import { StudioPage } from "./StudioPage";
import { TutorPage } from "./TutorPage";

let previousAdapter = apiClient.defaults.adapter;
let tutorCourses: ApiCourseSummary[] = [];

function renderWithProviders(ui: ReactNode) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false
      }
    }
  });

  render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

function renderPage(page: ReactNode) {
  renderWithProviders(<MemoryRouter>{page}</MemoryRouter>);
}

function renderRoutePage(page: ReactNode, path: string) {
  renderWithProviders(<MemoryRouter initialEntries={[path]}>{page}</MemoryRouter>);
}

describe("student core pages", () => {
  beforeEach(() => {
    previousAdapter = apiClient.defaults.adapter;
    tutorCourses = [
      {
        id: "808",
        title: "AI 搜索复习",
        description: "由 1 份资料生成",
        subject: "自主学习",
        source_type: "uploaded",
        status: "ready",
        progress_percent: 0,
        material_count: 1,
        knowledge_point_count: 2,
        chunk_count: 3
      }
    ];
    apiClient.defaults.adapter = async (config) => {
      if (config.url === MATERIAL_ENDPOINTS.list) {
        const materials: MaterialListItem[] = [
          {
            id: "301",
            title: "AI 导论讲义",
            type: "DOCX",
            detail: "12 个知识点",
            modified: "今天",
            size: "1.2 MB",
            category: "document",
            extension: "DOCX",
            parse_status: "completed",
            course_ids: ["101"]
          }
        ];

        return {
          data: { data: materials, trace_id: "trace_core_materials" },
          status: 200,
          statusText: "OK",
          headers: {},
          config
        };
      }

      if (config.url === COURSE_ENDPOINTS.list) {
        return {
          data: { data: tutorCourses, trace_id: "trace_core_courses" },
          status: 200,
          statusText: "OK",
          headers: {},
          config
        };
      }

      return {
        data: { data: {}, trace_id: "trace_core_default" },
        status: 200,
        statusText: "OK",
        headers: {},
        config
      };
    };
  });

  afterEach(() => {
    apiClient.defaults.adapter = previousAdapter;
  });

  it("renders the material library as a source workspace", async () => {
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
    expect(await screen.findByRole("button", { name: /AI 导论讲义/ })).toBeInTheDocument();
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

  it("renders the AI tutor route as a course selector instead of a static demo chat", async () => {
    renderPage(<TutorPage />);

    expect(screen.getByRole("heading", { name: "AI 辅导" })).toBeInTheDocument();
    expect(await screen.findByRole("region", { name: "课程辅导入口" })).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: /AI 搜索复习/ })).toHaveAttribute("href", buildCoursePath("808"));
    expect(screen.queryByText("为什么反向传播需要链式法则？")).not.toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "引用来源" })).not.toBeInTheDocument();
    expect(screen.queryByRole("textbox", { name: "追问输入" })).not.toBeInTheDocument();
  });

  it("guides the student to upload materials when AI tutor has no courses", async () => {
    tutorCourses = [];

    renderPage(<TutorPage />);

    expect(await screen.findByText("还没有可辅导的课程")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "去资料库上传资料" })).toHaveAttribute("href", "/app/library");
    expect(screen.getByRole("link", { name: "回到学习主页" })).toHaveAttribute("href", "/app");
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
    expect(screen.getByRole("combobox", { name: "Provider 预设" })).toBeInTheDocument();
    expect(screen.getByText("讯飞星火 Spark")).toBeInTheDocument();
    expect(screen.queryByText("深度思考")).not.toBeInTheDocument();
    expect(screen.queryByText("联网搜索")).not.toBeInTheDocument();
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

import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { apiClient } from "../api/client";
import { type DashboardSummary } from "../api/dashboard";
import { AppRoutes } from "./routes";
import { useAuthStore } from "../features/auth/authStore";

const dashboardSummary: DashboardSummary = {
  profile_summary: {
    display_name: "演示学生",
    starter_mode: "data_structures",
    has_profile: false,
    knowledge_foundation: null,
    learning_goal: null
  },
  recent_conversations: [],
  recent_courses: [
    {
      id: "101",
      title: "人工智能导论",
      source_type: "builtin",
      progress_label: "未开始",
      focus: "人工智能",
      next: "开始学习"
    }
  ],
  material_library_summary: {
    material_count: 1,
    unassigned_count: 0
  },
  recent_materials: [],
  recent_resources: [],
  command_suggestions: ["帮我复习人工智能导论"],
  evidence_summary: {
    citation_count: 0,
    latest_trace_id: null,
    low_evidence_count: 0
  },
  empty_state: {
    kind: "starter",
    title: "从人工智能导论开始",
    description: "内置课程已经进入你的个人空间，可以直接开始学习。",
    action_label: "开始学习"
  }
};

let previousAdapter = apiClient.defaults.adapter;

function renderRoutes(initialEntries: string[]) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false
      }
    }
  });

  apiClient.defaults.adapter = async (config) => ({
    data: {
      data: dashboardSummary,
      trace_id: "trace_routes_test"
    },
    status: 200,
    statusText: "OK",
    headers: {},
    config
  });

  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={initialEntries}>
        <AppRoutes />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("EduNova routes", () => {
  beforeEach(() => {
    previousAdapter = apiClient.defaults.adapter;
    localStorage.clear();
    useAuthStore.getState().clearSession();
  });

  afterEach(() => {
    apiClient.defaults.adapter = previousAdapter;
    localStorage.clear();
  });

  it("redirects unauthenticated app routes to the calm login entry", async () => {
    renderRoutes(["/app/studio"]);

    expect(await screen.findByRole("heading", { name: "登录" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /演示学生/ })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "创建账号" })).toHaveAttribute("href", "/register");
  });

  it("redirects authenticated students away from public entry pages", async () => {
    useAuthStore.getState().setSession({
      token: "demo-token",
      user: {
        id: 1,
        account: "demo",
        displayName: "演示学生",
        role: "student"
      }
    });

    renderRoutes(["/login"]);

    expect(await screen.findByRole("heading", { name: "嗨，同学，准备好一起学习了吗？" })).toBeInTheDocument();
  });

  it("renders the protected course shell without demo fallback for an invalid course id", async () => {
    useAuthStore.getState().setSession({
      token: "demo-token",
      user: {
        id: 1,
        account: "demo",
        displayName: "演示学生",
        role: "student"
      }
    });

    renderRoutes(["/app/courses/course-ai"]);

    expect(await screen.findByRole("heading", { name: "课程暂不可用" }, { timeout: 5_000 })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "人工智能导论" })).not.toBeInTheDocument();
    expect(screen.getByRole("region", { name: "课程对话空间" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "问答" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "课程内容" })).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByRole("region", { name: "课程提问引导" })).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "知识学习画布" })).not.toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "证据与 Agent 轨迹" })).not.toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "资源生成区" })).not.toBeInTheDocument();
  });

  it("renders the protected learning path workspace for an authenticated student", async () => {
    useAuthStore.getState().setSession({
      token: "demo-token",
      user: {
        id: 1,
        account: "demo",
        displayName: "演示学生",
        role: "student"
      }
    });

    renderRoutes(["/app/path"]);

    expect(await screen.findByRole("heading", { name: "学习路径" })).toHaveClass("visually-hidden");
    expect(screen.getByText("个性化学习安排")).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "任务状态" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "生成学习路径" })).toBeInTheDocument();
    expect(screen.queryByText("期末冲刺")).not.toBeInTheDocument();
  });

  it("treats the retired design lab route as not found", async () => {
    useAuthStore.getState().setSession({
      token: "demo-token",
      user: {
        id: 1,
        account: "demo",
        displayName: "演示学生",
        role: "student"
      }
    });

    renderRoutes(["/app/design-lab"]);

    expect(await screen.findByRole("heading", { name: "没有找到这个学习入口" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "回到学习空间" })).toBeInTheDocument();
  });

  it("treats the retired demo entry as not found", async () => {
    renderRoutes(["/demo"]);

    expect(await screen.findByRole("heading", { name: "没有找到这个学习入口" })).toBeInTheDocument();
  });

  it("redirects the retired tutor entry to the authenticated home", async () => {
    useAuthStore.getState().setSession({
      token: "test-token",
      user: {
        id: 1,
        account: "student",
        displayName: "测试学生",
        role: "student"
      }
    });

    renderRoutes(["/app/tutor"]);

    expect(await screen.findByRole("heading", { name: "嗨，同学，准备好一起学习了吗？" })).toBeInTheDocument();
  });
});

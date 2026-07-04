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
    starter_mode: "ai_intro",
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

    expect(await screen.findByRole("heading", { name: "进入你的学习空间" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /演示学生/ })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "创建学生账号" })).toHaveAttribute("href", "/register");
  });

  it("redirects authenticated students away from public entry pages", async () => {
    useAuthStore.getState().setSession({
      token: "demo-token",
      user: {
        id: 1,
        email: "demo@edunova.local",
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
        email: "demo@edunova.local",
        displayName: "演示学生",
        role: "student"
      }
    });

    renderRoutes(["/app/courses/course-ai"]);

    expect(await screen.findByRole("heading", { name: "课程暂不可用" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "人工智能导论" })).not.toBeInTheDocument();
    expect(screen.getByRole("region", { name: "课程对话空间" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "问答模式" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "学习模式" })).toHaveAttribute("aria-pressed", "false");
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
        email: "demo@edunova.local",
        displayName: "演示学生",
        role: "student"
      }
    });

    renderRoutes(["/app/path"]);

    expect(await screen.findByRole("heading", { name: "学习路径" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "阶段任务" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "路径依据" })).toBeInTheDocument();
    expect(screen.getByText("下一步行动")).toBeInTheDocument();
  });

  it("treats the retired design lab route as not found", async () => {
    useAuthStore.getState().setSession({
      token: "demo-token",
      user: {
        id: 1,
        email: "demo@edunova.local",
        displayName: "演示学生",
        role: "student"
      }
    });

    renderRoutes(["/app/design-lab"]);

    expect(await screen.findByRole("heading", { name: "没有找到这个学习入口" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "回到学习空间" })).toBeInTheDocument();
  });
});

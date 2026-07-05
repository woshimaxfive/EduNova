import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { type ReactNode } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { PATHS } from "../app/routePaths";
import { apiClient } from "../api/client";
import { COURSE_ENDPOINTS } from "../api/courses";
import { PATH_ENDPOINTS } from "../api/paths";
import { LearningPathPage } from "./LearningPathPage";

let previousAdapter = apiClient.defaults.adapter;

function renderWithProviders(ui: ReactNode, initialPath = `${PATHS.path}?course_id=808`) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false
      }
    }
  });

  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialPath]}>
        <Routes>
          <Route path={PATHS.path} element={ui} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

function parsePayload(data: unknown) {
  return typeof data === "string" ? JSON.parse(data) : data;
}

const courseListResponse = {
  data: [
    {
      id: "808",
      title: "AI 搜索复习",
      description: "由 1 份资料生成",
      subject: "人工智能",
      source_type: "uploaded",
      status: "ready",
      progress_percent: 0,
      material_count: 1,
      knowledge_point_count: 3,
      chunk_count: 8
    }
  ],
  page: 1,
  page_size: 1,
  total: 1,
  trace_id: "trace_courses"
};

const activePathResponse = {
  course_id: "808",
  status: "active",
  message: "当前学习路径进行中。",
  path: {
    id: "901",
    course_id: "808",
    title: "AI 搜索复习 学习路径",
    goal: "期末前掌握搜索算法",
    status: "active",
    plan_json: {
      duration_days: 7
    },
    created_at: "2026-07-05T09:00:00Z",
    updated_at: "2026-07-05T09:00:00Z"
  },
  tasks: [
    {
      id: "1001",
      path_id: "901",
      course_id: "808",
      knowledge_point_id: "401",
      title: "复习启发式搜索",
      task_type: "review",
      reason: "来自已确认薄弱点",
      recommended_resource_ids: ["801"],
      recommended_resources: [
        {
          id: "801",
          title: "启发式搜索讲解",
          resource_type: "doc"
        }
      ],
      status: "doing",
      due_at: "2026-07-06T09:00:00Z",
      next_review_at: null,
      created_at: "2026-07-05T09:00:00Z",
      updated_at: "2026-07-05T09:00:00Z"
    }
  ],
  evidence_summary: {
    knowledge_point_count: 3,
    confirmed_or_reviewing_weakness_count: 1,
    pending_weakness_count: 0,
    resource_count: 1,
    basis: ["课程知识点 3 个。", "已确认或复习中的薄弱点 1 个。"]
  }
};

const masteryResponse = {
  course_id: "808",
  summary: {
    total_count: 3,
    weak_count: 1,
    learning_count: 1,
    mastered_count: 1,
    recommended_review_count: 0,
    not_started_count: 0
  },
  points: [
    {
      id: "401",
      title: "启发式搜索",
      chapter: "搜索问题",
      order_index: 0,
      status: "weak",
      score: 35,
      prerequisite_ids: [],
      weakness_item_ids: ["701"],
      recommended_resource_ids: ["801"]
    }
  ]
};

describe("LearningPathPage", () => {
  beforeEach(() => {
    previousAdapter = apiClient.defaults.adapter;
  });

  afterEach(() => {
    apiClient.defaults.adapter = previousAdapter;
  });

  it("renders real course path, mastery map and updates task status", async () => {
    const user = userEvent.setup();
    const calls: Array<{ method: string; url: string; payload: unknown; params: unknown }> = [];

    apiClient.defaults.adapter = async (config) => {
      const method = (config.method ?? "get").toLowerCase();
      const url = config.url ?? "";
      calls.push({ method, url, payload: parsePayload(config.data), params: config.params });

      if (url === COURSE_ENDPOINTS.list) {
        return { data: courseListResponse, status: 200, statusText: "OK", headers: {}, config };
      }
      if (url === PATH_ENDPOINTS.current) {
        return { data: { data: activePathResponse, trace_id: "trace_path" }, status: 200, statusText: "OK", headers: {}, config };
      }
      if (url === COURSE_ENDPOINTS.masteryMap(808)) {
        return { data: { data: masteryResponse, trace_id: "trace_mastery" }, status: 200, statusText: "OK", headers: {}, config };
      }
      if (url === PATH_ENDPOINTS.updateTask(1001)) {
        return {
          data: {
            data: {
              ...activePathResponse.tasks[0],
              status: "completed"
            },
            trace_id: "trace_task"
          },
          status: 200,
          statusText: "OK",
          headers: {},
          config
        };
      }

      throw new Error(`Unexpected request ${method} ${url}`);
    };

    renderWithProviders(<LearningPathPage />);

    expect(await screen.findByText("复习启发式搜索")).toBeInTheDocument();
    expect(screen.getByText("启发式搜索讲解")).toBeInTheDocument();
    const masteryRegion = screen.getByRole("region", { name: "掌握度图" });
    expect(within(masteryRegion).getByText("启发式搜索")).toBeInTheDocument();
    expect(within(masteryRegion).getByText("薄弱")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "完成 复习启发式搜索" }));

    await waitFor(() => {
      expect(calls).toContainEqual(
        expect.objectContaining({
          method: "patch",
          url: PATH_ENDPOINTS.updateTask(1001),
          payload: {
            status: "completed"
          }
        })
      );
    });
  });

  it("shows a real empty state and generates a path for the selected course", async () => {
    const user = userEvent.setup();
    let hasPath = false;
    const calls: Array<{ method: string; url: string; payload: unknown }> = [];

    apiClient.defaults.adapter = async (config) => {
      const method = (config.method ?? "get").toLowerCase();
      const url = config.url ?? "";
      const payload = parsePayload(config.data);
      calls.push({ method, url, payload });

      if (url === COURSE_ENDPOINTS.list) {
        return { data: courseListResponse, status: 200, statusText: "OK", headers: {}, config };
      }
      if (url === PATH_ENDPOINTS.current) {
        const data = hasPath
          ? activePathResponse
          : {
              course_id: "808",
              status: "not_started",
              message: "学习路径尚未生成。",
              path: null,
              tasks: [],
              evidence_summary: {
                knowledge_point_count: 3,
                confirmed_or_reviewing_weakness_count: 1,
                pending_weakness_count: 0,
                resource_count: 1,
                basis: []
              }
            };
        return { data: { data, trace_id: "trace_path" }, status: 200, statusText: "OK", headers: {}, config };
      }
      if (url === COURSE_ENDPOINTS.masteryMap(808)) {
        return { data: { data: masteryResponse, trace_id: "trace_mastery" }, status: 200, statusText: "OK", headers: {}, config };
      }
      if (url === PATH_ENDPOINTS.generate) {
        hasPath = true;
        return { data: { data: activePathResponse, trace_id: "trace_generated" }, status: 200, statusText: "OK", headers: {}, config };
      }

      throw new Error(`Unexpected request ${method} ${url}`);
    };

    renderWithProviders(<LearningPathPage />);

    expect(await screen.findByText("学习路径尚未生成。")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "生成学习路径" }));

    expect(await screen.findByText("复习启发式搜索")).toBeInTheDocument();
    expect(calls).toContainEqual(
      expect.objectContaining({
        method: "post",
        url: PATH_ENDPOINTS.generate,
        payload: {
          course_id: 808,
          duration_days: 7,
          goal: ""
        }
      })
    );
  });

  it("shows local feedback when path data fails to load", async () => {
    apiClient.defaults.adapter = async (config) => {
      if (config.url === COURSE_ENDPOINTS.list) {
        return { data: courseListResponse, status: 200, statusText: "OK", headers: {}, config };
      }
      throw new Error("path failed");
    };

    renderWithProviders(<LearningPathPage />);

    expect(await screen.findByText("学习路径数据读取失败，请稍后重试。")).toBeInTheDocument();
  });
});

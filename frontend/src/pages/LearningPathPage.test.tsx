import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { type ReactNode } from "react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { PATHS } from "../app/routePaths";
import { AGENT_ENDPOINTS } from "../api/agents";
import { apiClient } from "../api/client";
import { COURSE_ENDPOINTS } from "../api/courses";
import { EXAM_SPRINT_ENDPOINTS } from "../api/examSprint";
import { MATERIAL_ENDPOINTS } from "../api/materials";
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
          <Route path={PATHS.path} element={<>{ui}<LocationProbe /></>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

function LocationProbe() {
  const location = useLocation();
  return <output data-testid="location">{location.pathname}{location.search}</output>;
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
  message: "已根据练习结果更新学习路径。",
  agent_trace_id: "trace_path",
  path: {
    id: "901",
    course_id: "808",
    title: "AI 搜索复习 学习路径",
    goal: "期末前掌握搜索算法",
    status: "active",
    plan_json: {
      duration_days: 7,
      trigger: "assessment",
      preserved_task_count: 2,
      generation_mode: "model_enhanced",
      review_mode: "model_and_rules"
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

const sprintPlanResponse = {
  id: "3001",
  course_id: "808",
  agent_trace_id: "trace_sprint",
  comparison_id: "1201",
  trigger: "manual",
  generation_mode: "deterministic_source",
  review_mode: "rules_only",
  preserved_task_count: 0,
  warnings: [],
  duration_days: 7,
  goal: "期末冲刺",
  status: "sprint_active",
  high_frequency_points: [
    {
      knowledge_point_id: "401",
      title: "启发式搜索",
      reason: "来自练习低分或错题",
      score: 120,
      recommended_resource_ids: ["801"],
      recommended_resources: [
        {
          id: "801",
          title: "启发式搜索讲解",
          resource_type: "doc",
          knowledge_point_id: "401"
        }
      ]
    }
  ],
  weak_points: [
    {
      knowledge_point_id: "401",
      title: "启发式搜索",
      reason: "来自已确认或复习中的弱点队列",
      score: 130,
      recommended_resource_ids: ["801"],
      recommended_resources: [
        {
          id: "801",
          title: "启发式搜索讲解",
          resource_type: "doc",
          knowledge_point_id: "401"
        }
      ]
    }
  ],
  daily_tasks: [
    {
      id: "4001",
      day_index: 1,
      title: "第 1 天复习启发式搜索",
      task_type: "sprint_review",
      status: "doing",
      due_at: "2026-07-05T11:00:00Z",
      knowledge_point_id: "401",
      reason: "期末冲刺优先处理薄弱点和高频知识点。",
      recommended_resource_ids: ["801"],
      recommended_resources: [
        {
          id: "801",
          title: "启发式搜索讲解",
          resource_type: "doc",
          knowledge_point_id: "401"
        }
      ]
    },
    {
      id: "4002",
      day_index: 1,
      title: "完成启发式搜索必刷题",
      task_type: "sprint_practice",
      status: "todo",
      due_at: "2026-07-05T11:00:00Z",
      knowledge_point_id: "401",
      reason: "用练习检查复习结果。",
      recommended_resource_ids: [],
      recommended_resources: []
    }
  ],
  must_do_questions: [
    {
      id: "sprint-q1",
      knowledge_point_id: "401",
      title: "启发式搜索",
      question_type: "short_answer",
      prompt: "用课程证据解释启发式搜索的核心概念、常见误区和解题步骤。",
      reason: "来自弱点、练习低分或高频知识点。"
    }
  ],
  easy_mistake_warnings: [
    {
      knowledge_point_id: "401",
      title: "启发式搜索",
      warning: "启发式搜索：先复述概念边界，再做题；错题要标出依据缺口。"
    }
  ],
  recommended_resources: [
    {
      id: "801",
      title: "启发式搜索讲解",
      resource_type: "doc",
      knowledge_point_id: "401"
    }
  ],
  evidence_summary: {
    knowledge_point_count: 3,
    weakness_count: 1,
    practice_low_score_count: 1,
    resource_count: 1,
    report_suggestion_count: 1,
    material_filter_count: 0,
    basis: ["课程知识点 3 个。"]
  },
  created_at: "2026-07-05T11:00:00Z",
  updated_at: "2026-07-05T11:00:00Z"
};

describe("LearningPathPage", () => {
  beforeEach(() => {
    previousAdapter = apiClient.defaults.adapter;
  });

  afterEach(() => {
    apiClient.defaults.adapter = previousAdapter;
  });

  it("renders the path workspace, filters tasks, opens details and updates the current task", async () => {
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
      if (url === AGENT_ENDPOINTS.trace("trace_path")) {
        return {
          data: {
            data: {
              trace_id: "trace_path",
              workflow: "path_planning",
              artifact_type: "learning_path",
              artifact_id: "901",
              course_id: "808",
              status: "completed",
              steps: [
                {
                  id: "1",
                  agent_name: "deterministic_rank",
                  step_index: 2,
                  status: "completed",
                  input_summary: "整理弱点与既有进度",
                  output_summary: "已保留进度并重排任务",
                  duration_ms: 9,
                  metadata: { preserved_task_count: 2 },
                  created_at: "2026-07-05T09:00:01Z"
                }
              ]
            },
            trace_id: "trace_api"
          },
          status: 200,
          statusText: "OK",
          headers: {},
          config
        };
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
    expect(screen.getByText("由练习结果更新 · 保留 2 个既有任务")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "个性化路径" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("navigation", { name: "任务状态" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "路径详情" }));
    const drawer = screen.getByRole("dialog", { name: "路径详情" });
    expect(screen.getByTestId("path-drawer-layer").closest(".page-workbench")).toBeNull();
    expect(within(drawer).getByText("启发式搜索")).toBeInTheDocument();
    expect(within(drawer).getByText("薄弱 · 35")).toBeInTheDocument();
    await user.click(within(drawer).getByRole("tab", { name: "规划依据" }));
    expect(within(drawer).getByText("模型增强 · 模型与规则审核")).toBeInTheDocument();
    expect(within(drawer).getByText("课程知识点 3 个。")).toBeInTheDocument();
    await user.click(within(drawer).getByRole("tab", { name: "协作轨迹" }));
    await user.click(within(drawer).getByRole("button", { name: "查看 PathPlanningGraph" }));
    expect(await screen.findByText("deterministic_rank")).toBeInTheDocument();
    await user.click(within(drawer).getByRole("button", { name: "关闭" }));

    await user.click(screen.getByRole("button", { name: "标记完成" }));

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

  it("opens generation settings from the empty state and creates a path", async () => {
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

    expect(await screen.findByText("还没有个性化学习路径")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "生成学习路径" }));
    const drawer = screen.getByRole("dialog", { name: "学习路径生成设置" });
    await user.selectOptions(within(drawer).getByLabelText("学习周期"), "7");
    await user.click(within(drawer).getByRole("button", { name: "生成学习路径" }));

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

  it("switches to sprint mode, generates a plan and preserves the normal path", async () => {
    const user = userEvent.setup();
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
        return { data: { data: activePathResponse, trace_id: "trace_path" }, status: 200, statusText: "OK", headers: {}, config };
      }
      if (url === COURSE_ENDPOINTS.masteryMap(808)) {
        return { data: { data: masteryResponse, trace_id: "trace_mastery" }, status: 200, statusText: "OK", headers: {}, config };
      }
      if (url === EXAM_SPRINT_ENDPOINTS.current) {
        return { data: { data: null }, status: 200, statusText: "OK", headers: {}, config };
      }
      if (url === EXAM_SPRINT_ENDPOINTS.generate) {
        return { data: { data: sprintPlanResponse, trace_id: "trace_sprint" }, status: 200, statusText: "OK", headers: {}, config };
      }

      throw new Error(`Unexpected request ${method} ${url}`);
    };

    renderWithProviders(<LearningPathPage />);

    expect(await screen.findByText("复习启发式搜索")).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "期末冲刺" }));
    expect(screen.getByTestId("location")).toHaveTextContent("view=sprint");
    expect(await screen.findByText("还没有期末冲刺计划")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "生成冲刺计划" }));
    const drawer = screen.getByRole("dialog", { name: "期末冲刺生成设置" });
    await user.selectOptions(within(drawer).getByLabelText("冲刺天数"), "3");
    await user.click(within(drawer).getByRole("button", { name: "生成期末冲刺计划" }));

    expect(await screen.findByText("第 1 天复习启发式搜索")).toBeInTheDocument();
    expect(screen.getByText("启发式搜索讲解")).toBeInTheDocument();
    expect(screen.queryByText("复习启发式搜索")).not.toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "个性化路径" }));
    expect(await screen.findByText("复习启发式搜索")).toBeInTheDocument();
    expect(calls).toContainEqual(
      expect.objectContaining({
        method: "post",
        url: EXAM_SPRINT_ENDPOINTS.generate,
        payload: {
          course_id: 808,
          duration_days: 3,
          material_ids: [],
          goal: ""
        }
      })
    );
  });

  it("keeps sprint generation settings after a local failure", async () => {
    const user = userEvent.setup();

    apiClient.defaults.adapter = async (config) => {
      if (config.url === COURSE_ENDPOINTS.list) {
        return { data: courseListResponse, status: 200, statusText: "OK", headers: {}, config };
      }
      if (config.url === PATH_ENDPOINTS.current) {
        return { data: { data: activePathResponse, trace_id: "trace_path" }, status: 200, statusText: "OK", headers: {}, config };
      }
      if (config.url === COURSE_ENDPOINTS.masteryMap(808)) {
        return { data: { data: masteryResponse, trace_id: "trace_mastery" }, status: 200, statusText: "OK", headers: {}, config };
      }
      if (config.url === EXAM_SPRINT_ENDPOINTS.current) {
        return { data: { data: null }, status: 200, statusText: "OK", headers: {}, config };
      }
      if (config.url === EXAM_SPRINT_ENDPOINTS.generate) {
        throw new Error("sprint failed");
      }
      throw new Error(`Unexpected request ${config.url}`);
    };

    renderWithProviders(<LearningPathPage />);

    expect(await screen.findByText("复习启发式搜索")).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "期末冲刺" }));
    await user.click(await screen.findByRole("button", { name: "生成冲刺计划" }));
    const drawer = screen.getByRole("dialog", { name: "期末冲刺生成设置" });
    await user.type(within(drawer).getByPlaceholderText("例如：优先突破高频考点与错题"), "突破启发式搜索");
    await user.click(within(drawer).getByRole("button", { name: "生成期末冲刺计划" }));

    expect(await within(drawer).findByText("期末冲刺计划生成失败，请稍后重试。")).toBeInTheDocument();
    expect(within(drawer).getByDisplayValue("突破启发式搜索")).toBeInTheDocument();
  });

  it("uses an explicit material comparison, restores sprint and links targeted practice", async () => {
    const comparison = {
      id: "1201",
      course_id: "808",
      material_ids: ["201", "202"],
      agent_trace_id: "trace_comparison",
      summary: {
        compared_material_count: 2,
        comparable_material_count: 2,
        matched_concept_count: 3,
        citation_count: 4,
        message: "资料对比完成。"
      },
      repeated_concepts: [],
      exam_likely_points: [],
      materials_only_points: [],
      questions_only_points: [],
      missing_review_points: [],
      priority_order: [],
      citations: []
    };

    apiClient.defaults.adapter = async (config) => {
      const url = config.url ?? "";
      if (url === COURSE_ENDPOINTS.list) {
        return { data: courseListResponse, status: 200, statusText: "OK", headers: {}, config };
      }
      if (url === PATH_ENDPOINTS.current) {
        return { data: { data: activePathResponse }, status: 200, statusText: "OK", headers: {}, config };
      }
      if (url === COURSE_ENDPOINTS.masteryMap(808)) {
        return { data: { data: masteryResponse }, status: 200, statusText: "OK", headers: {}, config };
      }
      if (url === MATERIAL_ENDPOINTS.comparisonDetail(1201)) {
        return { data: { data: comparison }, status: 200, statusText: "OK", headers: {}, config };
      }
      if (url === EXAM_SPRINT_ENDPOINTS.current) {
        return { data: { data: sprintPlanResponse }, status: 200, statusText: "OK", headers: {}, config };
      }
      throw new Error(`Unexpected request ${url}`);
    };

    renderWithProviders(<LearningPathPage />, `${PATHS.path}?course_id=808&comparison_id=1201&sprint_plan_id=3001`);

    expect(await screen.findByText("资料对比 #1201")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "期末冲刺" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByTestId("location")).toHaveTextContent("comparison_id=1201");
    expect(screen.getByTestId("location")).toHaveTextContent("sprint_plan_id=3001");
    expect(screen.getByText("完成启发式搜索必刷题")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "开始针对性练习" })).toHaveAttribute(
      "href",
      "/app/practice?course_id=808&knowledge_point_id=401&sprint_plan_id=3001&sprint_task_id=4002&new=1"
    );
    await userEvent.setup().click(screen.getByRole("button", { name: "路径详情" }));
    const drawer = screen.getByRole("dialog", { name: "路径详情" });
    await userEvent.setup().click(within(drawer).getByRole("tab", { name: "协作轨迹" }));
    expect(within(drawer).getByRole("button", { name: "查看 ExamSprintGraph" })).toBeInTheDocument();
  });
});

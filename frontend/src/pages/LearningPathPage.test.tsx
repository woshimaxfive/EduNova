import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { type ReactNode } from "react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { AGENT_ENDPOINTS } from "../api/agents";
import { AI_JOB_ENDPOINTS } from "../api/aiJobs";
import { apiClient } from "../api/client";
import { COURSE_ENDPOINTS } from "../api/courses";
import { PATH_ENDPOINTS } from "../api/paths";
import { PATHS } from "../app/routePaths";
import { LearningPathPage } from "./LearningPathPage";

let previousAdapter = apiClient.defaults.adapter;

function renderWithProviders(ui: ReactNode, initialPath = `${PATHS.path}?course_id=808`) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialPath]}>
        <Routes>
          <Route path={PATHS.path} element={<>{ui}<LocationProbe /></>} />
          <Route path={PATHS.coursePath} element={<>{ui}<LocationProbe /></>} />
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
  data: [{
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
  }],
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
    goal: "掌握搜索算法",
    status: "active",
    plan_json: {
      schema_version: 4,
      path_mode: "ordered",
      trigger: "assessment",
      preserved_task_count: 2,
      generation_mode: "model_generated",
      review_mode: "model_and_rules"
    },
    personalization: {
      status: "stale",
      profile_applied_version: 2,
      current_profile_applied_version: 3,
      reason: "学习画像已变化"
    },
    created_at: "2026-07-05T09:00:00Z",
    updated_at: "2026-07-05T09:00:00Z"
  },
  tasks: [{
    id: "1001",
    path_id: "901",
    course_id: "808",
    knowledge_point_id: "401",
    title: "复习启发式搜索",
    task_type: "review",
    reason: "来自已确认薄弱点",
    recommended_resource_ids: ["801"],
    recommended_resources: [{ id: "801", title: "启发式搜索讲解", resource_type: "doc" }],
    learning_bundle: {
      strategy: "先讲解再练习",
      teaching_strategy: "worked_example",
      difficulty: "medium",
      used_profile_factor_codes: ["confirmed_weaknesses"],
      generation_mode: "model_generated",
      rationale: "先补齐概念，再用导图建立联系。",
      ready_count: 1,
      completed_count: 0,
      items: [
        { resource_type: "doc", role: "概念讲解", resource_id: "801", status: "ready", learning_status: "not_started" },
        { resource_type: "mindmap", role: "结构梳理", resource_id: null, status: "recommended", learning_status: "not_started" }
      ]
    },
    status: "doing",
    created_at: "2026-07-05T09:00:00Z",
    updated_at: "2026-07-05T09:00:00Z"
  }],
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
  summary: { total_count: 1, weak_count: 1, learning_count: 0, mastered_count: 0, recommended_review_count: 0, not_started_count: 0 },
  points: [{
    id: "401",
    title: "启发式搜索",
    chapter: "搜索问题",
    order_index: 0,
    status: "weak",
    score: 35,
    prerequisite_ids: [],
    weakness_item_ids: ["701"],
    recommended_resource_ids: ["801"]
  }]
};

function installBaseAdapter(options: {
  empty?: boolean;
  pathResponse?: typeof activePathResponse;
  calls?: Array<{ method: string; url: string; payload: unknown }>;
} = {}) {
  const hasPath = !options.empty;
  apiClient.defaults.adapter = async (config) => {
    const method = (config.method ?? "get").toLowerCase();
    const url = config.url ?? "";
    const payload = parsePayload(config.data);
    options.calls?.push({ method, url, payload });
    if (url === COURSE_ENDPOINTS.list) return { data: courseListResponse, status: 200, statusText: "OK", headers: {}, config };
    if (url === PATH_ENDPOINTS.current) {
      const data = !hasPath
        ? { course_id: "808", status: "not_started", message: "学习路径尚未生成。", path: null, tasks: [], evidence_summary: { knowledge_point_count: 3, confirmed_or_reviewing_weakness_count: 1, pending_weakness_count: 0, resource_count: 1, basis: [] } }
        : options.pathResponse ?? activePathResponse;
      return { data: { data }, status: 200, statusText: "OK", headers: {}, config };
    }
    if (url === COURSE_ENDPOINTS.masteryMap(808)) return { data: { data: masteryResponse }, status: 200, statusText: "OK", headers: {}, config };
    if (url === AI_JOB_ENDPOINTS.pathPlanning) {
      return {
        data: { data: {
          job_id: "path-job-1", workflow: "path_planning", status: "queued", course_id: "808",
          retry_of_job_id: null, progress_percent: 0, stage: "queued", label: "学习路径规划已排队", steps: [],
          agent_trace_id: "trace_path_job", request: { course_id: 808 }, result: {}, warnings: [], error_code: null,
          error_message: null, attempt_count: 0, can_cancel: true, can_retry: false,
          created_at: "2026-07-15T10:00:00Z", updated_at: "2026-07-15T10:00:00Z", started_at: null, completed_at: null
        } },
        status: 202, statusText: "Accepted", headers: {}, config
      };
    }
    if (url === PATH_ENDPOINTS.taskResourceJobs(1001)) {
      return {
        data: { data: {
          job_id: "resource-job-1", workflow: "resource_generation", status: "queued", course_id: "808",
          retry_of_job_id: null, progress_percent: 0, stage: "queued", label: "本节资源生成已排队", steps: [],
          agent_trace_id: "trace_resource_job", request: { course_id: 808, path_task_id: 1001, resource_types: ["mindmap"] },
          result: {}, warnings: [], error_code: null, error_message: null, attempt_count: 0, can_cancel: true,
          can_retry: false, created_at: "2026-07-15T10:00:00Z", updated_at: "2026-07-15T10:00:00Z",
          started_at: null, completed_at: null
        } },
        status: 202, statusText: "Accepted", headers: {}, config
      };
    }
    if (url === PATH_ENDPOINTS.updateTask(1001)) return { data: { data: { ...activePathResponse.tasks[0], status: "completed" } }, status: 200, statusText: "OK", headers: {}, config };
    if (url === AGENT_ENDPOINTS.trace("trace_path")) {
      return {
        data: { data: { trace_id: "trace_path", workflow: "path_planning", artifact_type: "learning_path", artifact_id: "901", course_id: "808", status: "completed", steps: [{ id: "1", agent_name: "deterministic_rank", step_index: 3, status: "completed", input_summary: "整理弱点与进度", output_summary: "任务已排序", duration_ms: 9, metadata: { preserved_task_count: 2 }, created_at: "2026-07-05T09:00:01Z" }] } },
        status: 200,
        statusText: "OK",
        headers: {},
        config
      };
    }
    throw new Error(`Unexpected request ${method} ${url}`);
  };
}

describe("LearningPathPage", () => {
  beforeEach(() => {
    previousAdapter = apiClient.defaults.adapter;
  });

  afterEach(() => {
    apiClient.defaults.adapter = previousAdapter;
  });

  it("renders one continuous path workspace, opens details and updates the current task", async () => {
    const user = userEvent.setup();
    const calls: Array<{ method: string; url: string; payload: unknown }> = [];
    installBaseAdapter({ calls });
    renderWithProviders(<LearningPathPage />);

    expect(await screen.findByText("复习启发式搜索")).toBeInTheDocument();
    expect(screen.getByText("个性化学习安排")).toBeInTheDocument();
    expect(screen.queryByText("期末冲刺")).not.toBeInTheDocument();
    expect(screen.getByText("个性化规划 · 难度 适中")).toBeInTheDocument();
    expect(screen.getByText("AI 当前推荐")).toBeInTheDocument();
    expect(screen.getByText("讲解文档")).toBeInTheDocument();
    expect(screen.getByText("思维导图")).toBeInTheDocument();
    expect(screen.getByText(/当前安排 1 项任务；优先处理 1 个已确认薄弱点；规划 2 项学习资源，其中 1 项已就绪/)).toBeInTheDocument();
    expect(document.querySelector(".path-task-list")).toHaveClass("connected");
    expect(screen.queryByText(/安全默认组合/)).not.toBeInTheDocument();
    expect(screen.getByText("由练习结果更新 · 保留 2 个既有任务")).toBeInTheDocument();
    expect(screen.getByText("学习画像已变化，可更新学习路径以应用新的安排依据。")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /进行中/ }));
    expect(document.querySelector(".path-task-list")).not.toHaveClass("connected");
    await user.click(screen.getByRole("button", { name: /全部任务/ }));

    await user.click(screen.getByRole("button", { name: "路径详情" }));
    const drawer = screen.getByRole("dialog", { name: "路径详情" });
    expect(within(drawer).getByText("薄弱 · 35 分")).toBeInTheDocument();
    await user.click(within(drawer).getByRole("tab", { name: "规划依据" }));
    expect(within(drawer).getByText("模型生成 · 模型与规则审核")).toBeInTheDocument();
    await user.click(within(drawer).getByRole("tab", { name: "协作轨迹" }));
    await user.click(within(drawer).getByRole("button", { name: "查看 PathPlanningGraph" }));
    expect(await screen.findByText("deterministic_rank")).toBeInTheDocument();
    await user.click(within(drawer).getByRole("button", { name: "关闭" }));

    await user.click(screen.getByRole("button", { name: "完成本节学习" }));
    expect(screen.getByRole("alertdialog", { name: "仍有学习资源未完成" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "仍然完成本节" }));
    await waitFor(() => expect(calls).toContainEqual(expect.objectContaining({ method: "patch", url: PATH_ENDPOINTS.updateTask(1001), payload: { status: "completed" } })));
  });

  it("queues only the missing resources for the current section", async () => {
    const user = userEvent.setup();
    const calls: Array<{ method: string; url: string; payload: unknown }> = [];
    installBaseAdapter({ calls });
    renderWithProviders(<LearningPathPage />);

    expect(await screen.findByText("本节学习安排")).toBeInTheDocument();
    expect(screen.getByText("本节已完成 0/1 个可学习资源 · 1 项待补齐")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "补齐未生成资源" }));

    await waitFor(() => expect(calls).toContainEqual(expect.objectContaining({
      method: "post",
      url: PATH_ENDPOINTS.taskResourceJobs(1001)
    })));
    expect(await screen.findByRole("button", { name: "正在生成" })).toBeDisabled();
  });

  it("labels a deterministic current task without presenting it as an AI recommendation", async () => {
    installBaseAdapter({
      pathResponse: {
        ...activePathResponse,
        path: {
          ...activePathResponse.path,
          plan_json: { ...activePathResponse.path.plan_json, generation_mode: "deterministic_source" }
        },
        tasks: activePathResponse.tasks.map((task) => ({
          ...task,
          learning_bundle: { ...task.learning_bundle, generation_mode: "deterministic_source" }
        }))
      }
    });
    renderWithProviders(<LearningPathPage />);

    expect(await screen.findByText("当前学习任务")).toBeInTheDocument();
    expect(screen.queryByText("AI 当前推荐")).not.toBeInTheDocument();
  });

  it("queues path planning with one click and only sends the course id", async () => {
    const user = userEvent.setup();
    const calls: Array<{ method: string; url: string; payload: unknown }> = [];
    installBaseAdapter({ empty: true, calls });
    renderWithProviders(<LearningPathPage />);

    expect(await screen.findByText("还没有个性化学习路径")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "一键生成学习路径" }));
    expect((await screen.findAllByRole("button", { name: "正在规划" })).every((button) => button.hasAttribute("disabled"))).toBe(true);
    expect(calls).toContainEqual(expect.objectContaining({ method: "post", url: AI_JOB_ENDPOINTS.pathPlanning, payload: { course_id: 808 } }));
    expect(screen.queryByText("学习周期")).not.toBeInTheDocument();
  });

  it("removes retired path parameters while keeping the selected course", async () => {
    installBaseAdapter();
    renderWithProviders(<LearningPathPage />, `${PATHS.path}?course_id=808&view=sprint&comparison_id=1201&sprint_plan_id=3001`);

    expect(await screen.findByText("复习启发式搜索")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByTestId("location")).toHaveTextContent("/app/courses/808/path");
      expect(screen.getByTestId("location")).not.toHaveTextContent("sprint");
      expect(screen.getByTestId("location")).not.toHaveTextContent("comparison_id");
    });
  });

  it("shows local feedback when path data fails to load", async () => {
    apiClient.defaults.adapter = async (config) => {
      if (config.url === COURSE_ENDPOINTS.list) return { data: courseListResponse, status: 200, statusText: "OK", headers: {}, config };
      throw new Error("path failed");
    };
    renderWithProviders(<LearningPathPage />);
    expect(await screen.findByText("学习路径数据读取失败，请稍后重试。")).toBeInTheDocument();
  });
});

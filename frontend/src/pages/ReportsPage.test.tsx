import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { type ReactNode } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../api/client";
import { AGENT_ENDPOINTS } from "../api/agents";
import { COURSE_ENDPOINTS } from "../api/courses";
import { EXPORT_ENDPOINTS } from "../api/exports";
import { PATH_ENDPOINTS } from "../api/paths";
import { PRACTICE_ENDPOINTS } from "../api/practice";
import { REPORT_ENDPOINTS } from "../api/reports";
import { PATHS } from "../app/routePaths";
import { ReportsPage } from "./ReportsPage";

let previousAdapter = apiClient.defaults.adapter;
let createObjectUrlSpy: ReturnType<typeof vi.fn>;
let revokeObjectUrlSpy: ReturnType<typeof vi.fn>;
let clickSpy: ReturnType<typeof vi.spyOn>;

function renderWithProviders(ui: ReactNode, initialPath = `${PATHS.reports}?course_id=808`) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialPath]}>
        <Routes>
          <Route path={PATHS.reports} element={ui} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

function parsePayload(data: unknown) {
  return typeof data === "string" ? JSON.parse(data) : data;
}

const coursesResponse = {
  data: [
    {
      id: "808",
      title: "人工智能导论",
      description: "课程资料",
      subject: "人工智能",
      source_type: "uploaded",
      status: "ready",
      progress_percent: 0,
      material_count: 1,
      knowledge_point_count: 2,
      chunk_count: 4
    }
  ],
  page: 1,
  page_size: 1,
  total: 1,
  trace_id: "trace_courses"
};

const emptyReport = {
  id: null,
  course_id: "808",
  practice_session_id: null,
  status: "empty",
  score: null,
  report: {
    summary: "还没有真实学习报告。",
    mastery_update: { weak_count: 0, mastered_count: 0, learning_count: 0 },
    weakness_list: [],
    evidence_refs: [],
    next_step_suggestions: ["完成一次课程练习后生成报告。"],
    review_queue_updates: [],
    profile_changes: []
  },
  created_at: null
};

const readyReport = {
  id: "801",
  course_id: "808",
  practice_session_id: "501",
  status: "ready",
  agent_trace_id: "trace_report",
  score: 67,
  report: {
    summary: "本次评估得分 67，基于真实练习作答生成。",
    mastery_update: { weak_count: 1, mastered_count: 2, learning_count: 1 },
    weakness_list: [{ knowledge_point_id: "401", title: "启发式搜索", source_type: "practice_assessment" }],
    evidence_refs: [{ practice_answer_id: "601", knowledge_point_id: "401", score: 0 }],
    next_step_suggestions: ["优先复习薄弱点。"],
    review_queue_updates: [],
    profile_changes: [],
    trend: {
      direction: "improved",
      score_delta: 12,
      sessions_compared: 3,
      scores: [55, 61, 67]
    },
    evidence_summary: {
      practice_count: 3,
      answer_count: 15,
      weakness_count: 1,
      path_status: "active",
      resource_count: 2
    },
    review_result: {
      review_status: "passed",
      confidence: 0.91,
      risk_flags: [],
      safety_summary: "统计数字与练习证据一致。"
    },
    resource_usage_summary: {
      doc: { opened: 2, started: 1, completed: 1, helpful: 1, too_easy: 0, too_hard: 0, not_helpful: 0 },
      video: { opened: 1, started: 1, completed: 0, helpful: 0, too_easy: 0, too_hard: 1, not_helpful: 0 }
    }
  },
  created_at: "2026-07-05T10:10:00Z"
};

const masteryResponse = {
  data: {
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
        order_index: 1,
        status: "weak",
        score: 38,
        prerequisite_ids: [],
        weakness_item_ids: ["701"],
        recommended_resource_ids: []
      },
      {
        id: "402",
        title: "智能体任务版图",
        chapter: "人工智能概述",
        order_index: 2,
        status: "mastered",
        score: 82,
        prerequisite_ids: [],
        weakness_item_ids: [],
        recommended_resource_ids: []
      },
      {
        id: "403",
        title: "状态空间",
        chapter: "搜索问题",
        order_index: 3,
        status: "learning",
        score: 60,
        prerequisite_ids: [],
        weakness_item_ids: [],
        recommended_resource_ids: []
      }
    ]
  },
  trace_id: "trace_mastery"
};

const completedPractice = {
  id: "501",
  course_id: "808",
  title: "人工智能导论练习",
  status: "completed",
  score: 67,
  requested_difficulty: "adaptive",
  effective_difficulty: "medium",
  questions: [],
  answers: [],
  created_at: "2026-07-05T09:00:00Z",
  updated_at: "2026-07-05T10:00:00Z"
};

const emptyPathResponse = {
  data: {
    course_id: "808",
    status: "not_started",
    message: "尚未生成路径",
    path: null,
    tasks: [],
    evidence_summary: {
      knowledge_point_count: 3,
      confirmed_or_reviewing_weakness_count: 1,
      pending_weakness_count: 0,
      resource_count: 0,
      basis: []
    }
  },
  trace_id: "trace_path"
};

describe("ReportsPage", () => {
  beforeEach(() => {
    previousAdapter = apiClient.defaults.adapter;
    createObjectUrlSpy = vi.fn(() => "blob:learning-dossier");
    revokeObjectUrlSpy = vi.fn();
    Object.defineProperty(window.URL, "createObjectURL", {
      configurable: true,
      value: createObjectUrlSpy
    });
    Object.defineProperty(window.URL, "revokeObjectURL", {
      configurable: true,
      value: revokeObjectUrlSpy
    });
    clickSpy = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
  });

  afterEach(() => {
    apiClient.defaults.adapter = previousAdapter;
    clickSpy.mockRestore();
  });

  it("renders empty latest report, generates a real report, and exports Markdown through an async job", async () => {
    const user = userEvent.setup();
    const calls: Array<{ method: string; url: string; payload: unknown; params: unknown }> = [];
    let generated = false;

    apiClient.defaults.adapter = async (config) => {
      const method = (config.method ?? "get").toLowerCase();
      const url = config.url ?? "";
      const payload = parsePayload(config.data);
      calls.push({ method, url, payload, params: config.params });

      if (url === COURSE_ENDPOINTS.list) {
        return { data: coursesResponse, status: 200, statusText: "OK", headers: {}, config };
      }
      if (url === REPORT_ENDPOINTS.latest) {
        return {
          data: { data: generated ? readyReport : emptyReport, trace_id: "trace_latest_report" },
          status: 200,
          statusText: "OK",
          headers: {},
          config
        };
      }
      if (url === COURSE_ENDPOINTS.masteryMap(808)) {
        return { data: masteryResponse, status: 200, statusText: "OK", headers: {}, config };
      }
      if (url === PRACTICE_ENDPOINTS.recent) {
        return {
          data: {
            data: generated
              ? [
                  completedPractice,
                  { ...completedPractice, id: "500", score: 61, updated_at: "2026-07-04T10:00:00Z" },
                  { ...completedPractice, id: "499", score: 55, updated_at: "2026-07-03T10:00:00Z" }
                ]
              : [],
            trace_id: "trace_practice"
          },
          status: 200,
          statusText: "OK",
          headers: {},
          config
        };
      }
      if (url === PATH_ENDPOINTS.current) {
        return { data: emptyPathResponse, status: 200, statusText: "OK", headers: {}, config };
      }
      if (url === REPORT_ENDPOINTS.generate) {
        generated = true;
        return { data: { data: readyReport, trace_id: "trace_report" }, status: 200, statusText: "OK", headers: {}, config };
      }
      if (url === AGENT_ENDPOINTS.trace("trace_report")) {
        return {
          data: {
            data: {
              trace_id: "trace_report",
              workflow: "report",
              artifact_type: "assessment_report",
              artifact_id: "801",
              course_id: "808",
              status: "completed",
              steps: [
                {
                  id: "1",
                  agent_name: "aggregate_evidence",
                  step_index: 2,
                  status: "completed",
                  input_summary: "汇总练习与掌握度",
                  output_summary: "已生成确定性趋势",
                  duration_ms: 11,
                  metadata: { practice_count: 3, trend_direction: "improved" },
                  created_at: "2026-07-05T10:10:01Z"
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
      if (url === EXPORT_ENDPOINTS.learningDossierJob) {
        return {
          data: {
            data: {
              job_id: "901",
              status: "queued",
              format: "markdown",
              filename: "edunova-人工智能导论-learning-dossier.md",
              content_type: "text/markdown; charset=utf-8",
              agent_trace_id: null,
              error_message: null,
              created_at: "2026-07-05T15:00:00Z",
              updated_at: "2026-07-05T15:00:00Z",
              completed_at: null
            },
            trace_id: "trace_export_job"
          },
          status: 200,
          statusText: "OK",
          headers: {},
          config
        };
      }
      if (url === EXPORT_ENDPOINTS.job(901)) {
        return {
          data: {
            data: {
              job_id: "901",
              status: "completed",
              format: "markdown",
              filename: "edunova-人工智能导论-learning-dossier.md",
              content_type: "text/markdown; charset=utf-8",
              agent_trace_id: null,
              error_message: null,
              created_at: "2026-07-05T15:00:00Z",
              updated_at: "2026-07-05T15:00:01Z",
              completed_at: "2026-07-05T15:00:01Z"
            },
            trace_id: "trace_export_job_done"
          },
          status: 200,
          statusText: "OK",
          headers: {},
          config
        };
      }
      if (url === EXPORT_ENDPOINTS.download(901)) {
        return {
          data: new Blob(["# 人工智能导论 学习档案\n\n本次评估得分 67，基于真实练习作答生成。"], {
            type: "text/markdown; charset=utf-8"
          }),
          status: 200,
          statusText: "OK",
          headers: {},
          config
        };
      }
      throw new Error(`Unexpected request ${method} ${url}`);
    };

    renderWithProviders(<ReportsPage />);

    expect(await screen.findByText("还没有真实学习报告")).toBeInTheDocument();
    expect(screen.getByText("完成一次课程练习后可生成报告")).toBeInTheDocument();
    expect(screen.queryByText("学习报告读取失败，请稍后重试。")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "导出学习档案" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "生成学习报告" }));

    expect(await screen.findByText("本次评估得分 67，基于真实练习作答生成。")).toBeInTheDocument();
    expect(screen.getAllByText("启发式搜索").length).toBeGreaterThan(0);
    expect(screen.getByText("较早期提升 12 分")).toBeInTheDocument();
    expect(screen.getByText("60%")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "资源使用概览" })).toHaveTextContent("外部视频");
    expect(screen.getByRole("region", { name: "资源使用概览" })).toHaveTextContent("偏难 1");
    const reportDetailsTrigger = screen.getByRole("button", { name: "报告详情" });
    await user.click(reportDetailsTrigger);
    const closeDetails = screen.getByRole("button", { name: "关闭报告详情" });
    expect(closeDetails).toHaveFocus();
    await user.keyboard("{Shift>}{Tab}{/Shift}");
    expect(screen.getByRole("tab", { name: "协作轨迹" })).toHaveFocus();
    await user.tab();
    expect(closeDetails).toHaveFocus();
    expect(await screen.findByText("优先复习薄弱点。")).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "证据与审核" }));
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("15")).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "协作轨迹" }));
    await user.click(screen.getByRole("button", { name: "查看 ReportGraph" }));
    expect(await screen.findByText("aggregate_evidence")).toBeInTheDocument();
    expect(calls).toContainEqual(
      expect.objectContaining({
        method: "post",
        url: REPORT_ENDPOINTS.generate,
        payload: { course_id: 808 }
      })
    );

    await user.click(closeDetails);
    expect(reportDetailsTrigger).toHaveFocus();
    await user.click(screen.getByRole("button", { name: "导出学习档案" }));
    await user.click(screen.getByRole("button", { name: "导出 Markdown" }));

    expect(await screen.findByText("已生成 Markdown 学习档案。")).toBeInTheDocument();
    expect(createObjectUrlSpy).toHaveBeenCalledTimes(1);
    expect(clickSpy).toHaveBeenCalledTimes(1);
    expect(revokeObjectUrlSpy).not.toHaveBeenCalled();
    expect(calls).toContainEqual(
      expect.objectContaining({
        method: "post",
        url: EXPORT_ENDPOINTS.learningDossierJob,
        payload: { course_id: 808, format: "markdown" }
      })
    );
    expect(calls).toContainEqual(expect.objectContaining({ method: "get", url: EXPORT_ENDPOINTS.job(901) }));
    expect(calls).toContainEqual(
      expect.objectContaining({
        method: "get",
        url: EXPORT_ENDPOINTS.download(901)
      })
    );
  });

  it("shows local report loading errors", async () => {
    apiClient.defaults.adapter = async (config) => {
      if (config.url === COURSE_ENDPOINTS.list) {
        return { data: coursesResponse, status: 200, statusText: "OK", headers: {}, config };
      }
      throw new Error("report failed");
    };

    renderWithProviders(<ReportsPage />);

    expect(await screen.findByText("学习报告读取失败，请稍后重试。")).toBeInTheDocument();
    expect(screen.getByText("报告快照暂时无法读取")).toBeInTheDocument();
    expect(screen.queryByText("还没有真实学习报告")).not.toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "重新读取" }).length).toBeGreaterThan(0);
  });

  it("keeps the report snapshot visible while marking newer practice data stale", async () => {
    apiClient.defaults.adapter = async (config) => {
      if (config.url === COURSE_ENDPOINTS.list) {
        return { data: coursesResponse, status: 200, statusText: "OK", headers: {}, config };
      }
      if (config.url === REPORT_ENDPOINTS.latest) {
        return { data: { data: readyReport, trace_id: "trace_report" }, status: 200, statusText: "OK", headers: {}, config };
      }
      if (config.url === COURSE_ENDPOINTS.masteryMap(808)) {
        return { data: masteryResponse, status: 200, statusText: "OK", headers: {}, config };
      }
      if (config.url === PRACTICE_ENDPOINTS.recent) {
        return {
          data: { data: [{ ...completedPractice, id: "502", score: 82, updated_at: "2026-07-06T10:00:00Z" }, completedPractice], trace_id: "trace_practice" },
          status: 200,
          statusText: "OK",
          headers: {},
          config
        };
      }
      if (config.url === PATH_ENDPOINTS.current) {
        return { data: emptyPathResponse, status: 200, statusText: "OK", headers: {}, config };
      }
      throw new Error(`Unexpected request ${config.url}`);
    };

    renderWithProviders(
      <ReportsPage />,
      `${PATHS.reports}?course_id=808&return_to=course&course_session_id=91&course_message_id=92`
    );

    expect(await screen.findByText("已有新的练习结果")).toBeInTheDocument();
    expect(screen.getByText("实时数据已包含新的练习结果，下面的报告文字仍是上一次生成的快照。")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "更新学习报告" }).length).toBeGreaterThan(0);
    expect(within(screen.getByRole("region", { name: "实时学习指标" })).getByText("82 分")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "最近报告快照" })).toHaveTextContent("本次评估得分 67");
    expect(screen.getByRole("link", { name: "针对练习启发式搜索" })).toHaveAttribute(
      "href",
      "/app/practice?return_to=course&course_session_id=91&course_message_id=92&course_id=808&knowledge_point_id=401&new=1"
    );
  });

  it("shows local export errors without blocking the report", async () => {
    const user = userEvent.setup();

    apiClient.defaults.adapter = async (config) => {
      if (config.url === COURSE_ENDPOINTS.list) {
        return { data: coursesResponse, status: 200, statusText: "OK", headers: {}, config };
      }
      if (config.url === REPORT_ENDPOINTS.latest) {
        return { data: { data: readyReport, trace_id: "trace_latest_report" }, status: 200, statusText: "OK", headers: {}, config };
      }
      if (config.url === COURSE_ENDPOINTS.masteryMap(808)) {
        return { data: masteryResponse, status: 200, statusText: "OK", headers: {}, config };
      }
      if (config.url === PRACTICE_ENDPOINTS.recent) {
        return { data: { data: [completedPractice], trace_id: "trace_practice" }, status: 200, statusText: "OK", headers: {}, config };
      }
      if (config.url === PATH_ENDPOINTS.current) {
        return { data: emptyPathResponse, status: 200, statusText: "OK", headers: {}, config };
      }
      if (config.url === EXPORT_ENDPOINTS.learningDossierJob) {
        throw new Error("export failed");
      }
      throw new Error(`Unexpected request ${config.url}`);
    };

    renderWithProviders(<ReportsPage />);

    expect(await screen.findByText("本次评估得分 67，基于真实练习作答生成。")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "导出学习档案" }));
    await user.click(screen.getByRole("button", { name: "导出 Markdown" }));

    expect(await screen.findByText("学习档案导出失败，请稍后重试。")).toBeInTheDocument();
    expect(screen.getByText("本次评估得分 67，基于真实练习作答生成。")).toBeInTheDocument();
    await waitFor(() => expect(createObjectUrlSpy).not.toHaveBeenCalled());
  });
});

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { type ReactNode } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../api/client";
import { COURSE_ENDPOINTS } from "../api/courses";
import { EXPORT_ENDPOINTS } from "../api/exports";
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
  score: 67,
  report: {
    summary: "本次评估得分 67，基于真实练习作答生成。",
    mastery_update: { weak_count: 1, mastered_count: 2, learning_count: 1 },
    weakness_list: [{ knowledge_point_id: "401", title: "启发式搜索", source_type: "practice_assessment" }],
    evidence_refs: [{ practice_answer_id: "601", knowledge_point_id: "401", score: 0 }],
    next_step_suggestions: ["优先复习薄弱点。"],
    review_queue_updates: [],
    profile_changes: []
  },
  created_at: "2026-07-05T10:10:00Z"
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

  it("renders empty latest report, generates a real report, and exports Markdown", async () => {
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
      if (url === REPORT_ENDPOINTS.generate) {
        generated = true;
        return { data: { data: readyReport, trace_id: "trace_report" }, status: 200, statusText: "OK", headers: {}, config };
      }
      if (url === EXPORT_ENDPOINTS.learningDossier) {
        return {
          data: {
            data: {
              course_id: "808",
              filename: "edunova-人工智能导论-learning-dossier.md",
              content_type: "text/markdown; charset=utf-8",
              markdown: "# 人工智能导论 学习档案\n\n本次评估得分 67，基于真实练习作答生成。",
              generated_at: "2026-07-05T15:00:00Z",
              source_summary: {
                has_report: true,
                report_id: "801",
                knowledge_point_count: 2,
                weakness_count: 1,
                path_task_count: 0,
                resource_count: 0,
                practice_answer_count: 1
              }
            },
            trace_id: "trace_export"
          },
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
    expect(screen.getByText("启发式搜索")).toBeInTheDocument();
    expect(screen.getByText("优先复习薄弱点。")).toBeInTheDocument();
    expect(calls).toContainEqual(
      expect.objectContaining({
        method: "post",
        url: REPORT_ENDPOINTS.generate,
        payload: { course_id: 808 }
      })
    );

    await user.click(screen.getByRole("button", { name: "导出学习档案" }));

    expect(await screen.findByText("已生成 Markdown 学习档案。")).toBeInTheDocument();
    expect(createObjectUrlSpy).toHaveBeenCalledTimes(1);
    expect(clickSpy).toHaveBeenCalledTimes(1);
    expect(revokeObjectUrlSpy).toHaveBeenCalledWith("blob:learning-dossier");
    expect(calls).toContainEqual(
      expect.objectContaining({
        method: "post",
        url: EXPORT_ENDPOINTS.learningDossier,
        payload: { course_id: 808 }
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
      if (config.url === EXPORT_ENDPOINTS.learningDossier) {
        throw new Error("export failed");
      }
      throw new Error(`Unexpected request ${config.url}`);
    };

    renderWithProviders(<ReportsPage />);

    expect(await screen.findByText("本次评估得分 67，基于真实练习作答生成。")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "导出学习档案" }));

    expect(await screen.findByText("学习档案导出失败，请稍后重试。")).toBeInTheDocument();
    expect(screen.getByText("本次评估得分 67，基于真实练习作答生成。")).toBeInTheDocument();
    await waitFor(() => expect(createObjectUrlSpy).not.toHaveBeenCalled());
  });
});

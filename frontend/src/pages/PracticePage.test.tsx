import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { type ReactNode } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { apiClient } from "../api/client";
import { AGENT_ENDPOINTS } from "../api/agents";
import { COURSE_ENDPOINTS } from "../api/courses";
import { PRACTICE_ENDPOINTS } from "../api/practice";
import { PATHS } from "../app/routePaths";
import { PracticePage } from "./PracticePage";

let previousAdapter = apiClient.defaults.adapter;

function renderWithProviders(ui: ReactNode, initialPath = `${PATHS.practice}?course_id=808`) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialPath]}>
        <Routes>
          <Route path={PATHS.practice} element={ui} />
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

const pointsResponse = {
  data: [
    {
      id: "401",
      title: "启发式搜索",
      summary: "理解启发函数。",
      chapter: "搜索问题",
      order_index: 0,
      difficulty: null
    }
  ],
  trace_id: "trace_points"
};

const practiceSession = {
  id: "501",
  course_id: "808",
  title: "人工智能导论 练习",
  status: "in_progress",
  score: null,
  questions: [
    {
      id: "q1",
      question_type: "single_choice",
      knowledge_point_id: "401",
      knowledge_point_title: "启发式搜索",
      prompt: "关于启发式搜索，哪一项最符合课程复习重点？",
      options: ["启发式搜索", "无关概念"],
      correct_answer: null,
      keywords: ["启发式搜索", "关键概念"],
      explanation: "围绕课程引用复习。",
      difficulty: "medium"
    }
  ],
  answers: [],
  created_at: "2026-07-05T10:00:00Z",
  updated_at: "2026-07-05T10:00:00Z"
};

describe("PracticePage", () => {
  beforeEach(() => {
    previousAdapter = apiClient.defaults.adapter;
  });

  afterEach(() => {
    apiClient.defaults.adapter = previousAdapter;
  });

  it("creates a real practice session and submits answers for feedback", async () => {
    const user = userEvent.setup();
    const calls: Array<{ method: string; url: string; payload: unknown; params: unknown }> = [];

    apiClient.defaults.adapter = async (config) => {
      const method = (config.method ?? "get").toLowerCase();
      const url = config.url ?? "";
      const payload = parsePayload(config.data);
      calls.push({ method, url, payload, params: config.params });

      if (url === COURSE_ENDPOINTS.list) {
        return { data: coursesResponse, status: 200, statusText: "OK", headers: {}, config };
      }
      if (url === COURSE_ENDPOINTS.knowledgePoints(808)) {
        return { data: pointsResponse, status: 200, statusText: "OK", headers: {}, config };
      }
      if (url === PRACTICE_ENDPOINTS.sessions) {
        return { data: { data: practiceSession, trace_id: "trace_practice" }, status: 200, statusText: "OK", headers: {}, config };
      }
      if (url === PRACTICE_ENDPOINTS.answers(501)) {
        return {
          data: {
            data: {
              ...practiceSession,
              status: "completed",
              agent_trace_id: "trace_assessment",
              score: 0,
              closure_update: {
                weaknesses_added: 1,
                weaknesses_updated: 0,
                path_update_status: "replanned",
                path_agent_trace_id: "trace_path_replan",
                recommended_resource_ids: ["801"]
              },
              answers: [
                {
                  question_id: "q1",
                  answer_text: "无关概念",
                  is_correct: false,
                  feedback: {
                    score: 0,
                    message: "这道题暴露了需要复习的知识点。",
                    matched_keywords: [],
                    missing_keywords: ["启发式搜索"],
                    explanation: "围绕课程引用复习。",
                    diagnosis: {
                      misconception: "混淆了启发式搜索与无信息搜索。",
                      missing_concepts: ["启发函数"],
                      recommended_action: "复习课程引用并完成同类题。",
                      confidence: 0.88,
                      evidence_ref: { type: "practice_answer", id: "601" }
                    }
                  }
                }
              ]
            },
            trace_id: "trace_feedback"
          },
          status: 200,
          statusText: "OK",
          headers: {},
          config
        };
      }
      if (url === AGENT_ENDPOINTS.trace("trace_assessment")) {
        return {
          data: {
            data: {
              trace_id: "trace_assessment",
              workflow: "assessment",
              artifact_type: "practice_session",
              artifact_id: "501",
              course_id: "808",
              status: "completed",
              steps: [
                {
                  id: "1",
                  agent_name: "diagnose_errors",
                  step_index: 3,
                  status: "completed",
                  input_summary: "分析低分题",
                  output_summary: "已生成错因诊断",
                  duration_ms: 12,
                  metadata: { weakness_count: 1 },
                  created_at: "2026-07-05T10:00:01Z"
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
      throw new Error(`Unexpected request ${method} ${url}`);
    };

    renderWithProviders(<PracticePage />);

    expect(await screen.findByDisplayValue("人工智能导论")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "生成练习" }));
    expect(await screen.findByText("关于启发式搜索，哪一项最符合课程复习重点？")).toBeInTheDocument();

    await user.type(screen.getByRole("textbox", { name: "q1 作答区" }), "无关概念");
    await user.click(screen.getByRole("button", { name: "提交答案" }));

    expect((await screen.findAllByText("这道题暴露了需要复习的知识点。")).length).toBeGreaterThan(0);
    expect(screen.getByText("得分 0")).toBeInTheDocument();
    expect(screen.getByText("混淆了启发式搜索与无信息搜索。")).toBeInTheDocument();
    expect(screen.getByText("启发函数")).toBeInTheDocument();
    expect(screen.getByText("已有路径已按本次练习重排")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "查看更新后的路径" })).toHaveAttribute("href", "/app/path?course_id=808");
    await user.click(screen.getByRole("button", { name: "查看 AssessmentGraph" }));
    expect(await screen.findByText("diagnose_errors")).toBeInTheDocument();
    expect(calls).toContainEqual(
      expect.objectContaining({
        method: "post",
        url: PRACTICE_ENDPOINTS.sessions,
        payload: {
          course_id: 808,
          knowledge_point_ids: [401],
          question_count: 5,
          difficulty: "adaptive"
        }
      })
    );
    expect(calls).toContainEqual(
      expect.objectContaining({
        method: "post",
        url: PRACTICE_ENDPOINTS.answers(501),
        payload: {
          answers: [{ question_id: "q1", answer_text: "无关概念" }]
        }
      })
    );
  });

  it("shows real empty and local error states", async () => {
    apiClient.defaults.adapter = async (config) => {
      if (config.url === COURSE_ENDPOINTS.list) {
        return { data: coursesResponse, status: 200, statusText: "OK", headers: {}, config };
      }
      if (config.url === COURSE_ENDPOINTS.knowledgePoints(808)) {
        return { data: pointsResponse, status: 200, statusText: "OK", headers: {}, config };
      }
      throw new Error("practice failed");
    };

    renderWithProviders(<PracticePage />);

    expect(await screen.findByText("选择课程和知识点后生成练习。")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "生成练习" }));
    expect(await screen.findByText("练习生成失败，请稍后重试。")).toBeInTheDocument();
  });

  it("restores the session selected by the URL instead of creating a new practice", async () => {
    const calls: string[] = [];
    const completedSession = {
      ...practiceSession,
      status: "completed",
      requested_difficulty: "adaptive",
      effective_difficulty: "easy",
      score: 86,
      answers: [
        {
          question_id: "q1",
          answer_text: "启发函数用于估计剩余代价",
          is_correct: true,
          feedback: {
            score: 100,
            message: "作答正确。",
            matched_keywords: ["启发函数"],
            missing_keywords: [],
            explanation: "已命中课程关键概念。"
          }
        }
      ]
    };

    apiClient.defaults.adapter = async (config) => {
      const url = config.url ?? "";
      calls.push(`${(config.method ?? "get").toLowerCase()} ${url}`);
      if (url === COURSE_ENDPOINTS.list) {
        return { data: coursesResponse, status: 200, statusText: "OK", headers: {}, config };
      }
      if (url === COURSE_ENDPOINTS.knowledgePoints(808)) {
        return { data: pointsResponse, status: 200, statusText: "OK", headers: {}, config };
      }
      if (url === PRACTICE_ENDPOINTS.detail(501)) {
        return { data: { data: completedSession, trace_id: "trace_restore" }, status: 200, statusText: "OK", headers: {}, config };
      }
      throw new Error(`Unexpected request ${url}`);
    };

    renderWithProviders(<PracticePage />, `${PATHS.practice}?course_id=808&session_id=501`);

    expect(await screen.findByText("关于启发式搜索，哪一项最符合课程复习重点？")).toBeInTheDocument();
    expect(screen.getByText("本次得分 86 · 智能适配为基础")).toBeInTheDocument();
    expect(screen.getByDisplayValue("启发函数用于估计剩余代价")).toBeDisabled();
    expect(calls).not.toContain(`post ${PRACTICE_ENDPOINTS.sessions}`);
  });

  it("restores draft answers without showing an unevaluated zero score", async () => {
    const draftSession = {
      ...practiceSession,
      requested_difficulty: "adaptive",
      effective_difficulty: "easy",
      draft_saved_at: "2026-07-05T10:01:00Z",
      answers: [
        {
          question_id: "q1",
          answer_text: "先写下启发函数的作用",
          is_correct: null,
          feedback: {
            score: 0,
            message: "",
            matched_keywords: [],
            missing_keywords: [],
            explanation: ""
          }
        }
      ]
    };

    apiClient.defaults.adapter = async (config) => {
      const url = config.url ?? "";
      if (url === COURSE_ENDPOINTS.list) {
        return { data: coursesResponse, status: 200, statusText: "OK", headers: {}, config };
      }
      if (url === COURSE_ENDPOINTS.knowledgePoints(808)) {
        return { data: pointsResponse, status: 200, statusText: "OK", headers: {}, config };
      }
      if (url === PRACTICE_ENDPOINTS.detail(501)) {
        return { data: { data: draftSession, trace_id: "trace_draft" }, status: 200, statusText: "OK", headers: {}, config };
      }
      throw new Error(`Unexpected request ${url}`);
    };

    renderWithProviders(<PracticePage />, `${PATHS.practice}?course_id=808&session_id=501`);

    expect(await screen.findByDisplayValue("先写下启发函数的作用")).toBeEnabled();
    expect(screen.queryByText("得分 0")).not.toBeInTheDocument();
    expect(screen.getByText("实际难度：基础")).toBeInTheDocument();
  });
});

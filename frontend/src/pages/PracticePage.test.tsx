import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { type ReactNode } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { apiClient } from "../api/client";
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
              score: 0,
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
                    explanation: "围绕课程引用复习。"
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
    expect(calls).toContainEqual(
      expect.objectContaining({
        method: "post",
        url: PRACTICE_ENDPOINTS.sessions,
        payload: {
          course_id: 808,
          knowledge_point_ids: [401],
          question_count: 5,
          difficulty: "medium"
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
});

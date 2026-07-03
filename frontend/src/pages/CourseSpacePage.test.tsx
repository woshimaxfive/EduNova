import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { type ReactNode } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { PATHS } from "../app/routePaths";
import { apiClient } from "../api/client";
import { COURSE_ENDPOINTS } from "../api/courses";
import { RAG_ENDPOINTS, type RagSearchResponse } from "../api/rag";
import { CourseSpacePage } from "./CourseSpacePage";

let previousAdapter = apiClient.defaults.adapter;

type ApiCall = {
  method: string;
  url: string;
  payload: unknown;
};

type CoursePageOptions = {
  ragResponse?: RagSearchResponse;
  failRag?: boolean;
};

const citationResponse: RagSearchResponse = {
  course_id: 808,
  query: "启发式搜索怎么复习？",
  top_k: 5,
  results: [
    {
      chunk_id: 501,
      course_id: 808,
      material_id: 301,
      knowledge_point_id: 401,
      content: "启发式搜索利用启发函数估计路径代价，A* 会结合实际代价和预估代价。",
      source_title: "人工智能导论讲义.md",
      page_number: null,
      section_title: "启发式搜索",
      score: 9.5
    }
  ]
};

function parsePayload(data: unknown) {
  if (typeof data !== "string") {
    return data;
  }

  try {
    return JSON.parse(data);
  } catch {
    return data;
  }
}

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

function renderCoursePage(options: CoursePageOptions = {}) {
  const calls: ApiCall[] = [];

  apiClient.defaults.adapter = async (config) => {
    const method = (config.method ?? "get").toLowerCase();
    const url = config.url ?? "";
    const payload = parsePayload(config.data);
    calls.push({ method, url, payload });

    if (url === COURSE_ENDPOINTS.detail(808)) {
      return {
        data: {
          data: {
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
          },
          trace_id: "trace_course_detail"
        },
        status: 200,
        statusText: "OK",
        headers: {},
        config
      };
    }

    if (url === COURSE_ENDPOINTS.overview(808)) {
      return {
        data: {
          data: {
            course: {
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
            },
            materials: ["人工智能导论讲义.md"],
            knowledge_points: [],
            chunk_count: 3
          },
          trace_id: "trace_course_overview"
        },
        status: 200,
        statusText: "OK",
        headers: {},
        config
      };
    }

    if (url === COURSE_ENDPOINTS.knowledgePoints(808)) {
      return {
        data: {
          data: [
            {
              id: "401",
              title: "启发式搜索",
              chapter: "搜索问题",
              summary: "理解启发函数和 A*。",
              order: 1,
              mastery_level: "not_started",
              chunk_count: 2
            }
          ],
          trace_id: "trace_course_points"
        },
        status: 200,
        statusText: "OK",
        headers: {},
        config
      };
    }

    if (url === RAG_ENDPOINTS.search && method === "post") {
      if (options.failRag) {
        throw new Error("rag failed");
      }

      return {
        data: {
          data:
            options.ragResponse ??
            ({
              course_id: 808,
              query: typeof payload === "object" && payload !== null && "query" in payload ? String(payload.query) : "",
              top_k: 5,
              results: []
            } satisfies RagSearchResponse),
          trace_id: "trace_rag_search"
        },
        status: 200,
        statusText: "OK",
        headers: {},
        config
      };
    }

    return {
      data: { data: {}, trace_id: "trace_default" },
      status: 200,
      statusText: "OK",
      headers: {},
      config
    };
  };

  renderWithProviders(
    <MemoryRouter initialEntries={["/app/courses/808"]}>
      <Routes>
        <Route path={PATHS.courseDetail} element={<CourseSpacePage />} />
      </Routes>
    </MemoryRouter>
  );

  return { calls };
}

describe("CourseSpacePage RAG citations", () => {
  beforeEach(() => {
    previousAdapter = apiClient.defaults.adapter;
    localStorage.clear();
  });

  afterEach(() => {
    apiClient.defaults.adapter = previousAdapter;
  });

  it("searches course chunks when sending a course question and renders real citations", async () => {
    const user = userEvent.setup();
    const { calls } = renderCoursePage({ ragResponse: citationResponse });

    await screen.findByRole("heading", { name: "AI 搜索复习" });
    await user.type(screen.getByRole("textbox", { name: "课程问题输入" }), "启发式搜索怎么复习？");
    await user.click(screen.getByRole("button", { name: "发送" }));

    expect(calls).toContainEqual(
      expect.objectContaining({
        method: "post",
        url: RAG_ENDPOINTS.search,
        payload: {
          course_id: 808,
          query: "启发式搜索怎么复习？",
          top_k: 5
        }
      })
    );
    expect(await screen.findAllByText("人工智能导论讲义.md")).not.toHaveLength(0);
    expect(screen.getAllByText("启发式搜索")).not.toHaveLength(0);
    expect(screen.getByText(/启发函数估计路径代价/)).toBeInTheDocument();
    expect(screen.queryByText("AI 导论内置讲义")).not.toBeInTheDocument();
  });

  it("shows an insufficient-evidence message when retrieval finds no chunks", async () => {
    const user = userEvent.setup();

    renderCoursePage();

    await screen.findByRole("heading", { name: "AI 搜索复习" });
    await user.type(screen.getByRole("textbox", { name: "课程问题输入" }), "量子通信怎么复习？");
    await user.click(screen.getByRole("button", { name: "发送" }));

    const thread = await screen.findByRole("region", { name: "课程即时对话" });

    expect(within(thread).getByText("当前课程资料里没有找到足够依据。")).toBeInTheDocument();
  });

  it("keeps the typed question when course retrieval fails", async () => {
    const user = userEvent.setup();

    renderCoursePage({ failRag: true });

    const input = await screen.findByRole("textbox", { name: "课程问题输入" });
    await user.type(input, "这次检索会失败吗？");
    await user.click(screen.getByRole("button", { name: "发送" }));

    expect(await screen.findByRole("status")).toHaveTextContent("课程检索失败，请稍后重试。");
    expect(input).toHaveValue("这次检索会失败吗？");
    expect(screen.queryByRole("region", { name: "课程即时对话" })).not.toBeInTheDocument();
  });
});

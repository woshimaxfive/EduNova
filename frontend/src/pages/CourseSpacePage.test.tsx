import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { type ReactNode } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { PATHS } from "../app/routePaths";
import { apiClient } from "../api/client";
import { COURSE_ENDPOINTS } from "../api/courses";
import { TUTOR_ENDPOINTS, type TutorCitation, type TutorSessionDetail, type TutorSessionSummary } from "../api/tutor";
import { CourseSpacePage } from "./CourseSpacePage";

let previousAdapter = apiClient.defaults.adapter;

type ApiCall = {
  method: string;
  url: string;
  payload: unknown;
  params: unknown;
};

type CoursePageOptions = {
  sessions?: TutorSessionSummary[];
  sendDetail?: TutorSessionDetail;
  historyDetail?: TutorSessionDetail;
  failSend?: boolean;
};

const citationItem: TutorCitation = {
  chunk_id: 501,
  course_id: 808,
  material_id: 301,
  knowledge_point_id: 401,
  content: "启发式搜索利用启发函数估计路径代价，A* 会结合实际代价和预估代价。",
  source_title: "人工智能导论讲义.md",
  page_number: null,
  section_title: "启发式搜索",
  score: 9.5
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

function makeSession(id: string, title: string): TutorSessionSummary {
  return {
    id,
    scope: "course",
    course_id: "808",
    title,
    mode: "chat",
    archived_from_home: false,
    created_at: "2026-07-03T12:00:00Z",
    updated_at: "2026-07-03T12:01:00Z"
  };
}

function makeDetail(
  session: TutorSessionSummary,
  question: string,
  assistant: string,
  citation_json: TutorCitation[] = [citationItem]
): TutorSessionDetail {
  return {
    session,
    messages: [
      {
        id: "m1",
        session_id: session.id,
        role: "user",
        content: question,
        citation_json: [],
        trace_id: null,
        created_at: "2026-07-03T12:00:00Z"
      },
      {
        id: "m2",
        session_id: session.id,
        role: "assistant",
        content: assistant,
        citation_json,
        trace_id: null,
        created_at: "2026-07-03T12:01:00Z"
      }
    ]
  };
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
  const createdSession = makeSession("901", "启发式搜索怎么复习？");
  const defaultSendDetail = makeDetail(
    createdSession,
    "启发式搜索怎么复习？",
    "我先从课程资料里找到了相关依据。下面保留真实引用片段，后续接入大模型后会基于这些来源生成完整回答。"
  );

  apiClient.defaults.adapter = async (config) => {
    const method = (config.method ?? "get").toLowerCase();
    const url = config.url ?? "";
    const payload = parsePayload(config.data);
    calls.push({ method, url, payload, params: config.params });

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

    if (url === TUTOR_ENDPOINTS.sessions && method === "get") {
      return {
        data: {
          data: options.sessions ?? [],
          trace_id: "trace_course_sessions"
        },
        status: 200,
        statusText: "OK",
        headers: {},
        config
      };
    }

    if (url === TUTOR_ENDPOINTS.sessions && method === "post") {
      const title = typeof payload === "object" && payload !== null && "title" in payload ? String(payload.title) : "课程问题";
      createdSession.title = title;

      return {
        data: {
          data: createdSession,
          trace_id: "trace_create_course_session"
        },
        status: 200,
        statusText: "OK",
        headers: {},
        config
      };
    }

    if (url === TUTOR_ENDPOINTS.message(createdSession.id) && method === "post") {
      if (options.failSend) {
        throw new Error("send failed");
      }

      return {
        data: {
          data: options.sendDetail ?? defaultSendDetail,
          trace_id: "trace_send_course_message"
        },
        status: 200,
        statusText: "OK",
        headers: {},
        config
      };
    }

    if (url === TUTOR_ENDPOINTS.detail("777") && method === "get") {
      return {
        data: {
          data:
            options.historyDetail ??
            makeDetail(
              makeSession("777", "已有课程历史"),
              "历史里的问题",
              "历史里的回答保留真实引用。",
              [citationItem]
            ),
          trace_id: "trace_history_detail"
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

describe("CourseSpacePage course tutor sessions", () => {
  beforeEach(() => {
    previousAdapter = apiClient.defaults.adapter;
    localStorage.clear();
  });

  afterEach(() => {
    apiClient.defaults.adapter = previousAdapter;
  });

  it("loads course-scoped tutor sessions for the current course", async () => {
    const { calls } = renderCoursePage({ sessions: [makeSession("777", "已有课程历史")] });

    const courseHistory = await screen.findByLabelText("课程内历史对话");
    expect(await within(courseHistory).findByRole("button", { name: /已有课程历史/ })).toBeInTheDocument();
    expect(calls).toContainEqual(
      expect.objectContaining({
        method: "get",
        url: TUTOR_ENDPOINTS.sessions,
        params: {
          scope: "course",
          course_id: 808
        }
      })
    );
  });

  it("creates a course session before sending the first course question and renders persisted citations", async () => {
    const user = userEvent.setup();
    const { calls } = renderCoursePage();

    await screen.findByRole("heading", { name: "AI 搜索复习" });
    await user.type(screen.getByRole("textbox", { name: "课程问题输入" }), "启发式搜索怎么复习？");
    await user.click(screen.getByRole("button", { name: "发送" }));

    expect(calls).toContainEqual(
      expect.objectContaining({
        method: "post",
        url: TUTOR_ENDPOINTS.sessions,
        payload: {
          scope: "course",
          course_id: 808,
          mode: "chat",
          title: "启发式搜索怎么复习？"
        }
      })
    );
    expect(calls).toContainEqual(
      expect.objectContaining({
        method: "post",
        url: TUTOR_ENDPOINTS.message("901"),
        payload: {
          message: "启发式搜索怎么复习？"
        }
      })
    );
    expect(await screen.findAllByText("人工智能导论讲义.md")).not.toHaveLength(0);
    expect(screen.getAllByText("启发式搜索")).not.toHaveLength(0);
    expect(screen.getByText(/启发函数估计路径代价/)).toBeInTheDocument();
  });

  it("reuses the active course session for follow-up questions", async () => {
    const user = userEvent.setup();
    const { calls } = renderCoursePage();

    const input = await screen.findByRole("textbox", { name: "课程问题输入" });
    await user.type(input, "启发式搜索怎么复习？");
    await user.click(screen.getByRole("button", { name: "发送" }));
    await screen.findByText(/启发函数估计路径代价/);
    await user.type(input, "再讲讲 A*。");
    await user.click(screen.getByRole("button", { name: "发送" }));

    expect(calls.filter((call) => call.method === "post" && call.url === TUTOR_ENDPOINTS.sessions)).toHaveLength(1);
    expect(calls.filter((call) => call.method === "post" && call.url === TUTOR_ENDPOINTS.message("901"))).toHaveLength(2);
  });

  it("loads persisted messages and citations when selecting course history", async () => {
    const user = userEvent.setup();

    renderCoursePage({ sessions: [makeSession("777", "已有课程历史")] });

    const courseHistory = await screen.findByLabelText("课程内历史对话");
    await user.click(await within(courseHistory).findByRole("button", { name: /已有课程历史/ }));

    const thread = await screen.findByRole("region", { name: "课程即时对话" });
    expect(within(thread).getByText("历史里的问题")).toBeInTheDocument();
    expect(within(thread).getByText("历史里的回答保留真实引用。")).toBeInTheDocument();
    expect(screen.getAllByText("人工智能导论讲义.md")).not.toHaveLength(0);
    expect(screen.getByText(/启发函数估计路径代价/)).toBeInTheDocument();
  });

  it("shows an insufficient-evidence message from persisted assistant citations", async () => {
    const user = userEvent.setup();
    const session = makeSession("901", "量子通信怎么复习？");

    renderCoursePage({
      sendDetail: makeDetail(session, "量子通信怎么复习？", "我先检查了课程资料，但还没有足够依据支撑这个问题。", [])
    });

    await screen.findByRole("heading", { name: "AI 搜索复习" });
    await user.type(screen.getByRole("textbox", { name: "课程问题输入" }), "量子通信怎么复习？");
    await user.click(screen.getByRole("button", { name: "发送" }));

    const thread = await screen.findByRole("region", { name: "课程即时对话" });
    expect(within(thread).getByText("当前课程资料里没有找到足够依据。")).toBeInTheDocument();
  });

  it("keeps the typed question when course message persistence fails", async () => {
    const user = userEvent.setup();

    renderCoursePage({ failSend: true });

    const input = await screen.findByRole("textbox", { name: "课程问题输入" });
    await user.type(input, "这次保存会失败吗？");
    await user.click(screen.getByRole("button", { name: "发送" }));

    expect(await screen.findByRole("status")).toHaveTextContent("课程会话保存失败，请稍后重试。");
    expect(input).toHaveValue("这次保存会失败吗？");
    expect(screen.queryByRole("region", { name: "课程即时对话" })).not.toBeInTheDocument();
  });
});

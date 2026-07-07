import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { type ReactNode } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { PATHS } from "../app/routePaths";
import { AGENT_ENDPOINTS, type AgentTrace } from "../api/agents";
import { apiClient } from "../api/client";
import { COURSE_ENDPOINTS } from "../api/courses";
import { TUTOR_ENDPOINTS, type TutorCitation, type TutorSessionDetail, type TutorSessionSummary } from "../api/tutor";
import { CourseSpacePage } from "./CourseSpacePage";

let previousAdapter = apiClient.defaults.adapter;
const previousFetch = globalThis.fetch;

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
  learningState?: unknown;
  agentTrace?: AgentTrace;
  failLearningState?: boolean;
  failAgentTrace?: boolean;
  failWeaknessAction?: boolean;
  failSend?: boolean;
  streamEvents?: Array<{ event: string; data: unknown }>;
  controlledStream?: boolean;
  delayCourseDetail?: boolean;
  delayCourseData?: boolean;
};

type FetchCall = {
  url: string;
  method: string;
  payload: unknown;
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
  score: 9.5,
  keyword_score: 3.5,
  vector_score: 6,
  retrieval_source: "hybrid",
  embedding_status: "local_fallback"
};

const emptyLearningState = {
  course_id: "808",
  profile_overlay: {
    learning_goal: "",
    knowledge_foundation: "",
    weak_points: []
  },
  weakness_summary: {
    candidate_event_count: 0,
    pending_count: 0,
    confirmed_count: 0,
    reviewing_count: 0,
    completed_count: 0,
    dismissed_count: 0,
    latest_evidence_at: null
  },
  weakness_review_queue: [],
  path_summary: {
    status: "not_started",
    message: "学习路径尚未生成。",
    path_id: null,
    current_task_title: null,
    task_count: 0,
    completed_task_count: 0
  },
  mastery_summary: {
    total_count: 0,
    weak_count: 0,
    learning_count: 0,
    mastered_count: 0,
    recommended_review_count: 0,
    not_started_count: 0
  },
  evidence_summary: {
    candidate_event_count: 0,
    latest_trace_id: null,
    latest_source_title: null,
    latest_section_title: null
  }
};

const learningStateWithWeakness = {
  ...emptyLearningState,
  weakness_summary: {
    candidate_event_count: 2,
    pending_count: 1,
    confirmed_count: 0,
    reviewing_count: 0,
    completed_count: 0,
    dismissed_count: 0,
    latest_evidence_at: "2026-07-05T08:30:00Z"
  },
  weakness_review_queue: [
    {
      id: "701",
      title: "启发式搜索",
      status: "pending",
      source_type: "course_question",
      course_id: "808",
      knowledge_point_id: "401",
      recommended_resource_ids: [],
      recommended_resources: [],
      next_review_at: null,
      created_at: "2026-07-05T08:30:00Z",
      updated_at: "2026-07-05T08:30:00Z"
    }
  ],
  evidence_summary: {
    candidate_event_count: 2,
    latest_trace_id: "trace_candidate",
    latest_source_title: "人工智能导论讲义.md",
    latest_section_title: "启发式搜索"
  }
};

const agentTraceWithSteps: AgentTrace = {
  trace_id: "trace_candidate",
  course_id: "808",
  status: "completed",
  steps: [
    {
      id: "10",
      agent_name: "retrieve",
      step_index: 1,
      status: "completed",
      input_summary: "检索课程知识点",
      output_summary: "命中 2 条引用",
      duration_ms: 25,
      metadata: {
        citation_count: 2,
        review_result: "pass"
      },
      created_at: "2026-07-05T10:00:01Z"
    },
    {
      id: "11",
      agent_name: "diagnosis",
      step_index: 2,
      status: "completed",
      input_summary: "结合画像和引用判断薄弱点",
      output_summary: "形成待确认证据",
      duration_ms: 18,
      metadata: {},
      created_at: "2026-07-05T10:00:02Z"
    }
  ]
};

const learningStateWithReviewFlow = {
  ...emptyLearningState,
  weakness_summary: {
    candidate_event_count: 5,
    pending_count: 1,
    confirmed_count: 1,
    reviewing_count: 1,
    completed_count: 1,
    dismissed_count: 1,
    latest_evidence_at: "2026-07-05T08:30:00Z"
  },
  weakness_review_queue: [
    {
      id: "701",
      title: "启发式搜索",
      status: "pending",
      source_type: "course_question",
      course_id: "808",
      knowledge_point_id: "401",
      recommended_resource_ids: [],
      recommended_resources: [],
      next_review_at: null,
      created_at: "2026-07-05T08:30:00Z",
      updated_at: "2026-07-05T08:30:00Z"
    },
    {
      id: "702",
      title: "反向传播",
      status: "confirmed",
      source_type: "course_question",
      course_id: "808",
      knowledge_point_id: "402",
      recommended_resource_ids: ["801"],
      recommended_resources: [
        {
          id: "801",
          title: "反向传播讲解",
          resource_type: "doc"
        }
      ],
      next_review_at: null,
      created_at: "2026-07-05T08:31:00Z",
      updated_at: "2026-07-05T08:31:00Z"
    },
    {
      id: "703",
      title: "A* 搜索",
      status: "reviewing",
      source_type: "course_question",
      course_id: "808",
      knowledge_point_id: "403",
      recommended_resource_ids: [],
      recommended_resources: [],
      next_review_at: null,
      created_at: "2026-07-05T08:32:00Z",
      updated_at: "2026-07-05T08:32:00Z"
    },
    {
      id: "704",
      title: "搜索复杂度",
      status: "completed",
      source_type: "course_question",
      course_id: "808",
      knowledge_point_id: "404",
      recommended_resource_ids: [],
      recommended_resources: [],
      next_review_at: null,
      created_at: "2026-07-05T08:33:00Z",
      updated_at: "2026-07-05T08:33:00Z"
    },
    {
      id: "705",
      title: "已忽略弱点",
      status: "dismissed",
      source_type: "course_question",
      course_id: "808",
      knowledge_point_id: "405",
      recommended_resource_ids: [],
      recommended_resources: [],
      next_review_at: null,
      created_at: "2026-07-05T08:34:00Z",
      updated_at: "2026-07-05T08:34:00Z"
    }
  ]
};

const learningStateWithPath = {
  ...learningStateWithWeakness,
  path_summary: {
    status: "active",
    message: "当前学习路径进行中。",
    path_id: "901",
    current_task_title: "复习启发式搜索",
    task_count: 3,
    completed_task_count: 1
  },
  mastery_summary: {
    total_count: 4,
    weak_count: 1,
    learning_count: 1,
    mastered_count: 1,
    recommended_review_count: 1,
    not_started_count: 0
  },
  weakness_review_queue: [
    {
      id: "701",
      title: "启发式搜索",
      status: "confirmed",
      source_type: "course_question",
      course_id: "808",
      knowledge_point_id: "401",
      recommended_resource_ids: ["801"],
      recommended_resources: [
        {
          id: "801",
          title: "启发式搜索讲解",
          resource_type: "doc"
        }
      ],
      next_review_at: "2026-07-12T08:30:00Z",
      created_at: "2026-07-05T08:30:00Z",
      updated_at: "2026-07-05T08:30:00Z"
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

function createSseStream(events: Array<{ event: string; data: unknown }>) {
  const encoder = new TextEncoder();

  return new ReadableStream<Uint8Array>({
    start(controller) {
      for (const event of events) {
        controller.enqueue(encoder.encode(`event: ${event.event}\n`));
        controller.enqueue(encoder.encode(`data: ${JSON.stringify(event.data)}\n\n`));
      }
      controller.close();
    }
  });
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
  const fetchCalls: FetchCall[] = [];
  let streamController: ReadableStreamDefaultController<Uint8Array> | null = null;
  const encoder = new TextEncoder();
  const createdSession = makeSession("901", "启发式搜索怎么复习？");
  const defaultSendDetail = makeDetail(
    createdSession,
    "启发式搜索怎么复习？",
    "模型回答：启发式搜索复习时先理解启发函数，再对比 A* 的实际代价和预估代价。"
  );

  apiClient.defaults.adapter = async (config) => {
    const method = (config.method ?? "get").toLowerCase();
    const url = config.url ?? "";
    const payload = parsePayload(config.data);
    calls.push({ method, url, payload, params: config.params });

    if (options.delayCourseDetail && url === COURSE_ENDPOINTS.detail(808)) {
      return new Promise(() => {});
    }

    if (options.delayCourseData && [COURSE_ENDPOINTS.detail(808), COURSE_ENDPOINTS.overview(808), COURSE_ENDPOINTS.knowledgePoints(808)].includes(url)) {
      return new Promise(() => {});
    }

    if (url === COURSE_ENDPOINTS.learningState(808)) {
      if (options.failLearningState) {
        throw new Error("课程学习状态读取失败。");
      }

      return {
        data: {
          data: options.learningState ?? emptyLearningState,
          trace_id: "trace_learning_state"
        },
        status: 200,
        statusText: "OK",
        headers: {},
        config
      };
    }

    if (url === AGENT_ENDPOINTS.trace("trace_candidate")) {
      if (options.failAgentTrace) {
        throw new Error("Agent 轨迹读取失败。");
      }

      return {
        data: {
          data: options.agentTrace ?? agentTraceWithSteps,
          trace_id: "trace_agent_page"
        },
        status: 200,
        statusText: "OK",
        headers: {},
        config
      };
    }

    if (url.includes("/weakness-review-items/") && method === "post") {
      if (options.failWeaknessAction) {
        throw new Error("弱点状态更新失败。");
      }

      return {
        data: {
          data: {
            id: "701",
            title: "启发式搜索",
            status: "confirmed",
            source_type: "course_question",
            course_id: "808",
            knowledge_point_id: "401",
            recommended_resource_ids: [],
            recommended_resources: [],
            next_review_at: null,
            created_at: "2026-07-05T08:30:00Z",
            updated_at: "2026-07-05T08:40:00Z"
          },
          trace_id: "trace_weakness_action"
        },
        status: 200,
        statusText: "OK",
        headers: {},
        config
      };
    }

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
              summary: "理解启发函数和 A*。",
              chapter: "搜索问题",
              order_index: 1,
              difficulty: "基础"
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

  globalThis.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = input instanceof Request ? input.url : String(input);
    const rawBody = typeof init?.body === "string" ? init.body : "";
    const payload = rawBody ? JSON.parse(rawBody) : null;
    fetchCalls.push({ url, method: init?.method ?? "GET", payload });

    if (options.failSend) {
      return new Response(
        createSseStream([
          {
            event: "error",
            data: {
              code: "MODEL_PROVIDER_ERROR",
              message: "模型暂不可用，请检查设置或稍后重试。"
            }
          }
        ]),
        { status: 200, headers: { "content-type": "text/event-stream" } }
      );
    }

    if (options.controlledStream) {
      const stream = new ReadableStream<Uint8Array>({
        start(controller) {
          streamController = controller;
        }
      });
      return new Response(stream, { status: 200, headers: { "content-type": "text/event-stream" } });
    }

    return new Response(
      createSseStream(
        options.streamEvents ?? [
          {
            event: "metadata",
            data: {
              session_id: createdSession.id,
              trace_id: "trace_stream_course_message",
              citation_count: 1,
              used_model: true
            }
          },
          { event: "token", data: { content: "模型回答：启发式搜索复习" } },
          { event: "token", data: { content: "时先理解启发函数。" } },
          { event: "done", data: options.sendDetail ?? defaultSendDetail }
        ]
      ),
      { status: 200, headers: { "content-type": "text/event-stream" } }
    );
  });

  renderWithProviders(
    <MemoryRouter initialEntries={["/app/courses/808"]}>
      <Routes>
        <Route path={PATHS.courseDetail} element={<CourseSpacePage />} />
      </Routes>
    </MemoryRouter>
  );

  function emitStreamEvent(event: string, data: unknown) {
    if (streamController === null) {
      throw new Error("stream controller is not ready");
    }
    streamController.enqueue(encoder.encode(`event: ${event}\n`));
    streamController.enqueue(encoder.encode(`data: ${JSON.stringify(data)}\n\n`));
  }

  function closeStream() {
    streamController?.close();
  }

  return { calls, fetchCalls, emitStreamEvent, closeStream };
}

describe("CourseSpacePage course tutor sessions", () => {
  beforeEach(() => {
    previousAdapter = apiClient.defaults.adapter;
    localStorage.clear();
  });

  afterEach(() => {
    apiClient.defaults.adapter = previousAdapter;
    globalThis.fetch = previousFetch;
  });

  it("loads course-scoped tutor sessions for the current course", async () => {
    const { calls } = renderCoursePage({ sessions: [makeSession("777", "已有课程历史")] });

    const courseHistory = await screen.findByLabelText("历史对话");
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

  it("shows start guidance instead of a fixed assistant answer before any course message exists", async () => {
    renderCoursePage();

    expect(await screen.findByRole("heading", { name: "AI 搜索复习" })).toBeInTheDocument();
    expect(await screen.findByRole("region", { name: "待复习弱点" })).toHaveTextContent("还没有待确认弱点");
    expect(screen.getByRole("region", { name: "课程提问引导" })).toBeInTheDocument();
    expect(screen.getByText("推荐问题")).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "知识学习画布" })).not.toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "证据与 Agent 轨迹" })).not.toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "资源生成区" })).not.toBeInTheDocument();
    expect(screen.queryByText("监督学习先抓住“数据、目标、泛化”三件事")).not.toBeInTheDocument();
    expect(screen.queryByText("AI 辅导回答")).not.toBeInTheDocument();
  });

  it("links practice and reports entries with the current course preselected", async () => {
    renderCoursePage();

    const actionLinks = await screen.findByRole("navigation", { name: "课程行动入口" });
    expect(within(actionLinks).getByRole("link", { name: "开始练习" })).toHaveAttribute(
      "href",
      `${PATHS.practice}?course_id=808`
    );
    expect(within(actionLinks).getByRole("link", { name: "查看学习报告" })).toHaveAttribute(
      "href",
      `${PATHS.reports}?course_id=808`
    );
  });

  it("renders pending course weakness review items from learning state", async () => {
    renderCoursePage({ learningState: learningStateWithWeakness });

    const weaknessRegion = await screen.findByRole("region", { name: "待复习弱点" });
    await within(weaknessRegion).findByText("启发式搜索");

    expect(weaknessRegion).toHaveTextContent(/待确认\s*1/);
    expect(weaknessRegion).toHaveTextContent(/候选证据\s*2/);
    expect(within(weaknessRegion).getByText("启发式搜索")).toBeInTheDocument();
    expect(within(weaknessRegion).getAllByText("待确认").length).toBeGreaterThanOrEqual(2);
    expect(within(weaknessRegion).queryByText("学习路径尚未生成")).not.toBeInTheDocument();
  });

  it("renders actionable course weakness review states", async () => {
    renderCoursePage({ learningState: learningStateWithReviewFlow });

    const weaknessRegion = await screen.findByRole("region", { name: "待复习弱点" });
    await within(weaknessRegion).findByText("启发式搜索");

    expect(weaknessRegion).toHaveTextContent(/待确认\s*1/);
    expect(weaknessRegion).toHaveTextContent(/待复习\s*1/);
    expect(weaknessRegion).toHaveTextContent(/复习中\s*1/);
    expect(weaknessRegion).toHaveTextContent(/已完成\s*1/);
    expect(within(weaknessRegion).getByRole("button", { name: "确认 启发式搜索" })).toBeInTheDocument();
    expect(within(weaknessRegion).getByRole("button", { name: "开始 启发式搜索" })).toBeInTheDocument();
    expect(within(weaknessRegion).getByRole("button", { name: "忽略 启发式搜索" })).toBeInTheDocument();
    expect(within(weaknessRegion).getByRole("button", { name: "开始 反向传播" })).toBeInTheDocument();
    expect(within(weaknessRegion).getByRole("button", { name: "完成 A* 搜索" })).toBeInTheDocument();
    expect(within(weaknessRegion).getByRole("button", { name: "移除 搜索复杂度" })).toBeInTheDocument();
    expect(within(weaknessRegion).queryByText("已忽略弱点")).not.toBeInTheDocument();
  });

  it("updates a weakness review item and refreshes course learning state", async () => {
    const user = userEvent.setup();
    const { calls } = renderCoursePage({ learningState: learningStateWithReviewFlow });

    const weaknessRegion = await screen.findByRole("region", { name: "待复习弱点" });
    await user.click(await within(weaknessRegion).findByRole("button", { name: "确认 启发式搜索" }));

    await waitFor(() => {
      expect(calls).toContainEqual(
        expect.objectContaining({
          method: "post",
          url: COURSE_ENDPOINTS.weaknessReviewAction(808, "701", "confirm")
        })
      );
    });
    await waitFor(() => {
      expect(calls.filter((call) => call.url === COURSE_ENDPOINTS.learningState(808))).toHaveLength(2);
    });
  });

  it("shows local feedback when weakness review item update fails without blocking course questions", async () => {
    const user = userEvent.setup();
    const { fetchCalls } = renderCoursePage({ learningState: learningStateWithReviewFlow, failWeaknessAction: true });

    const weaknessRegion = await screen.findByRole("region", { name: "待复习弱点" });
    await user.click(await within(weaknessRegion).findByRole("button", { name: "确认 启发式搜索" }));

    expect(await within(weaknessRegion).findByText("弱点状态更新失败，请稍后重试。")).toBeInTheDocument();

    await user.type(screen.getByRole("textbox", { name: "课程问题输入" }), "为什么启发式搜索这么难？");
    await user.click(screen.getByRole("button", { name: "发送" }));

    await waitFor(() => {
      expect(fetchCalls).toContainEqual(
        expect.objectContaining({
          method: "POST",
          url: `/api/v1${TUTOR_ENDPOINTS.stream("901")}`
        })
      );
    });
  });

  it("shows local feedback when course learning state fails to load", async () => {
    renderCoursePage({ failLearningState: true });

    expect(await screen.findByText("课程学习状态读取失败，请稍后重试。")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "AI 搜索复习" })).toBeInTheDocument();
  });

  it("renders real agent trace steps in the thinking panel", async () => {
    const user = userEvent.setup();
    const { calls } = renderCoursePage({
      sessions: [makeSession("777", "已有课程历史")],
      learningState: learningStateWithWeakness,
      agentTrace: agentTraceWithSteps
    });

    await screen.findByRole("heading", { name: "AI 搜索复习" });
    await user.click(await screen.findByRole("button", { name: "思考过程" }));

    const detailPanel = await screen.findByRole("region", { name: "回答展开详情" });
    expect(await within(detailPanel).findByLabelText("Agent 执行轨迹")).toBeInTheDocument();
    expect(within(detailPanel).getByText("retrieve")).toBeInTheDocument();
    expect(within(detailPanel).getByText("命中 2 条引用")).toBeInTheDocument();
    expect(within(detailPanel).getByText("diagnosis")).toBeInTheDocument();
    expect(calls).toContainEqual(
      expect.objectContaining({
        method: "get",
        url: AGENT_ENDPOINTS.trace("trace_candidate")
      })
    );
  });

  it("links the resources panel to the real studio with the current course preselected", async () => {
    const user = userEvent.setup();
    renderCoursePage({
      sessions: [makeSession("777", "已有课程历史")],
      learningState: learningStateWithWeakness
    });

    await screen.findByRole("heading", { name: "AI 搜索复习" });
    await user.click(await screen.findByRole("button", { name: "生成资源" }));

    const detailPanel = await screen.findByRole("region", { name: "回答展开详情" });
    expect(within(detailPanel).getByRole("link", { name: "进入资源工坊" })).toHaveAttribute(
      "href",
      `${PATHS.studio}?course_id=808`
    );
    expect(within(detailPanel).queryByText(/后续阶段接入/)).not.toBeInTheDocument();
  });

  it("shows real learning path summary and links to the course path workspace", async () => {
    const user = userEvent.setup();
    renderCoursePage({
      sessions: [makeSession("777", "已有课程历史")],
      learningState: learningStateWithPath
    });

    await screen.findByRole("heading", { name: "AI 搜索复习" });
    await user.click(await screen.findByRole("button", { name: "学习路径" }));

    const detailPanel = await screen.findByRole("region", { name: "回答展开详情" });
    expect(within(detailPanel).getByText("当前学习路径进行中。")).toBeInTheDocument();
    expect(within(detailPanel).getByText("复习启发式搜索")).toBeInTheDocument();
    expect(within(detailPanel).getByRole("link", { name: "查看完整路径" })).toHaveAttribute(
      "href",
      `${PATHS.path}?course_id=808`
    );
    expect(within(detailPanel).queryByText("先围绕本次命中的来源复习核心概念")).not.toBeInTheDocument();
  });

  it("renders a real empty state when the agent trace has no steps", async () => {
    const user = userEvent.setup();
    renderCoursePage({
      sessions: [makeSession("777", "已有课程历史")],
      learningState: learningStateWithWeakness,
      agentTrace: {
        trace_id: "trace_candidate",
        course_id: "808",
        status: "completed",
        steps: []
      }
    });

    await screen.findByRole("heading", { name: "AI 搜索复习" });
    await user.click(await screen.findByRole("button", { name: "思考过程" }));

    const detailPanel = await screen.findByRole("region", { name: "回答展开详情" });
    expect(await within(detailPanel).findByText("当前 Agent trace 暂无可展示步骤。")).toBeInTheDocument();
    expect(within(detailPanel).queryByLabelText("Agent 执行轨迹")).not.toBeInTheDocument();
  });

  it("shows local thinking-panel feedback when agent trace loading fails", async () => {
    const user = userEvent.setup();
    renderCoursePage({
      sessions: [makeSession("777", "已有课程历史")],
      learningState: learningStateWithWeakness,
      failAgentTrace: true
    });

    await screen.findByRole("heading", { name: "AI 搜索复习" });
    await user.click(await screen.findByRole("button", { name: "思考过程" }));

    const detailPanel = await screen.findByRole("region", { name: "回答展开详情" });
    expect(await within(detailPanel).findByText("Agent 轨迹读取失败，请稍后重试。")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "待复习弱点" })).toHaveTextContent("启发式搜索");
  });

  it("does not show demo course fallback while real course data is loading", () => {
    renderCoursePage({ delayCourseData: true });

    expect(screen.queryByRole("heading", { name: "人工智能导论" })).not.toBeInTheDocument();
    expect(screen.queryByText("AI 导论内置讲义")).not.toBeInTheDocument();
    expect(screen.queryByText("监督学习与泛化")).not.toBeInTheDocument();
  });

  it("keeps the real course title when detail is pending but overview is available", async () => {
    renderCoursePage({ delayCourseDetail: true });

    expect(await screen.findByRole("heading", { name: "AI 搜索复习" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "课程加载中" })).not.toBeInTheDocument();
    expect(screen.getByLabelText("课程状态")).toHaveTextContent("资料1");
    expect(screen.getByLabelText("课程状态")).toHaveTextContent("知识点2");
  });

  it("creates a course session before sending the first course question and renders persisted citations", async () => {
    const user = userEvent.setup();
    const { calls, fetchCalls } = renderCoursePage();

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
    await waitFor(() => {
      expect(fetchCalls).toContainEqual(
        expect.objectContaining({
          method: "POST",
          url: `/api/v1${TUTOR_ENDPOINTS.stream("901")}`,
          payload: {
            message: "启发式搜索怎么复习？"
          }
        })
      );
    });
    expect(await screen.findAllByText("人工智能导论讲义.md")).not.toHaveLength(0);
    expect(screen.getByText(/模型回答：启发式搜索复习/)).toBeInTheDocument();
    expect(screen.getAllByText("启发式搜索")).not.toHaveLength(0);
    expect(screen.getAllByText("混合检索")).not.toHaveLength(0);
    expect(screen.getAllByText(/本地 fallback/)).not.toHaveLength(0);
    expect(screen.getByText(/启发函数估计路径代价/)).toBeInTheDocument();
    expect(screen.queryByText("监督学习先抓住“数据、目标、泛化”三件事")).not.toBeInTheDocument();
  });

  it("refreshes course learning state after a course question is sent", async () => {
    const user = userEvent.setup();
    const { calls } = renderCoursePage();

    await screen.findByRole("heading", { name: "AI 搜索复习" });
    await user.type(screen.getByRole("textbox", { name: "课程问题输入" }), "为什么启发式搜索这么难？");
    await user.click(screen.getByRole("button", { name: "发送" }));

    await waitFor(() => {
      expect(calls.filter((call) => call.url === COURSE_ENDPOINTS.learningState(808))).toHaveLength(2);
    });
  });

  it("opens study mode from a course knowledge point", async () => {
    const user = userEvent.setup();

    renderCoursePage();

    await screen.findByRole("heading", { name: "AI 搜索复习" });
    expect(screen.getByRole("button", { name: "问答模式" })).toHaveAttribute("aria-pressed", "true");

    await user.click(screen.getByRole("button", { name: "学习模式" }));
    await user.click(screen.getByRole("button", { name: "启发式搜索" }));

    const studyMode = screen.getByRole("region", { name: "课程学习模式" });
    expect(studyMode).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "学习模式" })).toHaveAttribute("aria-pressed", "true");
    expect(within(studyMode).getByRole("heading", { name: "启发式搜索" })).toBeInTheDocument();
    expect(within(studyMode).getByText("理解启发函数和 A*。")).toBeInTheDocument();
    expect(within(studyMode).getByLabelText("知识点信息")).toHaveTextContent("搜索问题");
    expect(screen.getByRole("complementary", { name: "AI 辅导" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "回到问答模式" }));

    expect(screen.getByRole("region", { name: "课程提问引导" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "问答模式" })).toHaveAttribute("aria-pressed", "true");
  });

  it("reuses the active course session for follow-up questions", async () => {
    const user = userEvent.setup();
    const { calls, fetchCalls } = renderCoursePage();

    const input = await screen.findByRole("textbox", { name: "课程问题输入" });
    await user.type(input, "启发式搜索怎么复习？");
    await user.click(screen.getByRole("button", { name: "发送" }));
    await screen.findByText(/启发函数估计路径代价/);
    await user.type(input, "再讲讲 A*。");
    await user.click(screen.getByRole("button", { name: "发送" }));

    expect(calls.filter((call) => call.method === "post" && call.url === TUTOR_ENDPOINTS.sessions)).toHaveLength(1);
    await waitFor(() => {
      expect(fetchCalls.filter((call) => call.url === `/api/v1${TUTOR_ENDPOINTS.stream("901")}`)).toHaveLength(2);
    });
  });

  it("renders streamed answer tokens before replacing them with persisted messages", async () => {
    const user = userEvent.setup();
    const { emitStreamEvent, closeStream } = renderCoursePage({ controlledStream: true });

    await screen.findByRole("heading", { name: "AI 搜索复习" });
    await user.type(screen.getByRole("textbox", { name: "课程问题输入" }), "启发式搜索怎么复习？");
    await user.click(screen.getByRole("button", { name: "发送" }));

    emitStreamEvent("metadata", {
      session_id: "901",
      trace_id: "trace_stream_course_message",
      citation_count: 1,
      used_model: true
    });
    emitStreamEvent("token", { content: "模型回答：" });

    expect(await screen.findByText("模型回答：")).toBeInTheDocument();

    emitStreamEvent("token", { content: "先看启发函数。" });
    emitStreamEvent("done", makeDetail(makeSession("901", "启发式搜索怎么复习？"), "启发式搜索怎么复习？", "持久化后的完整回答。", [citationItem]));
    closeStream();

    expect(await screen.findByText("持久化后的完整回答。")).toBeInTheDocument();
    expect(screen.queryByText("模型回答：先看启发函数。")).not.toBeInTheDocument();
  });

  it("loads persisted messages and citations when selecting course history", async () => {
    const user = userEvent.setup();

    renderCoursePage({ sessions: [makeSession("777", "已有课程历史")] });

    const courseHistory = await screen.findByLabelText("历史对话");
    await user.click(await within(courseHistory).findByRole("button", { name: /已有课程历史/ }));

    const thread = await screen.findByRole("region", { name: "课程即时对话" });
    expect(within(thread).getByText("历史里的问题")).toBeInTheDocument();
    expect(within(thread).getByText("历史里的回答保留真实引用。")).toBeInTheDocument();
    expect(screen.getAllByText("人工智能导论讲义.md")).not.toHaveLength(0);
    expect(screen.getByText(/启发函数估计路径代价/)).toBeInTheDocument();
  });

  it("opens study mode from a persisted citation and keeps the current session when returning", async () => {
    const user = userEvent.setup();

    renderCoursePage({ sessions: [makeSession("777", "已有课程历史")] });

    const courseHistory = await screen.findByLabelText("历史对话");
    await user.click(await within(courseHistory).findByRole("button", { name: /已有课程历史/ }));

    await user.click(await screen.findByRole("button", { name: /人工智能导论讲义\.md/ }));

    const studyMode = screen.getByRole("region", { name: "课程学习模式" });
    expect(within(studyMode).getByText("资料来源")).toBeInTheDocument();
    expect(within(studyMode).getByRole("heading", { name: "启发式搜索" })).toBeInTheDocument();
    expect(within(studyMode).getByText(/启发函数估计路径代价/)).toBeInTheDocument();
    expect(within(studyMode).getByLabelText("引用信息")).toHaveTextContent("人工智能导论讲义.md");
    expect(within(studyMode).getByLabelText("引用信息")).toHaveTextContent("本地 fallback");
    expect(screen.getByRole("complementary", { name: "AI 辅导" })).toHaveTextContent("历史里的回答保留真实引用。");

    await user.click(screen.getByRole("button", { name: "回到问答模式" }));

    const thread = await screen.findByRole("region", { name: "课程即时对话" });
    expect(within(thread).getByText("历史里的问题")).toBeInTheDocument();
    expect(within(thread).getByText("历史里的回答保留真实引用。")).toBeInTheDocument();
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
    expect(within(thread).getByText("我先检查了课程资料，但还没有足够依据支撑这个问题。")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "回答展开详情" })).toHaveTextContent("当前课程资料里没有找到足够依据。");
  });

  it("keeps the typed question when course message persistence fails", async () => {
    const user = userEvent.setup();

    renderCoursePage({ failSend: true });

    const input = await screen.findByRole("textbox", { name: "课程问题输入" });
    await user.type(input, "这次保存会失败吗？");
    await user.click(screen.getByRole("button", { name: "发送" }));

    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    expect(await screen.findByRole("alert")).toHaveTextContent("模型暂不可用，请检查设置或稍后重试。");
    expect(input).toHaveValue("这次保存会失败吗？");
    expect(screen.queryByRole("region", { name: "课程即时对话" })).not.toBeInTheDocument();
  });
});

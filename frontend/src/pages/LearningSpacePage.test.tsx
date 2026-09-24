import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes, type MemoryRouterProps } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { PATHS } from "../app/routePaths";
import { AGENT_ENDPOINTS } from "../api/agents";
import { apiClient } from "../api/client";
import { COURSE_ENDPOINTS } from "../api/courses";
import { DASHBOARD_ENDPOINTS, type DashboardSummary } from "../api/dashboard";
import { LEARNING_ENDPOINTS } from "../api/learning";
import { MATERIAL_ENDPOINTS, type MaterialListItem } from "../api/materials";
import { TUTOR_ENDPOINTS } from "../api/tutor";
import { useAuthStore } from "../features/auth/authStore";
import { isRestorableCourseBuilderJob } from "../features/aiJobs/jobRestoration";
import { makeCompletedAiJob } from "../test/aiJobs";
import { LearningSpacePage } from "./LearningSpacePage";

const starterSummary: DashboardSummary = {
  profile_summary: {
    display_name: "示例学生",
    starter_mode: "data_structures",
    has_profile: false,
    knowledge_foundation: null,
    learning_goal: null
  },
  recent_conversations: [
    {
      id: "501",
      title: "接口里的主页历史",
      meta: "刚刚",
      scope: "home",
      updated_at: "2026-07-03T12:00:00Z"
    }
  ],
  recent_courses: [
    {
      id: "101",
      title: "真实机器学习课",
      source_type: "generated",
      progress_label: "未开始",
      practiced_knowledge_point_count: 0,
      knowledge_point_count: 8,
      focus: "监督学习",
      next: "开始学习"
    }
  ],
  material_library_summary: {
    material_count: 1,
    unassigned_count: 0
  },
  recent_materials: [
    {
      id: "201",
      title: "真实资料讲义.md",
      type: "MD",
      detail: "已解析",
      modified: "今天",
      size: "12 KB"
    }
  ],
  recent_resources: [],
  command_suggestions: ["根据真实资料复习"],
  evidence_summary: {
    citation_count: 0,
    latest_trace_id: null,
    low_evidence_count: 0
  },
  empty_state: {
    kind: "active",
    title: "继续学习",
    description: "从最近内容继续。",
    action_label: "继续学习"
  }
};

const blankSummary: DashboardSummary = {
  ...starterSummary,
  profile_summary: {
    display_name: "空白学习者",
    starter_mode: "blank",
    has_profile: false,
    knowledge_foundation: null,
    learning_goal: null
  },
  recent_conversations: [],
  recent_courses: [],
  material_library_summary: {
    material_count: 0,
    unassigned_count: 0
  },
  recent_materials: [],
  command_suggestions: ["上传第一份资料"],
  empty_state: {
    kind: "blank",
    title: "还没有课程",
    description: "上传资料后可直接问，也可生成课程。",
    action_label: "上传资料"
  }
};

const materialRichSummary: DashboardSummary = {
  ...starterSummary,
  material_library_summary: {
    material_count: 3,
    unassigned_count: 0
  },
  recent_materials: [
    starterSummary.recent_materials[0],
    {
      id: "202",
      title: "期末复习题 2025",
      type: "PDF",
      detail: "已解析",
      modified: "昨天",
      size: "1.6 MB"
    },
    {
      id: "203",
      title: "神经网络课堂讲义",
      type: "DOCX",
      detail: "已解析",
      modified: "07-01",
      size: "820 KB"
    }
  ]
};

const allCourseSummaries = [
  {
    id: "101",
    title: "真实机器学习课",
    description: "从监督学习开始建立机器学习基础。",
    subject: "人工智能",
    source_type: "generated" as const,
    status: "active",
    progress_percent: 34,
    practiced_knowledge_point_count: 3,
    material_count: 2,
    knowledge_point_count: 8,
    chunk_count: 12,
  },
  {
    id: "102",
    title: "数据结构复习",
    description: "围绕树、图和排序算法复习。",
    subject: "计算机基础",
    source_type: "uploaded" as const,
    status: "active",
    progress_percent: 72,
    practiced_knowledge_point_count: 4,
    material_count: 1,
    knowledge_point_count: 6,
    chunk_count: 9,
  },
];

let previousAdapter = apiClient.defaults.adapter;
let previousFetch = globalThis.fetch;

type ApiCall = {
  method: string;
  url: string;
  payload: unknown;
};

type TutorMockOptions = {
  failMessageSend?: boolean;
  failMaterialSave?: boolean;
  historyDetail?: unknown;
  historyDetails?: Record<string, unknown>;
  streamReplacement?: string;
  streamWarnings?: string[];
  courseListFailures?: number;
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

function makeSessionDetail(
  sessionId: string,
  title: string,
  messages: Array<{
    id: string;
    role: "user" | "assistant";
    content: string;
    citation_json?: unknown[];
    trace_id?: string | null;
  }>,
  selectedMaterialIds: number[] = []
) {
  return {
    session: {
      id: sessionId,
      scope: "home",
      course_id: null,
      title,
      mode: "chat",
      archived_from_home: false,
      selected_material_ids: selectedMaterialIds,
      created_at: "2026-07-03T12:00:00Z",
      updated_at: "2026-07-03T12:01:00Z"
    },
    messages: messages.map((message, index) => ({
      ...message,
      citation_json: message.citation_json ?? [],
      trace_id: message.trace_id ?? null,
      created_at: `2026-07-03T12:0${index}:00Z`
    }))
  };
}

function renderWithDashboardSummary(
  summary: DashboardSummary = starterSummary,
  tutorOptions: TutorMockOptions = {},
  initialEntries: MemoryRouterProps["initialEntries"] = [PATHS.app]
) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false
      }
    }
  });
  const calls: ApiCall[] = [];
  const sentMessages: Array<{
    id: string;
    role: "user" | "assistant";
    content: string;
    citation_json?: unknown[];
    trace_id?: string | null;
  }> = [];
  const createdSession = {
    id: "501",
    scope: "home",
    course_id: null,
    title: "主页第一问",
    mode: "chat",
    archived_from_home: false,
    selected_material_ids: [] as number[],
    created_at: "2026-07-03T12:00:00Z",
    updated_at: "2026-07-03T12:00:00Z"
  };
  let recentConversations: DashboardSummary["recent_conversations"] = [...summary.recent_conversations];
  let courseListFailures = tutorOptions.courseListFailures ?? 0;

  globalThis.fetch = vi.fn(async (input, init) => {
    const rawUrl = typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;
    const url = rawUrl.replace(/^https?:\/\/[^/]+/, "").replace(/^\/api\/v1/, "");
    const payload = parsePayload(init?.body);
    calls.push({ method: String(init?.method ?? "get").toLowerCase(), url, payload });

    if (url !== TUTOR_ENDPOINTS.stream(501)) {
      return new Response(null, { status: 404 });
    }
    if (tutorOptions.failMessageSend) {
      return new Response(
        `event: error\ndata: ${JSON.stringify({ code: "MODEL_PROVIDER_ERROR", message: "模型暂不可用，请检查设置或稍后重试。" })}\n\n`,
        { status: 200, headers: { "Content-Type": "text/event-stream; charset=utf-8" } }
      );
    }

    const message = typeof payload === "object" && payload !== null && "message" in payload ? String(payload.message) : "";
    const citations = [
      {
        source_type: "material",
        material_id: "201",
        title: "真实资料讲义.md",
        section_title: "反向传播",
        page_number: null,
        snippet: "资料短摘录：反向传播需要先理解链式法则。",
        score: 8.2,
        retrieval_source: "hybrid",
        embedding_status: "local_fallback"
      },
      {
        source_type: "web",
        title: "联网搜索结果",
        url: "https://example.com/latest-ai-learning",
        snippet: "网页摘要：把概念复习和练习反馈结合起来。"
      }
    ];
    const draft = "## 学习建议\n\n先把学习目标拆成三步，再按资料和题型复习。";
    const finalAnswer = tutorOptions.streamReplacement ?? draft;
    sentMessages.push(
      { id: `u-${sentMessages.length + 1}`, role: "user", content: message },
      {
        id: `a-${sentMessages.length + 2}`,
        role: "assistant",
        content: finalAnswer,
        citation_json: citations,
        trace_id: "trace_home_tutor_test"
      }
    );
    const detail = makeSessionDetail("501", createdSession.title, sentMessages);
    const events = [
      ["metadata", { session_id: "501", trace_id: "trace_home_tutor_test", workflow: "home_tutor", citation_count: 0, used_model: true }],
      ["status", { stage: "material_retriever", label: "正在检索资料" }],
      ["sources", { citations, warnings: tutorOptions.streamWarnings ?? [] }],
      ["status", { stage: "answer", label: "正在生成回答" }],
      ["token", { content: "## 学习建议\n\n" }],
      ["token", { content: "先把学习目标拆成三步，再按资料和题型复习。" }],
      ...(tutorOptions.streamReplacement ? [["replace", { content: finalAnswer, reason: "review_repair" }]] : []),
      ["done", detail]
    ];
    const body = events
      .map(([event, data]) => `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`)
      .join("");

    return new Response(body, {
      status: 200,
      headers: { "Content-Type": "text/event-stream; charset=utf-8" }
    });
  });

  apiClient.defaults.adapter = async (config) => {
    const method = (config.method ?? "get").toLowerCase();
    const url = config.url ?? "";
    const payload = parsePayload(config.data);
    calls.push({ method, url, payload });

    if (url === DASHBOARD_ENDPOINTS.summary) {
      return {
        data: {
          data: {
            ...summary,
            recent_conversations: recentConversations
          },
          trace_id: "trace_dashboard_test"
        },
        status: 200,
        statusText: "OK",
        headers: {},
        config
      };
    }

    if (url === MATERIAL_ENDPOINTS.list && method === "get") {
      const materials: MaterialListItem[] = summary.recent_materials.map((material) => ({
        ...material,
        category: "document",
        extension: material.type,
        parse_status: material.detail === "已解析" ? "completed" : "uploaded",
        course_ids: []
      }));
      return {
        data: { data: materials, trace_id: "trace_material_list_test" },
        status: 200,
        statusText: "OK",
        headers: {},
        config
      };
    }

    if (url === COURSE_ENDPOINTS.list && method === "get") {
      if (courseListFailures > 0) {
        courseListFailures -= 1;
        throw new Error("course list failed");
      }

      return {
        data: { data: allCourseSummaries, trace_id: "trace_course_list_test" },
        status: 200,
        statusText: "OK",
        headers: {},
        config,
      };
    }

    if (url === LEARNING_ENDPOINTS.nextAction && method === "get") {
      return {
        data: {
          data: {
            kind: "study_knowledge_point",
            status: "ready",
            label: "学习知识点：监督学习",
            description: "先阅读课程内容，再通过练习形成有效掌握度证据。",
            course_id: "101",
            material_id: null,
            knowledge_point_id: "88",
            path_task_id: null,
            resource_id: null,
            weakness_item_id: null
          },
          trace_id: "trace_next_action_test"
        },
        status: 200,
        statusText: "OK",
        headers: {},
        config
      };
    }

    if (url === TUTOR_ENDPOINTS.history && method === "get") {
      const query = String((config.params as { q?: string } | undefined)?.q ?? "").toLowerCase();
      const items = recentConversations
        .filter((thread) => !query || thread.title.toLowerCase().includes(query) || "后端保存的问题".includes(query))
        .map((thread) => ({
          id: thread.id,
          scope: "home" as const,
          course_id: null,
          title: thread.title,
          mode: "chat" as const,
          archived_from_home: false,
          selected_material_ids: thread.id === createdSession.id ? createdSession.selected_material_ids : [],
          created_at: "2026-07-03T12:00:00Z",
          updated_at: thread.updated_at,
          match_snippet: query ? "后端保存的问题" : null
        }));
      return {
        data: { data: { items, page: 1, page_size: 30, total: items.length, has_more: false }, trace_id: "trace_history_test" },
        status: 200,
        statusText: "OK",
        headers: {},
        config
      };
    }

    if (url === TUTOR_ENDPOINTS.sessions && method === "post") {
      const title = typeof payload === "object" && payload !== null && "title" in payload ? String(payload.title) : "主页第一问";
      createdSession.title = title;
      createdSession.selected_material_ids = typeof payload === "object" && payload !== null && "selected_material_ids" in payload
        ? (payload.selected_material_ids as number[])
        : [];

      return {
        data: {
          data: createdSession,
          trace_id: "trace_session_create_test"
        },
        status: 200,
        statusText: "OK",
        headers: {},
        config
      };
    }

    const sessionDetailMatch = url.match(/^\/tutor\/sessions\/([^/]+)$/);
    if (sessionDetailMatch && method === "get") {
      const sessionId = sessionDetailMatch[1];
      const summaryThread = recentConversations.find((thread) => thread.id === sessionId);
      const fallbackTitle = summaryThread?.title ?? "接口里的主页历史";
      return {
        data: {
          data:
            tutorOptions.historyDetails?.[sessionId] ??
            tutorOptions.historyDetail ??
            makeSessionDetail(sessionId, fallbackTitle, [
              { id: `u-${sessionId}`, role: "user", content: "后端保存的问题" },
              { id: `a-${sessionId}`, role: "assistant", content: "后端保存的回答" }
            ]),
          trace_id: "trace_session_detail_test"
        },
        status: 200,
        statusText: "OK",
        headers: {},
        config
      };
    }

    if (sessionDetailMatch && method === "patch") {
      const sessionId = sessionDetailMatch[1];
      const title = typeof payload === "object" && payload !== null && "title" in payload ? String(payload.title).trim() : undefined;
      const selectedIds = typeof payload === "object" && payload !== null && "selected_material_ids" in payload
        ? (payload.selected_material_ids as number[])
        : undefined;
      if (selectedIds !== undefined && tutorOptions.failMaterialSave) {
        throw new Error("material save failed");
      }
      if (title !== undefined) {
        recentConversations = recentConversations.map((thread) => (thread.id === sessionId ? { ...thread, title } : thread));
      }
      if (createdSession.id === sessionId) {
        if (title !== undefined) createdSession.title = title;
        if (selectedIds !== undefined) createdSession.selected_material_ids = selectedIds;
      }

      return {
        data: {
          data: {
            id: sessionId,
            scope: "home",
            course_id: null,
            title: title ?? createdSession.title,
            mode: "chat",
            archived_from_home: false,
            selected_material_ids: selectedIds ?? createdSession.selected_material_ids,
            created_at: "2026-07-03T12:00:00Z",
            updated_at: "2026-07-03T12:02:00Z"
          },
          trace_id: "trace_session_rename_test"
        },
        status: 200,
        statusText: "OK",
        headers: {},
        config
      };
    }

    if (sessionDetailMatch && method === "delete") {
      const sessionId = sessionDetailMatch[1];
      recentConversations = recentConversations.filter((thread) => thread.id !== sessionId);

      return {
        data: {
          data: {
            session_id: sessionId,
            deleted: true
          },
          trace_id: "trace_session_delete_test"
        },
        status: 200,
        statusText: "OK",
        headers: {},
        config
      };
    }

    if (url === TUTOR_ENDPOINTS.message(501) && method === "post") {
      if (tutorOptions.failMessageSend) {
        throw new Error("send failed");
      }

      const message = typeof payload === "object" && payload !== null && "message" in payload ? String(payload.message) : "";
      sentMessages.push(
        { id: `u-${sentMessages.length + 1}`, role: "user", content: message },
        {
          id: `a-${sentMessages.length + 2}`,
          role: "assistant",
          content: "模型回答：先把学习目标拆成三步，再按资料和题型复习。",
          citation_json: [
            {
              source_type: "material",
              title: "真实资料讲义.md",
              snippet: "资料短摘录：反向传播需要先理解链式法则。"
            },
            {
              source_type: "web",
              title: "联网搜索结果",
              url: "https://example.com/latest-ai-learning",
              snippet: "网页摘要：把概念复习和练习反馈结合起来。"
            }
          ],
          trace_id: "trace_home_tutor_test"
        }
      );

      return {
        data: {
          data: makeSessionDetail("501", createdSession.title, sentMessages),
          trace_id: "trace_message_test"
        },
        status: 200,
        statusText: "OK",
        headers: {},
        config
      };
    }

    if (url === AGENT_ENDPOINTS.trace("trace_home_tutor_test") && method === "get") {
      return {
        data: {
          data: {
            trace_id: "trace_home_tutor_test",
            workflow: "home_tutor",
            artifact_type: "home_answer",
            artifact_id: "a-2",
            course_id: null,
            status: "completed",
            steps: [
              {
                id: "step-profile",
                agent_name: "context",
                step_index: 1,
                status: "completed",
                input_summary: "读取主页画像与会话上下文",
                output_summary: "识别学习目标和当前问题",
                duration_ms: 12,
                metadata: {
                  context_message_count: 2,
                  context_summary_used: false,
                  retrieval_query_mode: "contextual"
                },
                created_at: "2026-07-03T12:00:02Z"
              },
              {
                id: "step-review",
                agent_name: "review",
                step_index: 7,
                status: "completed",
                input_summary: "审核回答",
                output_summary: "确认不展示原始思维链",
                duration_ms: 9,
                metadata: {},
                created_at: "2026-07-03T12:00:03Z"
              }
            ]
          },
          trace_id: "trace_home_tutor_test"
        },
        status: 200,
        statusText: "OK",
        headers: {},
        config
      };
    }

    if (url === COURSE_ENDPOINTS.fromMaterialsJobs && method === "post") {
      return {
        data: {
          data: makeCompletedAiJob({ workflow: "course_builder", course_id: null, result: { course_id: "909" } }),
          trace_id: "trace_course_create_test"
        },
        status: 200,
        statusText: "OK",
        headers: {},
        config
      };
    }

    return {
      data: {
        data: {},
        trace_id: "trace_default_test"
      },
      status: 200,
      statusText: "OK",
      headers: {},
      config
    };
  };

  useAuthStore.getState().setSession({
    token: "dashboard-token",
    user: {
      id: 1,
      account: "student",
      displayName: summary.profile_summary.display_name,
      role: "student",
      starterMode: summary.profile_summary.starter_mode
    }
  });

  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={initialEntries}>
        <Routes>
          <Route path={PATHS.app} element={<LearningSpacePage />} />
          <Route path={PATHS.courseDetail} element={<div>已进入生成课程</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );

  return { calls };
}

describe("LearningSpacePage", () => {
  it("restores only active course-building jobs and never reopens an old failed job", () => {
    expect(isRestorableCourseBuilderJob({ workflow: "course_builder", status: "queued" })).toBe(true);
    expect(isRestorableCourseBuilderJob({ workflow: "course_builder", status: "running" })).toBe(true);
    expect(isRestorableCourseBuilderJob({ workflow: "course_builder", status: "cancelling" })).toBe(true);
    expect(isRestorableCourseBuilderJob({ workflow: "course_builder", status: "failed" })).toBe(false);
    expect(isRestorableCourseBuilderJob({ workflow: "course_builder", status: "completed" })).toBe(false);
    expect(isRestorableCourseBuilderJob({ workflow: "path_planning", status: "running" })).toBe(false);
  });
  beforeEach(() => {
    previousAdapter = apiClient.defaults.adapter;
    previousFetch = globalThis.fetch;
    localStorage.clear();
    useAuthStore.getState().clearSession();
  });

  afterEach(() => {
    apiClient.defaults.adapter = previousAdapter;
    globalThis.fetch = previousFetch;
    Reflect.deleteProperty(window, "SpeechRecognition");
    Reflect.deleteProperty(window, "webkitSpeechRecognition");
    Reflect.deleteProperty(window, "speechSynthesis");
    Reflect.deleteProperty(globalThis, "SpeechSynthesisUtterance");
    useAuthStore.getState().clearSession();
  });

  it("loads the home summary from the dashboard API instead of static starter courses", async () => {
    const { calls } = renderWithDashboardSummary();

    expect(await screen.findByRole("link", { name: /真实机器学习课/ }, { timeout: 5_000 })).toHaveAttribute("href", "/app/courses/101");
    expect(screen.getByRole("button", { name: "全部课程" })).toHaveAttribute("aria-expanded", "false");
    expect(screen.getByRole("button", { name: /接口里的主页历史/ })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Python 基础补齐/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "快捷学习建议" })).not.toBeInTheDocument();
    expect(screen.queryByText("根据真实资料复习")).not.toBeInTheDocument();
    expect(calls.map((call) => call.url)).toContain(DASHBOARD_ENDPOINTS.summary);
  });

  it("opens the complete course drawer on demand and supports search, close, retry, and course navigation", async () => {
    const user = userEvent.setup();
    const { calls } = renderWithDashboardSummary(starterSummary, { courseListFailures: 1 });

    expect(calls.map((call) => call.url)).not.toContain(COURSE_ENDPOINTS.list);
    await user.click(await screen.findByRole("button", { name: "全部课程" }));

    const drawer = await screen.findByRole("dialog", { name: "全部课程" });
    expect(await within(drawer).findByText("课程列表暂时没有读取成功")).toBeInTheDocument();
    await user.click(within(drawer).getByRole("button", { name: "重新读取" }));

    expect(await within(drawer).findByRole("link", { name: "打开课程真实机器学习课" })).toBeInTheDocument();
    expect(within(drawer).getByText("2 门课程")).toBeInTheDocument();
    await user.type(within(drawer).getByRole("textbox", { name: "搜索课程" }), "数据结构");
    expect(within(drawer).queryByRole("link", { name: "打开课程真实机器学习课" })).not.toBeInTheDocument();
    expect(within(drawer).getByRole("link", { name: "打开课程数据结构复习" })).toBeInTheDocument();

    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog", { name: "全部课程" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "全部课程" }));
    await user.click(await screen.findByRole("link", { name: "打开课程数据结构复习" }));
    expect(await screen.findByText("已进入生成课程")).toBeInTheDocument();
  }, 15_000);

  it("keeps blank dashboard summaries free of static materials and starter history", async () => {
    const user = userEvent.setup();
    const { calls } = renderWithDashboardSummary(blankSummary);

    expect(await screen.findByText("还没有课程")).toBeInTheDocument();
    expect(screen.getByText("还没有历史对话")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /人工智能导论/ })).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "打开资料库" }));

    expect(screen.getByRole("dialog", { name: "资料库" })).toHaveTextContent("资料库还是空的");
    expect(screen.queryByRole("button", { name: /神经网络课堂讲义/ })).not.toBeInTheDocument();
    expect(calls.map((call) => call.url)).toContain(DASHBOARD_ENDPOINTS.summary);
  });

  it("renders a calm conversation-first learning home without dashboard rails", async () => {
    renderWithDashboardSummary();

    expect(document.querySelector(".home-learning-surface")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "嗨，示例学生，准备好一起学习了吗？" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "历史对话" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "AI 学习入口" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "最近学习" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "学习问题输入" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "打开资料库" })).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: /真实机器学习课/ })).toHaveAttribute("href", "/app/courses/101");
    expect((await screen.findAllByText("学习知识点：监督学习")).length).toBeGreaterThanOrEqual(2);
    expect(screen.getByRole("link", { name: "下一步：学习知识点：监督学习" })).toHaveAttribute("href", "/app/courses/101?mode=study&view=overview&knowledge_point_id=88&guided=1");
    expect(screen.getByText("0 / 8")).toBeInTheDocument();
    expect(screen.getByRole("list", { name: "最近学习列表" })).toBeInTheDocument();
    expect(screen.getAllByRole("listitem")).toHaveLength(1);
    expect(screen.queryByRole("region", { name: "资料库轻入口" })).not.toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "知识学习画布" })).not.toBeInTheDocument();
  });

  it("opens the course generation overlay from the home input", async () => {
    const user = userEvent.setup();

    renderWithDashboardSummary();

    await screen.findByRole("link", { name: /真实机器学习课/ });
    await user.click(screen.getByRole("button", { name: "生成课程" }));

    const dialog = screen.getByRole("dialog", { name: "从资料生成课程" });

    expect(dialog).toBeInTheDocument();
    expect(within(dialog).getByRole("textbox", { name: "课程名称" })).toHaveValue("我的资料课程");
    expect(within(dialog).getByRole("button", { name: /真实资料讲义.md/ })).toHaveAttribute("aria-pressed", "false");
    expect(within(dialog).getByText("先选择要生成课程的资料")).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "生成课程" })).toBeDisabled();
  });

  it("keeps the edge rail focused on chat history and account actions", () => {
    renderWithDashboardSummary();

    const historyRail = screen.getByRole("region", { name: "历史对话" });

    expect(within(historyRail).queryByRole("link", { name: /学习空间/ })).not.toBeInTheDocument();
    expect(within(historyRail).getByRole("link", { name: "资料库" })).toHaveAttribute("href", "/app/library");
    expect(within(historyRail).getByRole("link", { name: "资源工坊" })).toHaveAttribute("href", "/app/studio");
    expect(within(historyRail).getByRole("link", { name: "学习画像" })).toHaveAttribute("href", "/app/profile");
    expect(within(historyRail).queryByRole("link", { name: "个人资料" })).not.toBeInTheDocument();
    expect(within(historyRail).getByRole("link", { name: "设置" })).toHaveAttribute("href", "/app/settings");
    expect(within(historyRail).getByRole("button", { name: "退出登录" })).toBeInTheDocument();
  });

  it("opens history search as an overlay without squeezing the sidebar", async () => {
    const user = userEvent.setup();

    renderWithDashboardSummary();

    const historyRail = screen.getByRole("region", { name: "历史对话" });

    await screen.findByRole("button", { name: /接口里的主页历史/ });
    await user.click(within(historyRail).getByRole("button", { name: "搜索历史" }));

    const searchDialog = screen.getByRole("dialog", { name: "搜索历史" });
    const searchInput = within(searchDialog).getByRole("searchbox", { name: "搜索历史关键词" });

    await user.type(searchInput, "接口");

    expect(within(historyRail).queryByRole("searchbox", { name: "搜索历史关键词" })).not.toBeInTheDocument();
    expect(within(historyRail).getByRole("button", { name: /接口里的主页历史/, hidden: true })).toBeInTheDocument();
    expect(within(searchDialog).getByRole("button", { name: /接口里的主页历史/ })).toBeInTheDocument();
  });

  it("keeps an older home history item in place after selecting it", async () => {
    const user = userEvent.setup();
    const firstThread = {
      id: "501",
      title: "上方主页历史",
      meta: "刚刚",
      scope: "home" as const,
      updated_at: "2026-07-03T12:00:00Z"
    };
    const secondThread = {
      id: "502",
      title: "下方主页历史",
      meta: "昨天",
      scope: "home" as const,
      updated_at: "2026-07-02T12:00:00Z"
    };

    renderWithDashboardSummary(
      {
        ...starterSummary,
        recent_conversations: [firstThread, secondThread]
      },
      {
        historyDetails: {
          "502": makeSessionDetail("502", "下方主页历史", [
            { id: "u-502", role: "user", content: "下方历史问题" },
            { id: "a-502", role: "assistant", content: "下方历史回答" }
          ])
        }
      }
    );

    const historyRail = await screen.findByRole("region", { name: "历史对话" });
    expect((await within(historyRail).findAllByRole("button", { name: /主页历史/ })).map((button) => button.textContent)).toEqual([
      "上方主页历史2026-07-03",
      "下方主页历史2026-07-02"
    ]);

    await user.click(within(historyRail).getByRole("button", { name: /下方主页历史/ }));

    expect(await screen.findByText("下方历史问题")).toBeInTheDocument();
    expect(within(historyRail).getAllByRole("button", { name: /主页历史/ }).map((button) => button.textContent)).toEqual([
      "上方主页历史2026-07-03",
      "下方主页历史2026-07-02"
    ]);
  });

  it("keeps the open history menu layered above neighboring conversations", async () => {
    const user = userEvent.setup();
    const firstThread = {
      id: "501",
      title: "上方主页历史",
      meta: "刚刚",
      scope: "home" as const,
      updated_at: "2026-07-03T12:00:00Z"
    };
    const secondThread = {
      id: "502",
      title: "下方主页历史",
      meta: "昨天",
      scope: "home" as const,
      updated_at: "2026-07-02T12:00:00Z"
    };

    renderWithDashboardSummary({
      ...starterSummary,
      recent_conversations: [firstThread, secondThread]
    });

    const historyRail = await screen.findByRole("region", { name: "历史对话" });
    const upperThreadButton = await within(historyRail).findByRole("button", { name: /上方主页历史/ });
    const lowerThreadButton = within(historyRail).getByRole("button", { name: /下方主页历史/ });

    await user.click(within(historyRail).getByRole("button", { name: "打开会话操作菜单 501" }));

    expect(screen.getByRole("menu", { name: "会话操作" })).toBeInTheDocument();
    expect(upperThreadButton.closest(".home-thread")).toHaveAttribute("data-menu-open", "true");
    expect(lowerThreadButton.closest(".home-thread")).toHaveAttribute("data-menu-open", "false");
  });

  it("opens a home history thread passed from secondary route navigation", async () => {
    renderWithDashboardSummary(
      starterSummary,
      {
        historyDetails: {
          "501": makeSessionDetail("501", "接口里的主页历史", [
            { id: "u-501", role: "user", content: "从画像页点回来的问题" },
            { id: "a-501", role: "assistant", content: "从画像页点回来的回答" }
          ])
        }
      },
      [{ pathname: PATHS.app, state: { selectedHomeThreadId: "501" } }]
    );

    const thread = await screen.findByRole("region", { name: "主页对话" });

    expect(within(thread).getByText("从画像页点回来的问题")).toBeInTheDocument();
    expect(within(thread).getByText("从画像页点回来的回答")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /接口里的主页历史/ })).toHaveAttribute("aria-pressed", "true");
  });

  it("restores the active home session and its materials after a refresh URL", async () => {
    renderWithDashboardSummary(
      starterSummary,
      {
        historyDetail: makeSessionDetail("501", "刷新恢复会话", [
          { id: "u-refresh", role: "user", content: "刷新前的问题" },
          { id: "a-refresh", role: "assistant", content: "刷新后仍可见的回答", trace_id: "trace_home_tutor_test" }
        ], [201])
      },
      ["/app?session_id=501"]
    );

    expect(await screen.findByText("刷新前的问题")).toBeInTheDocument();
    expect(await screen.findByText("协作完成")).toBeInTheDocument();
    const composer = within(screen.getByRole("region", { name: "底部学习输入" }));
    expect(composer.getByText("真实资料讲义.md")).toBeInTheDocument();
    expect(composer.getByText("共 1 份")).toBeInTheDocument();
  });

  it("filters materials inside the home library drawer", async () => {
    const user = userEvent.setup();

    renderWithDashboardSummary(materialRichSummary);

    await screen.findByRole("link", { name: /真实机器学习课/ });
    await user.click(screen.getByRole("button", { name: "打开资料库" }));

    const dialog = screen.getByRole("dialog", { name: "资料库" });
    await user.type(within(dialog).getByRole("textbox", { name: "搜索资料" }), "期末");

    expect(within(dialog).getByRole("button", { name: /期末复习题 2025/ })).toBeInTheDocument();
    expect(within(dialog).queryByRole("button", { name: /神经网络课堂讲义/ })).not.toBeInTheDocument();
  });

  it("collapses the edge history sidebar without leaving the learning home", async () => {
    const user = userEvent.setup();

    renderWithDashboardSummary();

    const historyRail = screen.getByRole("region", { name: "历史对话" });

    expect(historyRail).toHaveAttribute("data-collapsed", "false");

    await user.click(screen.getByRole("button", { name: "收起侧栏" }));

    expect(historyRail).toHaveAttribute("data-collapsed", "true");
    expect(screen.getByRole("button", { name: "展开侧栏" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "AI 学习入口" })).toBeInTheDocument();
  });

  it("moves into a chat thread after the first home question", async () => {
    const user = userEvent.setup();

    renderWithDashboardSummary();

    await user.type(screen.getByRole("textbox", { name: "学习问题输入" }), "期末复习怎么安排？");
    await user.click(screen.getByRole("button", { name: "发送" }));

    const thread = screen.getByRole("region", { name: "主页对话" });

    expect(within(thread).getByText("期末复习怎么安排？")).toBeInTheDocument();
    expect(within(thread).getByRole("heading", { name: "学习建议" })).toBeInTheDocument();
    expect(within(thread).getByText(/先把学习目标拆成三步/)).toBeInTheDocument();
    expect(within(thread).queryByRole("region", { name: "回答展开详情" })).not.toBeInTheDocument();
    await user.click(within(thread).getByRole("button", { name: "来源" }));
    expect(within(thread).getByRole("region", { name: "回答展开详情" })).toHaveTextContent("来源");
    expect(screen.getByRole("region", { name: "底部学习输入" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /期末复习怎么安排/ })).toHaveAttribute("aria-pressed", "true");
    expect(screen.queryByText("已生成回答。")).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /准备好一起学习了吗/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "下一步学习" })).not.toBeInTheDocument();
  });

  it("keeps selected material state and removes manual capability toggles", async () => {
    const user = userEvent.setup();

    renderWithDashboardSummary(starterSummary);

    await user.click(screen.getByRole("button", { name: "打开资料库" }));
    await user.click(screen.getByRole("button", { name: /真实资料讲义.md/ }));
    await user.click(screen.getByRole("button", { name: "作为本次对话参考" }));
    const composer = screen.getByRole("region", { name: "学习输入区" });

    expect(within(composer).getByText("真实资料讲义.md")).toBeInTheDocument();
    expect(within(composer).getByText("共 1 份")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "联网搜索" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "深度思考" })).not.toBeInTheDocument();
  });

  it("restores a material selected from the library navigation state", async () => {
    renderWithDashboardSummary(materialRichSummary, {}, [{ pathname: PATHS.app, state: { selectedMaterialIds: ["203"] } }]);

    const drawer = await screen.findByRole("dialog", { name: "资料库" });
    expect(await within(drawer).findByRole("button", { name: /神经网络课堂讲义/ })).toHaveAttribute("aria-pressed", "true");
    expect(screen.queryByText("共 1 份")).not.toBeInTheDocument();
    await userEvent.click(within(drawer).getByRole("button", { name: "作为本次对话参考" }));
    expect(await screen.findByText("共 1 份")).toBeInTheDocument();
  });

  it("does not change conversation materials when the library draft is cancelled", async () => {
    const user = userEvent.setup();
    const { calls } = renderWithDashboardSummary(materialRichSummary);

    await user.click(screen.getByRole("button", { name: "打开资料库" }));
    await user.click(screen.getByRole("button", { name: /期末复习题 2025/ }));
    await user.click(screen.getByRole("button", { name: "关闭资料库" }));

    expect(screen.queryByText("共 1 份")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "打开资料库" }));
    expect(screen.getByRole("button", { name: /期末复习题 2025/ })).toHaveAttribute("aria-pressed", "false");
    expect(calls).not.toContainEqual(expect.objectContaining({
      method: "patch",
      payload: expect.objectContaining({ selected_material_ids: expect.any(Array) })
    }));
  });

  it("keeps the material draft open when saving session context fails", async () => {
    const user = userEvent.setup();
    renderWithDashboardSummary(starterSummary, { failMaterialSave: true });
    await user.click(await screen.findByRole("button", { name: /接口里的主页历史/ }));
    await user.click(screen.getByRole("button", { name: "打开资料库" }));
    await user.click(screen.getByRole("button", { name: /真实资料讲义.md/ }));
    await user.click(screen.getByRole("button", { name: "作为本次对话参考" }));

    expect(screen.getByRole("dialog", { name: "资料库" })).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("参考资料保存失败");
    expect(screen.queryByText("共 1 份")).not.toBeInTheDocument();
  });

  it("keeps course generation materials separate from conversation context", async () => {
    const user = userEvent.setup();
    renderWithDashboardSummary(materialRichSummary);
    await user.click(screen.getByRole("button", { name: "打开资料库" }));
    await user.click(screen.getByRole("button", { name: /真实资料讲义.md/ }));
    await user.click(screen.getByRole("button", { name: "作为本次对话参考" }));

    await user.click(screen.getByRole("button", { name: "生成课程" }));
    const courseDialog = screen.getByRole("dialog", { name: "从资料生成课程" });
    await user.click(within(courseDialog).getByRole("button", { name: /真实资料讲义.md/ }));
    await user.click(within(courseDialog).getByRole("button", { name: /期末复习题 2025/ }));
    expect(within(courseDialog).getByText("已选择 1 份资料")).toBeInTheDocument();
    await user.click(within(courseDialog).getByRole("button", { name: "关闭生成课程" }));

    const composer = within(screen.getByRole("region", { name: "学习输入区" }));
    expect(composer.getByText("真实资料讲义.md")).toBeInTheDocument();
    expect(composer.queryByText("期末复习题 2025.pdf")).not.toBeInTheDocument();
  });

  it("sends no manual tool flags and shows automatically selected sources", async () => {
    const user = userEvent.setup();
    const { calls } = renderWithDashboardSummary(materialRichSummary);

    await user.click(screen.getByRole("button", { name: "打开资料库" }));
    await user.click(screen.getByRole("button", { name: /期末复习题 2025/ }));
    await user.click(screen.getByRole("button", { name: "作为本次对话参考" }));
    await user.type(screen.getByRole("textbox", { name: "学习问题输入" }), "结合资料和最新趋势怎么复习？");
    await user.click(screen.getByRole("button", { name: "发送" }));

    const messageCall = calls.find((call) => call.method === "post" && call.url === TUTOR_ENDPOINTS.stream(501));

    expect(messageCall?.payload).toEqual({ message: "结合资料和最新趋势怎么复习？" });
    expect(messageCall?.payload).not.toHaveProperty("selected_material_ids");
    expect(calls).toContainEqual(expect.objectContaining({
      method: "post",
      url: TUTOR_ENDPOINTS.sessions,
      payload: expect.objectContaining({ selected_material_ids: [202] })
    }));

    const thread = screen.getByRole("region", { name: "主页对话" });

    await user.click(within(thread).getByRole("button", { name: "来源" }));
    expect(within(thread).getByRole("region", { name: "回答展开详情" })).toHaveTextContent("真实资料讲义.md");
    expect(within(thread).getByRole("region", { name: "回答展开详情" })).toHaveTextContent("联网搜索结果");

    expect(within(thread).getByRole("button", { name: "协作轨迹" })).toBeInTheDocument();
  });

  it("does not fall back to browser cloud speech when local capture or synthesis is unavailable", async () => {
    const user = userEvent.setup();
    const speakSpy = vi.fn();
    const cancelSpy = vi.fn();

    class MockSpeechRecognition {
      lang = "";
      interimResults = false;
      maxAlternatives = 1;
      onresult: ((event: { results: Array<Array<{ transcript: string }>> }) => void) | null = null;
      onerror: (() => void) | null = null;
      onend: (() => void) | null = null;

      start() {
        this.onresult?.({ results: [[{ transcript: "语音输入的问题" }]] });
        this.onend?.();
      }

      stop() {
        this.onend?.();
      }
    }

    Object.defineProperty(window, "webkitSpeechRecognition", {
      configurable: true,
      value: MockSpeechRecognition
    });
    Object.defineProperty(window, "speechSynthesis", {
      configurable: true,
      value: {
        cancel: cancelSpy,
        speak: speakSpy,
        getVoices: () => [],
        addEventListener: vi.fn(),
        removeEventListener: vi.fn()
      }
    });
    Object.defineProperty(globalThis, "SpeechSynthesisUtterance", {
      configurable: true,
      value: class {
        lang = "";

        constructor(public text: string) {}
      }
    });

    renderWithDashboardSummary();

    await user.click(screen.getByRole("button", { name: "语音输入" }));

    expect(screen.getByRole("textbox", { name: "学习问题输入" })).toHaveValue("");
    expect(screen.queryByText("已识别语音输入，确认后再发送。")).not.toBeInTheDocument();

    await user.type(screen.getByRole("textbox", { name: "学习问题输入" }), "手动输入的问题");
    await user.click(screen.getByRole("button", { name: "发送" }));
    await user.click(await screen.findByRole("button", { name: "朗读回答" }));

    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("未检测到本地中文声音"), { timeout: 3000 });
    expect(speakSpy).not.toHaveBeenCalled();
    expect(cancelSpy).toHaveBeenCalled();
  });

  it("shows a non-blocking warning when the browser does not support voice input", async () => {
    const user = userEvent.setup();

    renderWithDashboardSummary();

    await user.click(screen.getByRole("button", { name: "语音输入" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("当前页面无法录音，请使用HTTPS或本机地址并允许麦克风权限。");
    expect(screen.getByRole("textbox", { name: "学习问题输入" })).toHaveValue("");
  });

  it("creates a persistent home session before the first send and reuses it for follow-ups", async () => {
    const user = userEvent.setup();

    const { calls } = renderWithDashboardSummary(blankSummary);
    const input = screen.getByRole("textbox", { name: "学习问题输入" });

    await user.type(input, "第一轮复习怎么开始？");
    await user.click(screen.getByRole("button", { name: "发送" }));

    expect(await screen.findAllByText("第一轮复习怎么开始？")).not.toHaveLength(0);

    await user.type(input, "那第二步做什么？");
    await user.click(screen.getByRole("button", { name: "发送" }));

    expect(await screen.findByText("那第二步做什么？")).toBeInTheDocument();

    const createCalls = calls.filter((call) => call.method === "post" && call.url === TUTOR_ENDPOINTS.sessions);
    const messageCalls = calls.filter((call) => call.method === "post" && call.url === TUTOR_ENDPOINTS.stream(501));

    expect(createCalls).toHaveLength(1);
    expect(createCalls[0].payload).toMatchObject({
      scope: "home",
      course_id: null,
      mode: "chat",
      title: "第一轮复习怎么开始？"
    });
    expect(messageCalls).toHaveLength(2);
    expect(messageCalls[0].payload).toMatchObject({ message: "第一轮复习怎么开始？" });
    expect(messageCalls[1].payload).toMatchObject({ message: "那第二步做什么？" });
  });

  it("loads persisted messages when selecting a home history thread", async () => {
    const user = userEvent.setup();

    const { calls } = renderWithDashboardSummary(starterSummary, {
      historyDetail: makeSessionDetail("501", "接口里的主页历史", [
        { id: "u-501", role: "user", content: "后端保存的问题" },
        { id: "a-501", role: "assistant", content: "后端保存的回答" }
      ], [201])
    });

    await user.click(await screen.findByRole("button", { name: /接口里的主页历史/ }));

    const thread = await screen.findByRole("region", { name: "主页对话" });

    expect(within(thread).getByText("后端保存的问题")).toBeInTheDocument();
    expect(within(thread).getByText("后端保存的回答")).toBeInTheDocument();
    expect(within(screen.getByRole("region", { name: "底部学习输入" })).getByText("真实资料讲义.md")).toBeInTheDocument();
    expect(calls).toContainEqual(expect.objectContaining({ method: "get", url: TUTOR_ENDPOINTS.detail(501) }));
  });

  it("hides legacy prompt echoes when loading an older home answer", async () => {
    const user = userEvent.setup();

    renderWithDashboardSummary(starterSummary, {
      historyDetail: makeSessionDetail("501", "接口里的主页历史", [
        { id: "u-legacy", role: "user", content: "什么是机器学习？" },
        {
          id: "a-legacy",
          role: "assistant",
          content:
            "学生问题：什么是机器学习？ 工具状态：联网未配置 可用来源摘要：资料开头 最终回答：## 机器学习\n\n机器学习让系统从数据中归纳规律。"
        }
      ])
    });

    await user.click(await screen.findByRole("button", { name: /接口里的主页历史/ }));

    const thread = await screen.findByRole("region", { name: "主页对话" });
    expect(within(thread).getByRole("heading", { name: "机器学习" })).toBeInTheDocument();
    expect(within(thread).getByText("机器学习让系统从数据中归纳规律。")).toBeInTheDocument();
    expect(within(thread).queryByText(/工具状态/)).not.toBeInTheDocument();
  });

  it("applies review replacement and keeps tool warnings inside the source panel", async () => {
    const user = userEvent.setup();

    renderWithDashboardSummary(blankSummary, {
      streamReplacement: "## 审核后的回答\n\n这是修订后的安全正文。",
      streamWarnings: ["联网搜索未配置，未返回网页来源。"]
    });

    await user.type(screen.getByRole("textbox", { name: "学习问题输入" }), "给我一个最新案例");
    await user.click(screen.getByRole("button", { name: "发送" }));

    const thread = await screen.findByRole("region", { name: "主页对话" });
    expect(within(thread).getByRole("heading", { name: "审核后的回答" })).toBeInTheDocument();
    expect(within(thread).queryByRole("heading", { name: "学习建议" })).not.toBeInTheDocument();
    expect(within(thread).queryByText("已思考若干秒")).not.toBeInTheDocument();

    await user.click(within(thread).getByRole("button", { name: "来源" }));
    expect(within(thread).getByRole("list", { name: "工具提示" })).toHaveTextContent("联网搜索未配置");
  });

  it("renames a home history conversation from the sidebar menu", async () => {
    const user = userEvent.setup();
    const { calls } = renderWithDashboardSummary(starterSummary);

    const historyRail = await screen.findByRole("region", { name: "历史对话" });
    expect(await within(historyRail).findByRole("button", { name: /接口里的主页历史/ })).toBeInTheDocument();

    await user.click(within(historyRail).getByRole("button", { name: "打开会话操作菜单 501" }));
    await user.click(screen.getByRole("menuitem", { name: "重命名" }));

    const titleInput = screen.getByRole("textbox", { name: "会话名称" });
    await user.clear(titleInput);
    await user.type(titleInput, "改名后的主页历史");
    await user.click(screen.getByRole("button", { name: "保存会话名称" }));

    expect(await within(historyRail).findByRole("button", { name: /改名后的主页历史/ })).toBeInTheDocument();
    expect(within(historyRail).queryByRole("button", { name: /接口里的主页历史/ })).not.toBeInTheDocument();
    await waitFor(() => {
      expect(calls).toContainEqual(
        expect.objectContaining({
          method: "patch",
          url: TUTOR_ENDPOINTS.detail(501),
          payload: { title: "改名后的主页历史" }
        })
      );
    });
  });

  it("deletes the active home history conversation and returns to the default home", async () => {
    const user = userEvent.setup();
    const { calls } = renderWithDashboardSummary(starterSummary);

    const historyRail = await screen.findByRole("region", { name: "历史对话" });
    await user.click(await within(historyRail).findByRole("button", { name: /接口里的主页历史/ }));
    expect(await screen.findByRole("region", { name: "主页对话" })).toBeInTheDocument();

    await user.click(within(historyRail).getByRole("button", { name: "打开会话操作菜单 501" }));
    await user.click(screen.getByRole("menuitem", { name: "删除" }));
    await user.click(screen.getByRole("menuitem", { name: "确认删除" }));

    expect(await screen.findByRole("heading", { name: "嗨，示例学生，准备好一起学习了吗？" })).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "主页对话" })).not.toBeInTheDocument();
    expect(within(historyRail).queryByRole("button", { name: /接口里的主页历史/ })).not.toBeInTheDocument();
    await waitFor(() => {
      expect(calls).toContainEqual(
        expect.objectContaining({
          method: "delete",
          url: TUTOR_ENDPOINTS.detail(501)
        })
      );
    });
  });

  it("returns to the default learning home when clicking the EduNova brand from a thread", async () => {
    const user = userEvent.setup();

    renderWithDashboardSummary(starterSummary);

    await user.click(await screen.findByRole("button", { name: /接口里的主页历史/ }));

    expect(await screen.findByRole("region", { name: "主页对话" })).toBeInTheDocument();

    await user.click(screen.getByRole("link", { name: "EduNova 首页" }));

    expect(screen.getByRole("heading", { name: "嗨，示例学生，准备好一起学习了吗？" })).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "主页对话" })).not.toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "学习问题输入" })).toHaveValue("");
    expect(screen.getByRole("region", { name: "历史对话" })).toHaveAttribute("data-collapsed", "false");
    expect(screen.getByRole("button", { name: /接口里的主页历史/ })).toHaveAttribute("aria-pressed", "false");
  });

  it("keeps the typed question when persistent message sending fails", async () => {
    const user = userEvent.setup();

    renderWithDashboardSummary(blankSummary, { failMessageSend: true });

    const input = screen.getByRole("textbox", { name: "学习问题输入" });
    await user.type(input, "这次发送会失败吗？");
    await user.click(screen.getByRole("button", { name: "发送" }));

    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    expect(await screen.findByRole("alert")).toHaveTextContent("模型暂不可用，请检查设置或稍后重试。");
    expect(input).toHaveValue("这次发送会失败吗？");
    expect(screen.queryByRole("region", { name: "主页对话" })).not.toBeInTheDocument();
  });

  it("keeps follow-up questions inside the active home thread", async () => {
    const user = userEvent.setup();

    renderWithDashboardSummary(blankSummary);

    const historyRail = screen.getByRole("region", { name: "历史对话" });
    const initialThreadCount = historyRail.querySelectorAll("button[aria-pressed]").length;
    const input = screen.getByRole("textbox", { name: "学习问题输入" });

    await user.type(input, "第一轮复习怎么开始？");
    await user.click(screen.getByRole("button", { name: "发送" }));

    const firstQuestionThread = within(historyRail).getByRole("button", { name: /第一轮复习怎么开始/ });

    expect(firstQuestionThread).toHaveAttribute("aria-pressed", "true");
    expect(historyRail.querySelectorAll("button[aria-pressed]")).toHaveLength(initialThreadCount + 1);

    await user.type(input, "那第二步做什么？");
    await user.click(screen.getByRole("button", { name: "发送" }));

    expect(within(screen.getByRole("region", { name: "主页对话" })).getByText("那第二步做什么？")).toBeInTheDocument();
    expect(firstQuestionThread).toHaveAttribute("aria-pressed", "true");
    expect(within(historyRail).queryByRole("button", { name: /那第二步做什么/ })).not.toBeInTheDocument();
    expect(historyRail.querySelectorAll("button[aria-pressed]")).toHaveLength(initialThreadCount + 1);
  });

  it("shows the home answer collaboration trace alongside sources and explanation", async () => {
    const user = userEvent.setup();

    renderWithDashboardSummary(starterSummary);

    await screen.findByRole("link", { name: /真实机器学习课/ });
    const input = screen.getByRole("textbox", { name: "学习问题输入" });
    await user.type(input, "把反向传播讲到我能做题");
    expect(input).toHaveValue("把反向传播讲到我能做题");

    await user.click(screen.getByRole("button", { name: "发送" }));
    expect(screen.queryByRole("button", { name: "学习路径" })).not.toBeInTheDocument();

    expect(screen.getByRole("button", { name: "协作轨迹" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "为什么这样回答" })).toBeInTheDocument();
  });

  it("creates a real course from the library drawer and enters the new course space", async () => {
    const user = userEvent.setup();

    const { calls } = renderWithDashboardSummary();

    await screen.findByRole("link", { name: /真实机器学习课/ });
    await user.click(screen.getByRole("button", { name: "打开资料库" }));

    const libraryDialog = screen.getByRole("dialog", { name: "资料库" });
    const attachButton = within(libraryDialog).getByRole("button", { name: "作为本次对话参考" });

    expect(attachButton).toBeDisabled();

    await user.click(within(libraryDialog).getByRole("button", { name: /真实资料讲义.md/ }));

    expect(attachButton).toBeEnabled();

    await user.click(within(libraryDialog).getByRole("button", { name: "生成课程" }));

    const courseDialog = screen.getByRole("dialog", { name: "从资料生成课程" });

    expect(screen.getAllByRole("dialog")).toHaveLength(1);
    expect(screen.queryByRole("dialog", { name: "资料库" })).not.toBeInTheDocument();
    expect(within(courseDialog).getByText("已选择 1 份资料")).toBeInTheDocument();
    expect(within(courseDialog).getByRole("button", { name: "生成课程" })).toBeEnabled();

    await user.click(within(courseDialog).getByRole("button", { name: "生成课程" }));

    expect(await screen.findByText("已进入生成课程")).toBeInTheDocument();
    expect(calls).toContainEqual(
      expect.objectContaining({
        method: "post",
        url: COURSE_ENDPOINTS.fromMaterialsJobs,
        payload: {
          material_ids: [201],
          course_title: "我的资料课程"
        }
      })
    );
  });

  it("keeps blank starter accounts empty until they upload their own material", async () => {
    const user = userEvent.setup();

    renderWithDashboardSummary(blankSummary);

    expect(await screen.findByText("还没有课程")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /人工智能导论/ })).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "打开资料库" }));

    expect(screen.getByRole("dialog", { name: "资料库" })).toHaveTextContent("资料库还是空的");
  });

  it("uploads home materials through the materials API and refreshes dashboard materials", async () => {
    const user = userEvent.setup();
    const calls: ApiCall[] = [];
    let uploaded = false;

    apiClient.defaults.adapter = async (config) => {
      const method = (config.method ?? "get").toLowerCase();
      const url = config.url ?? "";
      calls.push({ method, url, payload: config.data });

      if (url === DASHBOARD_ENDPOINTS.summary) {
        return {
          data: {
            data: uploaded
              ? {
                  ...blankSummary,
                  material_library_summary: { material_count: 1, unassigned_count: 1 },
                  recent_materials: [
                    {
                      id: "901",
                      title: "真实上传资料.txt",
                      type: "TXT",
                      detail: "已解析",
                      modified: "今天",
                      size: "14 B"
                    }
                  ]
                }
              : blankSummary,
            trace_id: "trace_dashboard_after_upload"
          },
          status: 200,
          statusText: "OK",
          headers: {},
          config
        };
      }

      if (url === MATERIAL_ENDPOINTS.upload && method === "post") {
        uploaded = true;
        return {
          data: {
            data: {
              id: "901",
              material_id: 901,
              course_id: null,
              filename: "真实上传资料.txt",
              title: "真实上传资料.txt",
              type: "TXT",
              detail: "已解析",
              modified: "今天",
              size: "14 B",
              parse_status: "completed"
            },
            trace_id: "trace_material_upload"
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

    useAuthStore.getState().setSession({
      token: "material-upload-token",
      user: {
        id: 1,
        account: "student",
        displayName: "资料学生",
        role: "student",
        starterMode: "blank"
      }
    });

    render(
      <QueryClientProvider
        client={
          new QueryClient({
            defaultOptions: {
              queries: { retry: false }
            }
          })
        }
      >
        <MemoryRouter>
          <LearningSpacePage />
        </MemoryRouter>
      </QueryClientProvider>
    );

    await screen.findByText("还没有课程");
    await user.upload(screen.getByLabelText("上传资料文件"), new File(["反向传播资料"], "真实上传资料.txt", { type: "text/plain" }));

    expect(calls.filter((call) => call.method === "post" && call.url === MATERIAL_ENDPOINTS.upload)).toHaveLength(1);
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "打开资料库" }));
    expect(screen.getByRole("dialog", { name: "资料库" })).toHaveTextContent("真实上传资料.txt");
  });

  it("sends with Enter and keeps Shift Enter as a line break", async () => {
    const user = userEvent.setup();

    renderWithDashboardSummary();

    const input = screen.getByRole("textbox", { name: "学习问题输入" });

    await user.type(input, "第一行{Shift>}{Enter}{/Shift}第二行");

    expect(input).toHaveValue("第一行\n第二行");

    await user.keyboard("{Enter}");

    expect(screen.getByRole("region", { name: "主页对话" })).toHaveTextContent("第一行 第二行");
    expect(input).toHaveValue("");
  });
});

import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { PATHS } from "../app/routePaths";
import { AGENT_ENDPOINTS } from "../api/agents";
import { apiClient } from "../api/client";
import { COURSE_ENDPOINTS } from "../api/courses";
import { DASHBOARD_ENDPOINTS, type DashboardSummary } from "../api/dashboard";
import { MATERIAL_ENDPOINTS } from "../api/materials";
import { TUTOR_ENDPOINTS } from "../api/tutor";
import { useAuthStore } from "../features/auth/authStore";
import { LearningSpacePage } from "./LearningSpacePage";

const starterSummary: DashboardSummary = {
  profile_summary: {
    display_name: "示例学生",
    starter_mode: "ai_intro",
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

let previousAdapter = apiClient.defaults.adapter;

type ApiCall = {
  method: string;
  url: string;
  payload: unknown;
};

type TutorMockOptions = {
  failMessageSend?: boolean;
  historyDetail?: unknown;
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
  }>
) {
  return {
    session: {
      id: sessionId,
      scope: "home",
      course_id: null,
      title,
      mode: "chat",
      archived_from_home: false,
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

function renderWithDashboardSummary(summary: DashboardSummary = starterSummary, tutorOptions: TutorMockOptions = {}) {
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
    created_at: "2026-07-03T12:00:00Z",
    updated_at: "2026-07-03T12:00:00Z"
  };

  apiClient.defaults.adapter = async (config) => {
    const method = (config.method ?? "get").toLowerCase();
    const url = config.url ?? "";
    const payload = parsePayload(config.data);
    calls.push({ method, url, payload });

    if (url === DASHBOARD_ENDPOINTS.summary) {
      return {
        data: {
          data: summary,
          trace_id: "trace_dashboard_test"
        },
        status: 200,
        statusText: "OK",
        headers: {},
        config
      };
    }

    if (url === TUTOR_ENDPOINTS.sessions && method === "post") {
      const title = typeof payload === "object" && payload !== null && "title" in payload ? String(payload.title) : "主页第一问";
      createdSession.title = title;

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

    if (url === TUTOR_ENDPOINTS.detail(501) && method === "get") {
      return {
        data: {
          data:
            tutorOptions.historyDetail ??
            makeSessionDetail("501", "接口里的主页历史", [
              { id: "m1", role: "user", content: "后端保存的问题" },
              { id: "m2", role: "assistant", content: "后端保存的回答" }
            ]),
          trace_id: "trace_session_detail_test"
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
                agent_name: "home_profile",
                step_index: 1,
                status: "completed",
                input_summary: "读取主页画像",
                output_summary: "识别学习目标和当前问题",
                duration_ms: 12,
                metadata: {},
                created_at: "2026-07-03T12:00:02Z"
              },
              {
                id: "step-review",
                agent_name: "review",
                step_index: 5,
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

    if (url === COURSE_ENDPOINTS.fromMaterials && method === "post") {
      return {
        data: {
          data: {
            course: {
              id: "909",
              title: "神经网络冲刺课",
              description: "由 1 份资料生成",
              source_type: "uploaded",
              status: "ready",
              knowledge_point_count: 3,
              chunk_count: 8,
              material_count: 1
            },
            knowledge_points: []
          },
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
      email: "student@edunova.local",
      displayName: summary.profile_summary.display_name,
      role: "student",
      starterMode: summary.profile_summary.starter_mode
    }
  });

  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[PATHS.app]}>
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
  beforeEach(() => {
    previousAdapter = apiClient.defaults.adapter;
    localStorage.clear();
    useAuthStore.getState().clearSession();
  });

  afterEach(() => {
    apiClient.defaults.adapter = previousAdapter;
    Reflect.deleteProperty(window, "SpeechRecognition");
    Reflect.deleteProperty(window, "webkitSpeechRecognition");
    Reflect.deleteProperty(window, "speechSynthesis");
    Reflect.deleteProperty(globalThis, "SpeechSynthesisUtterance");
    useAuthStore.getState().clearSession();
  });

  it("loads the home summary from the dashboard API instead of static starter courses", async () => {
    const { calls } = renderWithDashboardSummary();

    expect(await screen.findByRole("link", { name: /真实机器学习课/ })).toHaveAttribute("href", "/app/courses/101");
    expect(screen.getByRole("link", { name: /期末冲刺/ })).toHaveAttribute("href", "/app/path?course_id=101");
    expect(screen.getByRole("button", { name: /接口里的主页历史/ })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Python 基础补齐/ })).not.toBeInTheDocument();
    expect(calls.map((call) => call.url)).toContain(DASHBOARD_ENDPOINTS.summary);
  });

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

  it("renders a calm ChatGPT-style learning home without dashboard rails", async () => {
    renderWithDashboardSummary();

    expect(screen.getByRole("heading", { name: "嗨，同学，准备好一起学习了吗？" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "历史对话" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "AI 学习入口" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "最近学习" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "学习问题输入" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "打开资料库" })).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: /真实机器学习课/ })).toHaveAttribute("href", "/app/courses/101");
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
    expect(within(dialog).getByRole("textbox", { name: "课程名称" })).toHaveValue("人工智能导论期末复习");
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
    expect(within(historyRail).getByRole("link", { name: "个人资料" })).toHaveAttribute("href", "/app/profile");
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
    expect(within(historyRail).getByRole("button", { name: /接口里的主页历史/ })).toBeInTheDocument();
    expect(within(searchDialog).getByRole("button", { name: /接口里的主页历史/ })).toBeInTheDocument();
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
    expect(within(thread).getByText(/模型回答：先把学习目标拆成三步/)).toBeInTheDocument();
    expect(within(thread).queryByRole("region", { name: "回答展开详情" })).not.toBeInTheDocument();
    await user.click(within(thread).getByRole("button", { name: "来源" }));
    expect(within(thread).getByRole("region", { name: "回答展开详情" })).toHaveTextContent("来源");
    expect(screen.getByRole("region", { name: "底部学习输入" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /期末复习怎么安排/ })).toHaveAttribute("aria-pressed", "true");
    expect(screen.queryByText("已生成回答。")).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "嗨，同学，准备好一起学习了吗？" })).not.toBeInTheDocument();
  });

  it("keeps selected material state inside the composer without web search copy", async () => {
    const user = userEvent.setup();

    renderWithDashboardSummary(starterSummary);

    await user.click(screen.getByRole("button", { name: "打开资料库" }));
    await user.click(screen.getByRole("button", { name: /真实资料讲义.md/ }));
    await user.click(screen.getByRole("button", { name: "关闭资料库" }));
    await user.click(screen.getByRole("button", { name: "联网搜索" }));

    const composer = screen.getByRole("region", { name: "学习输入区" });

    expect(within(composer).getByText("已选择 1 份资料。")).toBeInTheDocument();
    expect(screen.queryByText(/联网搜索已开/)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "联网搜索" })).toHaveAttribute("aria-pressed", "true");
  });

  it("sends selected materials with web search and deep thinking, then shows citations and graph trace", async () => {
    const user = userEvent.setup();
    const { calls } = renderWithDashboardSummary(materialRichSummary);

    await user.click(screen.getByRole("button", { name: "打开资料库" }));
    await user.click(screen.getByRole("button", { name: /期末复习题 2025/ }));
    await user.click(screen.getByRole("button", { name: "关闭资料库" }));
    await user.click(screen.getByRole("button", { name: "联网搜索" }));
    await user.click(screen.getByRole("button", { name: "深度思考" }));
    await user.type(screen.getByRole("textbox", { name: "学习问题输入" }), "结合资料和最新趋势怎么复习？");
    await user.click(screen.getByRole("button", { name: "发送" }));

    const messageCall = calls.find((call) => call.method === "post" && call.url === TUTOR_ENDPOINTS.message(501));

    expect(messageCall?.payload).toMatchObject({
      message: "结合资料和最新趋势怎么复习？",
      use_web_search: true,
      deep_thinking: true,
      selected_material_ids: [202]
    });

    const thread = screen.getByRole("region", { name: "主页对话" });

    await user.click(within(thread).getByRole("button", { name: "来源" }));
    expect(within(thread).getByRole("region", { name: "回答展开详情" })).toHaveTextContent("真实资料讲义.md");
    expect(within(thread).getByRole("region", { name: "回答展开详情" })).toHaveTextContent("联网搜索结果");

    await user.click(within(thread).getByRole("button", { name: "思考过程" }));

    expect(await within(thread).findByText("home_profile")).toBeInTheDocument();
    expect(within(thread).getByText("确认不展示原始思维链")).toBeInTheDocument();
    expect(calls).toContainEqual(expect.objectContaining({ method: "get", url: AGENT_ENDPOINTS.trace("trace_home_tutor_test") }));
  });

  it("uses browser speech recognition for voice input and browser speech synthesis for read aloud", async () => {
    const user = userEvent.setup();
    const speakSpy = vi.fn();

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
        cancel: vi.fn(),
        speak: speakSpy
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

    expect(screen.getByRole("textbox", { name: "学习问题输入" })).toHaveValue("语音输入的问题");
    expect(await screen.findByText("已识别语音输入。")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "发送" }));
    await user.click(await screen.findByRole("button", { name: "朗读回答" }));

    expect(speakSpy).toHaveBeenCalledTimes(1);
    expect(screen.getByText("正在朗读回答。")).toBeInTheDocument();
  });

  it("shows a non-blocking warning when the browser does not support voice input", async () => {
    const user = userEvent.setup();

    renderWithDashboardSummary();

    await user.click(screen.getByRole("button", { name: "语音输入" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("当前浏览器不支持语音输入。");
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
    const messageCalls = calls.filter((call) => call.method === "post" && call.url === TUTOR_ENDPOINTS.message(501));

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

    const { calls } = renderWithDashboardSummary(starterSummary);

    await user.click(await screen.findByRole("button", { name: /接口里的主页历史/ }));

    const thread = await screen.findByRole("region", { name: "主页对话" });

    expect(within(thread).getByText("后端保存的问题")).toBeInTheDocument();
    expect(within(thread).getByText("后端保存的回答")).toBeInTheDocument();
    expect(calls).toContainEqual(expect.objectContaining({ method: "get", url: TUTOR_ENDPOINTS.detail(501) }));
  });

  it("keeps the typed question when persistent message sending fails", async () => {
    const user = userEvent.setup();

    renderWithDashboardSummary(blankSummary, { failMessageSend: true });

    const input = screen.getByRole("textbox", { name: "学习问题输入" });
    await user.type(input, "这次发送会失败吗？");
    await user.click(screen.getByRole("button", { name: "发送" }));

    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    expect(await screen.findByRole("alert")).toHaveTextContent("消息发送失败，请稍后再试。");
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

  it("lets the home answer reveal sources, path, and thinking details", async () => {
    const user = userEvent.setup();

    renderWithDashboardSummary({
      ...starterSummary,
      command_suggestions: ["把反向传播讲到我能做题"]
    });

    await screen.findByRole("link", { name: /真实机器学习课/ });
    await user.click(screen.getByRole("button", { name: "把反向传播讲到我能做题" }));
    expect(screen.getByRole("textbox", { name: "学习问题输入" })).toHaveValue("把反向传播讲到我能做题");

    await user.click(screen.getByRole("button", { name: "发送" }));
    await user.click(screen.getByRole("button", { name: "学习路径" }));

    expect(screen.getByRole("region", { name: "回答展开详情" })).toHaveTextContent("先用 10 分钟补概念");

    await user.click(screen.getByRole("button", { name: "思考过程" }));

    expect(screen.getByRole("region", { name: "回答展开详情" })).toHaveTextContent("课堂协作轨迹");
    expect(screen.getByRole("region", { name: "回答展开详情" })).toHaveTextContent("确认不展示原始思维链");
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
        url: COURSE_ENDPOINTS.fromMaterials,
        payload: {
          material_ids: [201],
          course_title: "人工智能导论期末复习"
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
        email: "student@edunova.local",
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

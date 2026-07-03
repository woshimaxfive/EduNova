import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { apiClient } from "../api/client";
import { DASHBOARD_ENDPOINTS, type DashboardSummary } from "../api/dashboard";
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
      id: "chat-101",
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

function renderWithDashboardSummary(summary: DashboardSummary = starterSummary) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false
      }
    }
  });
  const calls: string[] = [];

  apiClient.defaults.adapter = async (config) => {
    calls.push(config.url ?? "");

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
      <MemoryRouter>
        <LearningSpacePage />
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
    useAuthStore.getState().clearSession();
  });

  it("loads the home summary from the dashboard API instead of static starter courses", async () => {
    const { calls } = renderWithDashboardSummary();

    expect(await screen.findByRole("link", { name: /真实机器学习课/ })).toHaveAttribute("href", "/app/courses/101");
    expect(screen.getByRole("button", { name: /接口里的主页历史/ })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Python 基础补齐/ })).not.toBeInTheDocument();
    expect(calls).toContain(DASHBOARD_ENDPOINTS.summary);
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
    expect(calls).toContain(DASHBOARD_ENDPOINTS.summary);
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
    expect(within(dialog).getByRole("button", { name: "创建课程草案" })).toBeDisabled();
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
    expect(within(thread).getByText(/可以先把资料按章节和题型拆开/)).toBeInTheDocument();
    expect(within(thread).queryByRole("region", { name: "回答展开详情" })).not.toBeInTheDocument();
    await user.click(within(thread).getByRole("button", { name: "来源" }));
    expect(within(thread).getByRole("region", { name: "回答展开详情" })).toHaveTextContent("来源");
    expect(screen.getByRole("region", { name: "底部学习输入" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /期末复习怎么安排/ })).toHaveAttribute("aria-pressed", "true");
    expect(screen.queryByText("已生成回答。")).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "嗨，同学，准备好一起学习了吗？" })).not.toBeInTheDocument();
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

    expect(screen.getByRole("region", { name: "回答展开详情" })).toHaveTextContent("处理摘要");
  });

  it("moves from the library drawer to course generation as a single dialog", async () => {
    const user = userEvent.setup();

    renderWithDashboardSummary();

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
    expect(within(courseDialog).getByRole("button", { name: "创建课程草案" })).toBeEnabled();

    await user.click(within(courseDialog).getByRole("button", { name: "创建课程草案" }));

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("已用 1 份资料创建课程草案");
  });

  it("keeps blank starter accounts empty until they upload their own material", async () => {
    const user = userEvent.setup();

    renderWithDashboardSummary(blankSummary);

    expect(await screen.findByText("还没有课程")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /人工智能导论/ })).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "打开资料库" }));

    expect(screen.getByRole("dialog", { name: "资料库" })).toHaveTextContent("资料库还是空的");
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

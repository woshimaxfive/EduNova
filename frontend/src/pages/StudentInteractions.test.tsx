import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { type ReactNode } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { PATHS } from "../app/routePaths";
import { apiClient } from "../api/client";
import { DASHBOARD_ENDPOINTS, type DashboardSummary } from "../api/dashboard";
import { MATERIAL_ENDPOINTS, type MaterialListItem } from "../api/materials";
import { TUTOR_ENDPOINTS } from "../api/tutor";
import { useAuthStore } from "../features/auth/authStore";
import { CourseSpacePage } from "./CourseSpacePage";
import { LearningSpacePage } from "./LearningSpacePage";
import { LibraryPage } from "./LibraryPage";
import { PracticePage } from "./PracticePage";
import { ProfilePage } from "./ProfilePage";
import { ReportsPage } from "./ReportsPage";
import { SettingsPage } from "./SettingsPage";
import { StudioPage } from "./StudioPage";
import { TutorPage } from "./TutorPage";

let previousAdapter = apiClient.defaults.adapter;

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

function renderPage(page: ReactNode) {
  renderWithProviders(<MemoryRouter>{page}</MemoryRouter>);
}

describe("student interaction affordances", () => {
  beforeEach(() => {
    previousAdapter = apiClient.defaults.adapter;
    localStorage.clear();
    useAuthStore.getState().clearSession();
  });

  afterEach(() => {
    apiClient.defaults.adapter = previousAdapter;
    useAuthStore.getState().clearSession();
  });

  it("turns the home composer buttons into visible demo-state feedback", async () => {
    const user = userEvent.setup();
    const session = {
      id: "701",
      scope: "home",
      course_id: null,
      title: "监督学习怎么复习？",
      mode: "chat",
      archived_from_home: false,
      created_at: "2026-07-03T12:00:00Z",
      updated_at: "2026-07-03T12:01:00Z"
    };
    let uploadedMaterial: DashboardSummary["recent_materials"][number] | null = null;
    const dashboardSummary: DashboardSummary = {
      profile_summary: {
        display_name: "交互学生",
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
      recent_resources: [],
      command_suggestions: [],
      evidence_summary: {
        citation_count: 0,
        latest_trace_id: null,
        low_evidence_count: 0
      },
      empty_state: {
        kind: "blank",
        title: "还没有课程",
        description: "上传资料后可直接问，也可生成课程。",
        action_label: "上传资料"
      }
    };

    apiClient.defaults.adapter = async (config) => {
      const method = (config.method ?? "get").toLowerCase();
      const url = config.url ?? "";

      if (url === DASHBOARD_ENDPOINTS.summary) {
        return {
          data: {
            data: {
              ...dashboardSummary,
              material_library_summary: {
                material_count: uploadedMaterial ? 1 : 0,
                unassigned_count: uploadedMaterial ? 1 : 0
              },
              recent_materials: uploadedMaterial ? [uploadedMaterial] : []
            },
            trace_id: "trace_interaction_dashboard"
          },
          status: 200,
          statusText: "OK",
          headers: {},
          config
        };
      }

      if (url === TUTOR_ENDPOINTS.sessions && method === "post") {
        return {
          data: { data: session, trace_id: "trace_interaction_create" },
          status: 200,
          statusText: "OK",
          headers: {},
          config
        };
      }

      if (url === TUTOR_ENDPOINTS.message(session.id) && method === "post") {
        return {
          data: {
            data: {
              session,
              messages: [
                {
                  id: "701-u1",
                  session_id: session.id,
                  role: "user",
                  content: "监督学习怎么复习？",
                  citation_json: [],
                  trace_id: null,
                  created_at: "2026-07-03T12:00:30Z"
                },
                {
                  id: "701-a1",
                  session_id: session.id,
                  role: "assistant",
                  content: "可以先把资料按章节和题型拆开：先补核心概念，再用期末题做检索式复习。回答会保留引用和路径建议。",
                  citation_json: [],
                  trace_id: null,
                  created_at: "2026-07-03T12:01:00Z"
                }
              ]
            },
            trace_id: "trace_interaction_message"
          },
          status: 200,
          statusText: "OK",
          headers: {},
          config
        };
      }

      if (url === MATERIAL_ENDPOINTS.upload && method === "post") {
        uploadedMaterial = {
          id: "801",
          title: "数据结构期末题.pdf",
          type: "PDF",
          detail: "已入库",
          modified: "今天",
          size: "4 B"
        };

        return {
          data: {
            data: {
              ...uploadedMaterial,
              material_id: 801,
              course_id: null,
              filename: uploadedMaterial.title,
              parse_status: "uploaded"
            },
            trace_id: "trace_interaction_material_upload"
          },
          status: 200,
          statusText: "OK",
          headers: {},
          config
        };
      }

      return {
        data: { data: {}, trace_id: "trace_interaction_default" },
        status: 200,
        statusText: "OK",
        headers: {},
        config
      };
    };

    useAuthStore.getState().setSession({
      token: "interaction-token",
      user: {
        id: 7,
        email: "interaction@edunova.local",
        displayName: "交互学生",
        role: "student",
        starterMode: "blank"
      }
    });

    renderPage(<LearningSpacePage />);

    const uploadedFile = new File(["demo"], "数据结构期末题.pdf", { type: "application/pdf" });
    await user.upload(screen.getByLabelText("上传资料文件"), uploadedFile);

    expect(screen.getByRole("status")).toHaveTextContent("数据结构期末题.pdf 已上传到资料库");

    await user.click(screen.getByRole("button", { name: "打开资料库" }));

    expect(screen.getByRole("dialog", { name: "资料库" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /数据结构期末题.pdf/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "作为本次对话参考" })).toBeDisabled();

    const material = screen.getByRole("button", { name: /数据结构期末题.pdf/ });

    expect(material).toHaveAttribute("aria-pressed", "false");

    await user.click(material);

    expect(material).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("status")).toHaveTextContent("已选择 1 份资料");
    expect(screen.getByRole("button", { name: "作为本次对话参考" })).toBeEnabled();

    await user.click(screen.getByRole("button", { name: "关闭资料库" }));
    await user.click(screen.getByRole("button", { name: "发送" }));

    expect(screen.getByRole("status")).toHaveTextContent("先输入一个学习问题");

    await user.type(screen.getByRole("textbox", { name: "学习问题输入" }), "监督学习怎么复习？");
    await user.click(screen.getByRole("button", { name: "联网搜索" }));
    await user.click(screen.getByRole("button", { name: "深度思考" }));
    await user.click(screen.getByRole("button", { name: "发送" }));

    expect(screen.getByRole("button", { name: "联网搜索" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "深度思考" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.queryByText("已生成回答。")).not.toBeInTheDocument();
    expect(screen.getByRole("region", { name: "主页对话" })).toHaveTextContent("监督学习怎么复习？");
  });

  it("opens course answer detail panels instead of leaving action buttons inert", async () => {
    const user = userEvent.setup();

    renderPage(<CourseSpacePage />);

    await user.click(screen.getByRole("button", { name: "学习路径" }));

    expect(screen.getByRole("region", { name: "回答展开详情" })).toHaveTextContent("建议路径");

    await user.click(screen.getByRole("button", { name: "Agent 过程" }));

    expect(screen.getByRole("region", { name: "回答展开详情" })).toHaveTextContent("RetrieverAgent");
    expect(screen.getByRole("region", { name: "回答展开详情" })).toHaveTextContent("PathAgent");
    expect(screen.getByRole("region", { name: "回答展开详情" })).not.toHaveTextContent("PlannerAgent");

    await user.click(screen.getByRole("button", { name: "监督学习，当前焦点" }));

    expect(screen.getByRole("region", { name: "当前知识点详情" })).toHaveTextContent("监督学习");
  });

  it("keeps tutoring practice and reports as course-context actions", () => {
    renderPage(<CourseSpacePage />);

    const courseActions = screen.getByRole("navigation", { name: "课程行动入口" });
    const expectedActions = [
      ["进入 AI 辅导", PATHS.tutor],
      ["开始练习", PATHS.practice],
      ["查看学习报告", PATHS.reports]
    ] as const;

    for (const [label, path] of expectedActions) {
      expect(within(courseActions).getByRole("link", { name: label })).toHaveAttribute("href", path);
    }
  });

  it("sends course-local questions with Enter and adds them to the course history", async () => {
    const user = userEvent.setup();

    renderPage(<CourseSpacePage />);

    const courseInput = screen.getByRole("textbox", { name: "课程问题输入" });

    await user.type(courseInput, "给我一个十分钟复习计划{enter}");

    expect(courseInput).toHaveValue("");
    expect(screen.getByRole("status")).toHaveTextContent("已生成课程回答");
    expect(screen.getByRole("region", { name: "课程即时对话" })).toHaveTextContent("给我一个十分钟复习计划");
    expect(screen.getByRole("region", { name: "课程即时对话" })).toHaveTextContent("我会按课程资料回答");
    expect(screen.getByRole("region", { name: "历史对话" })).toHaveTextContent("给我一个十分钟复习计划");
  });

  it("uses the shared sidebar history to switch the course thread", async () => {
    const user = userEvent.setup();

    renderPage(<CourseSpacePage />);

    const historyRail = screen.getByRole("region", { name: "历史对话" });
    const courseThreadList = screen.getByLabelText("课程内历史对话");

    await user.click(within(historyRail).getByRole("button", { name: /解释泛化能力和过拟合的区别/ }));

    expect(within(courseThreadList).getByRole("button", { name: "解释泛化能力和过拟合的区别" })).toHaveAttribute("aria-pressed", "true");
  });

  it("switches tutor modes and provides feedback for tutor actions", async () => {
    const user = userEvent.setup();

    renderPage(<TutorPage />);

    await user.click(screen.getByRole("button", { name: "苏格拉底追问" }));

    expect(screen.getByRole("button", { name: "苏格拉底追问" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByText("当前模式：苏格拉底追问")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "深度思考" }));

    expect(screen.getByRole("status")).toHaveTextContent("深度思考已开启");
  });

  it("validates and acknowledges practice submissions", async () => {
    const user = userEvent.setup();

    renderPage(<PracticePage />);

    await user.click(screen.getByRole("button", { name: "提交答案" }));

    expect(screen.getByRole("status")).toHaveTextContent("先写下你的推导思路");

    await user.type(screen.getByRole("textbox", { name: "作答区" }), "需要把局部梯度沿计算图传回参数。");
    await user.click(screen.getByRole("button", { name: "提交答案" }));

    expect(screen.getByRole("status")).toHaveTextContent("已提交答案");
    expect(screen.getByRole("region", { name: "批改反馈" })).toHaveTextContent("本次批改");
    expect(screen.getByRole("region", { name: "薄弱点复习队列" })).toHaveTextContent("下一题");
  });

  it("generates studio resources into the local queue and output track", async () => {
    const user = userEvent.setup();

    renderPage(<StudioPage />);

    await user.selectOptions(screen.getByLabelText("知识点"), "反向传播");
    await user.click(screen.getByRole("button", { name: "练习" }));
    await user.click(screen.getAllByRole("button", { name: "生成资源" })[0]);

    expect(screen.getByRole("status")).toHaveTextContent("已生成「反向传播练习」任务");
    expect(screen.getByRole("region", { name: "生成队列" })).toHaveTextContent("反向传播练习");
    expect(screen.getByRole("region", { name: "资源生成区" })).toHaveTextContent("反向传播练习");
  });

  it("updates profile goals and evidence from local form input", async () => {
    const user = userEvent.setup();

    renderPage(<ProfilePage />);

    await user.click(screen.getByRole("button", { name: "更新目标" }));
    await user.clear(screen.getByRole("textbox", { name: "学习目标" }));
    await user.type(screen.getByRole("textbox", { name: "学习目标" }), "两周冲刺软件杯演示");
    await user.click(screen.getByRole("button", { name: "保存目标" }));

    expect(screen.getByRole("status")).toHaveTextContent("学习目标已更新");
    expect(screen.getByRole("region", { name: "画像证据" })).toHaveTextContent("目标更新：两周冲刺软件杯演示");

    await user.type(screen.getByRole("textbox", { name: "画像问题回答" }), "最担心反向传播推导。");
    await user.click(screen.getByRole("button", { name: "更新画像" }));

    expect(screen.getByRole("status")).toHaveTextContent("画像证据已更新");
    expect(screen.getByRole("region", { name: "画像证据" })).toHaveTextContent("画像对话：最担心反向传播推导。");
  });

  it("prepares the report export state before real file generation is connected", async () => {
    const user = userEvent.setup();

    renderPage(<ReportsPage />);

    await user.click(screen.getByRole("button", { name: "导出档案" }));

    expect(screen.getByRole("status")).toHaveTextContent("学习档案已准备好");
    expect(screen.getByRole("region", { name: "学习报告" })).toHaveTextContent("已整理画像、错因、引用和复习建议");
    expect(screen.getByRole("region", { name: "导出学习档案" })).toHaveTextContent("已生成 1 份学习档案");
  });

  it("shows feedback for library and settings actions that await real APIs", async () => {
    const user = userEvent.setup();
    let materials: MaterialListItem[] = [
      {
        id: "301",
        title: "AI 导论讲义",
        type: "DOCX",
        detail: "已解析",
        modified: "今天",
        size: "1.2 MB",
        category: "document",
        extension: "DOCX",
        parse_status: "completed",
        course_ids: ["101"]
      },
      {
        id: "302",
        title: "期末复习题样例",
        type: "MD",
        detail: "已解析",
        modified: "昨天",
        size: "68 KB",
        category: "document",
        extension: "MD",
        parse_status: "completed",
        course_ids: []
      }
    ];
    const calls: Array<{ method: string; url: string }> = [];

    apiClient.defaults.adapter = async (config) => {
      const method = (config.method ?? "get").toLowerCase();
      const url = config.url ?? "";
      calls.push({ method, url });

      if (url === MATERIAL_ENDPOINTS.list && method === "get") {
        return {
          data: { data: materials, trace_id: "trace_materials_list" },
          status: 200,
          statusText: "OK",
          headers: {},
          config
        };
      }

      if (url === MATERIAL_ENDPOINTS.upload && method === "post") {
        const uploaded = {
          id: "303",
          title: "课堂截图.png",
          type: "PNG",
          detail: "仅入库，暂不做 OCR",
          modified: "今天",
          size: "4 B",
          category: "image",
          extension: "PNG",
          parse_status: "uploaded",
          course_ids: []
        } satisfies MaterialListItem;
        materials = [uploaded, ...materials];
        return {
          data: {
            data: {
              ...uploaded,
              material_id: 303,
              course_id: null,
              filename: uploaded.title
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

    renderPage(<LibraryPage />);

    expect(await screen.findByRole("button", { name: /AI 导论讲义/ })).toBeInTheDocument();
    const uploadedFile = new File(["demo"], "课堂截图.png", { type: "image/png" });
    await user.upload(screen.getByLabelText("上传资料文件"), uploadedFile);

    expect(await screen.findByRole("status")).toHaveTextContent("课堂截图.png 已上传到资料库");
    expect(await screen.findByRole("button", { name: /课堂截图.png/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /课堂截图.png/ })).toHaveTextContent("仅入库，暂不做 OCR");
    expect(screen.queryByText("等待提取说明")).not.toBeInTheDocument();
    expect(calls).toContainEqual({ method: "post", url: MATERIAL_ENDPOINTS.upload });

    await user.click(screen.getByRole("button", { name: "图片" }));

    expect(screen.getByRole("button", { name: "图片" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: /课堂截图.png/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /AI 导论讲义/ })).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "全部" }));
    await user.click(screen.getByRole("button", { name: /AI 导论讲义/ }));

    expect(screen.getByRole("region", { name: "资料动作反馈" })).toHaveTextContent("AI 导论讲义");

    await user.click(screen.getByRole("button", { name: "生成课程" }));

    const courseDialog = screen.getByRole("dialog", { name: "从资料生成课程" });
    expect(courseDialog).toBeInTheDocument();
    const courseMaterial = within(courseDialog).getByRole("button", { name: /AI 导论讲义/ });

    expect(courseMaterial).toHaveAttribute("aria-pressed", "false");
    expect(within(courseDialog).getByRole("button", { name: "创建课程草案" })).toBeDisabled();

    await user.click(courseMaterial);

    expect(courseMaterial).toHaveAttribute("aria-pressed", "true");
    expect(within(courseDialog).getByRole("button", { name: "创建课程草案" })).toBeEnabled();

    renderPage(<SettingsPage />);

    const settingsRegion = screen.getByRole("region", { name: "账号设置" });

    await user.clear(within(settingsRegion).getByLabelText("昵称"));
    await user.type(within(settingsRegion).getByLabelText("昵称"), "冲刺学生");
    await user.selectOptions(screen.getByLabelText("供应商"), "DeepSeek");
    await user.click(screen.getByRole("button", { name: "保存设置" }));

    expect(within(settingsRegion).getByRole("status")).toHaveTextContent("冲刺学生 的设置已保存");
  });

  it("keeps route pages in the home shell with active navigation and a working new chat action", async () => {
    const user = userEvent.setup();

    renderWithProviders(
      <MemoryRouter initialEntries={[PATHS.library]}>
        <Routes>
          <Route path={PATHS.app} element={<LearningSpacePage />} />
          <Route path={PATHS.library} element={<LibraryPage />} />
        </Routes>
      </MemoryRouter>
    );

    const historyRail = screen.getByRole("region", { name: "历史对话" });

    expect(within(historyRail).getByRole("link", { name: "资料库" })).toHaveClass("active");
    expect(screen.queryByText("上传资料，搜索引用，也可以生成课程。")).not.toBeInTheDocument();

    await user.click(within(historyRail).getByRole("button", { name: "新建对话" }));

    expect(screen.getByRole("heading", { name: "嗨，同学，准备好一起学习了吗？" })).toBeInTheDocument();
  });
});

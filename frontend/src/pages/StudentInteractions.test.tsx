import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { type ReactNode } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { buildCoursePath, PATHS } from "../app/routePaths";
import { apiClient } from "../api/client";
import { COURSE_ENDPOINTS } from "../api/courses";
import { DASHBOARD_ENDPOINTS, type DashboardSummary } from "../api/dashboard";
import { MATERIAL_ENDPOINTS, type MaterialListItem } from "../api/materials";
import { SETTINGS_ENDPOINTS, type ModelConfigSummary, type ModelSettingsListResponse } from "../api/settings";
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

  it("does not create local course answers when the course route context is missing", async () => {
    const user = userEvent.setup();
    renderPage(<CourseSpacePage />);

    await user.type(screen.getByRole("textbox", { name: "课程问题输入" }), "监督学习怎么复习？");
    await user.click(screen.getByRole("button", { name: "发送" }));

    expect(screen.getByRole("status")).toHaveTextContent("课程地址无效，请从课程列表重新进入。");
    expect(screen.getByRole("textbox", { name: "课程问题输入" })).toHaveValue("监督学习怎么复习？");
    expect(screen.queryByRole("region", { name: "课程即时对话" })).not.toBeInTheDocument();
  });

  it("renders generated course detail and knowledge points from the course API", async () => {
    apiClient.defaults.adapter = async (config) => {
      const url = config.url ?? "";

      if (url === COURSE_ENDPOINTS.detail(808)) {
        return {
          data: {
            data: {
              id: "808",
              title: "机器学习期末复习",
              description: "由 1 份资料生成",
              subject: "自主学习",
              source_type: "uploaded",
              status: "ready",
              progress_percent: 0,
              material_count: 1,
              knowledge_point_count: 2,
              chunk_count: 5
            },
            trace_id: "trace_course_detail"
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
                id: "9001",
                title: "梯度下降",
                summary: "理解梯度方向和学习率。",
                chapter: "优化方法",
                order_index: 1,
                difficulty: "基础"
              },
              {
                id: "9002",
                title: "模型评估",
                summary: "区分训练集、验证集和测试集。",
                chapter: "评估指标",
                order_index: 2,
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

      return {
        data: { data: {}, trace_id: "trace_course_default" },
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

    expect(await screen.findByRole("heading", { name: "机器学习期末复习" })).toBeInTheDocument();
    expect(screen.getByLabelText("课程状态")).toHaveTextContent("资料");
    expect(screen.getByLabelText("课程状态")).toHaveTextContent("1");
    expect(screen.getByLabelText("课程状态")).toHaveTextContent("知识点");
    expect(screen.getByLabelText("课程状态")).toHaveTextContent("2");
    expect(screen.getByText("梯度下降")).toBeInTheDocument();
    expect(screen.getByText("模型评估")).toBeInTheDocument();
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

  it("keeps invalid course questions in the input instead of adding fake history", async () => {
    const user = userEvent.setup();

    renderPage(<CourseSpacePage />);

    const courseInput = screen.getByRole("textbox", { name: "课程问题输入" });

    await user.type(courseInput, "给我一个十分钟复习计划{enter}");

    expect(courseInput).toHaveValue("给我一个十分钟复习计划");
    expect(screen.getByRole("status")).toHaveTextContent("课程地址无效，请从课程列表重新进入。");
    expect(screen.queryByRole("region", { name: "课程即时对话" })).not.toBeInTheDocument();
    expect(screen.getByRole("region", { name: "历史对话" })).toHaveTextContent("还没有历史对话");
  });

  it("does not render static course history when no real course sessions exist", () => {
    renderPage(<CourseSpacePage />);

    const historyRail = screen.getByRole("region", { name: "历史对话" });
    const courseThreadList = screen.getByLabelText("课程内历史对话");

    expect(within(historyRail).queryByRole("button", { name: /解释泛化能力和过拟合的区别/ })).not.toBeInTheDocument();
    expect(within(courseThreadList).queryByRole("button")).not.toBeInTheDocument();
    expect(courseThreadList).toHaveTextContent("请从课程列表重新进入");
  });

  it("uses the tutor route as a course tutoring entry without static demo answers", async () => {
    apiClient.defaults.adapter = async (config) => {
      if (config.url === COURSE_ENDPOINTS.list) {
        return {
          data: {
            data: [
              {
                id: "808",
                title: "机器学习期末复习",
                description: "由资料生成",
                subject: "自主学习",
                source_type: "uploaded",
                status: "ready",
                progress_percent: 0,
                material_count: 1,
                knowledge_point_count: 2,
                chunk_count: 5
              }
            ],
            trace_id: "trace_tutor_courses"
          },
          status: 200,
          statusText: "OK",
          headers: {},
          config
        };
      }

      return {
        data: { data: {}, trace_id: "trace_tutor_default" },
        status: 200,
        statusText: "OK",
        headers: {},
        config
      };
    };

    renderPage(<TutorPage />);

    expect(await screen.findByRole("link", { name: /机器学习期末复习/ })).toHaveAttribute("href", buildCoursePath("808"));
    expect(screen.getByRole("region", { name: "课程辅导入口" })).toHaveTextContent("课程空间");
    expect(screen.queryByText("为什么反向传播需要链式法则？")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "苏格拉底追问" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "深度思考" })).not.toBeInTheDocument();
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

    expect(screen.getByRole("region", { name: "生成队列" })).not.toHaveTextContent("监督学习个性化讲解");
    expect(screen.getByRole("region", { name: "资源生成区" })).not.toHaveTextContent("反向传播薄弱点练习");

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

  it("shows feedback for library actions that await real APIs", async () => {
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
    expect(within(courseDialog).getByRole("button", { name: "生成课程" })).toBeDisabled();

    await user.click(courseMaterial);

    expect(courseMaterial).toHaveAttribute("aria-pressed", "true");
    expect(within(courseDialog).getByRole("button", { name: "生成课程" })).toBeEnabled();

  });

  it("manages isolated model configs with curated provider presets", async () => {
    const user = userEvent.setup();
    let settingsList: ModelSettingsListResponse = {
      configs: [
        {
          id: 1,
          source: "user",
          display_name: "星火 Lite",
          preset_id: "spark",
          provider: "openai_compatible",
          base_url: "https://spark-api-open.xf-yun.com/v1",
          chat_model: "lite",
          embedding_model: null,
          has_api_key: true,
          api_key_masked: "sp-u...oken",
          can_use_model: true,
          is_default: true,
          last_test_ok: null,
          last_test_message: null,
          last_tested_at: null
        }
      ],
      default_config_id: 1,
      system_summary: {
        source: "system",
        provider: "openai_compatible",
        base_url: "https://system-model.example.local/v1",
        chat_model: "system-chat",
        embedding_model: "system-embedding",
        has_api_key: true,
        api_key_masked: "sk-s...cret",
        can_use_model: true
      }
    };
    const calls: Array<{ method: string; url: string; payload: unknown }> = [];

    apiClient.defaults.adapter = async (config) => {
      const method = (config.method ?? "get").toLowerCase();
      const url = config.url ?? "";
      const payload = parsePayload(config.data);
      calls.push({ method, url, payload });

      if (url === SETTINGS_ENDPOINTS.configs && method === "get") {
        return {
          data: { data: settingsList, trace_id: "trace_settings_configs" },
          status: 200,
          statusText: "OK",
          headers: {},
          config
        };
      }

      if (url === SETTINGS_ENDPOINTS.configs && method === "post") {
        const data = payload as {
          display_name: string;
          preset_id: string;
          base_url: string;
          chat_model: string;
          embedding_model?: string;
          api_key?: string;
        };
        const newConfig: ModelConfigSummary = {
          id: 2,
          source: "user",
          display_name: data.display_name,
          preset_id: data.preset_id,
          provider: "openai_compatible",
          base_url: data.base_url,
          chat_model: data.chat_model,
          embedding_model: data.embedding_model ?? null,
          has_api_key: true,
          api_key_masked: "hy-u...oken",
          can_use_model: true,
          is_default: false,
          last_test_ok: null,
          last_test_message: null,
          last_tested_at: null
        };
        settingsList = {
          ...settingsList,
          configs: [...settingsList.configs, newConfig]
        };

        return {
          data: { data: newConfig, trace_id: "trace_settings_create" },
          status: 200,
          statusText: "OK",
          headers: {},
          config
        };
      }

      if (url === SETTINGS_ENDPOINTS.defaultConfig(2) && method === "post") {
        settingsList = {
          ...settingsList,
          default_config_id: 2,
          configs: settingsList.configs.map((item) => ({
            ...item,
            is_default: item.id === 2
          }))
        };

        return {
          data: { data: settingsList, trace_id: "trace_settings_default" },
          status: 200,
          statusText: "OK",
          headers: {},
          config
        };
      }

      if (url === SETTINGS_ENDPOINTS.testConfig(2) && method === "post") {
        settingsList = {
          ...settingsList,
          configs: settingsList.configs.map((item) =>
            item.id === 2 ? { ...item, last_test_ok: true, last_test_message: "模型连接成功。" } : item
          )
        };

        return {
          data: {
            data: {
              ok: true,
              source: "user",
              chat_model: "hunyuan-turbos-latest",
              message: "模型连接成功。",
              config_id: 2
            },
            trace_id: "trace_settings_test"
          },
          status: 200,
          statusText: "OK",
          headers: {},
          config
        };
      }

      if (url === SETTINGS_ENDPOINTS.config(2) && method === "delete") {
        settingsList = {
          ...settingsList,
          default_config_id: 1,
          configs: settingsList.configs
            .filter((item) => item.id !== 2)
            .map((item) => ({ ...item, is_default: item.id === 1 }))
        };

        return {
          data: { data: settingsList, trace_id: "trace_settings_delete" },
          status: 200,
          statusText: "OK",
          headers: {},
          config
        };
      }

      return {
        data: { data: {}, trace_id: "trace_settings_default" },
        status: 200,
        statusText: "OK",
        headers: {},
        config
      };
    };

    renderPage(<SettingsPage />);

    expect(await screen.findByRole("button", { name: /星火 Lite/ })).toBeInTheDocument();
    expect(screen.getByText("默认配置")).toBeInTheDocument();
    expect(screen.getByText("sp-u...oken")).toBeInTheDocument();
    expect(screen.queryByText("sk-••••••••")).not.toBeInTheDocument();
    expect(screen.queryByText("深度思考")).not.toBeInTheDocument();
    expect(screen.queryByText("联网搜索")).not.toBeInTheDocument();
    expect(screen.queryByText("OpenRouter")).not.toBeInTheDocument();

    const providerPreset = screen.getByRole("combobox", { name: "Provider 预设" });
    expect(within(providerPreset).getAllByRole("option")[0]).toHaveTextContent("讯飞星火 Spark");
    expect(within(providerPreset).getByRole("option", { name: "百度千帆" })).toBeInTheDocument();
    expect(within(providerPreset).getByRole("option", { name: "腾讯混元" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "新建配置" }));
    await user.selectOptions(providerPreset, "tencent-hunyuan");

    expect(screen.getByRole("textbox", { name: "Base URL" })).toHaveValue(
      "https://api.hunyuan.cloud.tencent.com/v1"
    );
    expect(screen.getByRole("textbox", { name: "回答模型" })).toHaveValue("hunyuan-turbos-latest");

    await user.clear(screen.getByRole("textbox", { name: "配置名称" }));
    await user.type(screen.getByRole("textbox", { name: "配置名称" }), "腾讯混元默认");
    await user.type(screen.getByLabelText("API Key"), "hunyuan-user-secret");
    await user.click(screen.getByRole("button", { name: "保存配置" }));

    expect(await screen.findByRole("status")).toHaveTextContent("模型配置已保存");
    expect(screen.getByRole("button", { name: /腾讯混元默认/ })).toBeInTheDocument();
    expect(screen.queryByText("hunyuan-user-secret")).not.toBeInTheDocument();
    expect(calls).toContainEqual({
      method: "post",
      url: SETTINGS_ENDPOINTS.configs,
      payload: {
        display_name: "腾讯混元默认",
        preset_id: "tencent-hunyuan",
        provider: "openai_compatible",
        base_url: "https://api.hunyuan.cloud.tencent.com/v1",
        api_key: "hunyuan-user-secret",
        chat_model: "hunyuan-turbos-latest",
        make_default: false
      }
    });

    await user.click(screen.getByRole("button", { name: "设为默认" }));
    expect(await screen.findByRole("status")).toHaveTextContent("已设为默认模型配置");

    await user.click(screen.getByRole("button", { name: "测试连接" }));

    expect(await screen.findByRole("status")).toHaveTextContent("模型连接成功");

    await user.click(screen.getByRole("button", { name: "删除配置" }));
    expect(await screen.findByRole("status")).toHaveTextContent("模型配置已删除");
    expect(screen.queryByRole("button", { name: /腾讯混元默认/ })).not.toBeInTheDocument();
  });

  it("creates a real course from the library page and enters the new course", async () => {
    const user = userEvent.setup();
    const calls: Array<{ method: string; url: string; payload: unknown }> = [];
    const materials: MaterialListItem[] = [
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

    apiClient.defaults.adapter = async (config) => {
      const method = (config.method ?? "get").toLowerCase();
      const url = config.url ?? "";
      calls.push({ method, url, payload: parsePayload(config.data) });

      if (url === MATERIAL_ENDPOINTS.list && method === "get") {
        return {
          data: { data: materials, trace_id: "trace_library_materials" },
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
                id: "808",
                title: "机器学习期末复习",
                description: "由 1 份资料生成",
                source_type: "uploaded",
                status: "ready",
                knowledge_point_count: 2,
                chunk_count: 5,
                material_count: 1
              },
              knowledge_points: []
            },
            trace_id: "trace_library_course"
          },
          status: 200,
          statusText: "OK",
          headers: {},
          config
        };
      }

      return {
        data: { data: {}, trace_id: "trace_library_default" },
        status: 200,
        statusText: "OK",
        headers: {},
        config
      };
    };

    useAuthStore.getState().setSession({
      token: "library-course-token",
      user: {
        id: 9,
        email: "library@edunova.local",
        displayName: "资料库学生",
        role: "student",
        starterMode: "blank"
      }
    });

    renderWithProviders(
      <MemoryRouter initialEntries={[PATHS.library]}>
        <Routes>
          <Route path={PATHS.library} element={<LibraryPage />} />
          <Route path={PATHS.courseDetail} element={<div>资料库建课已跳转</div>} />
        </Routes>
      </MemoryRouter>
    );

    expect(await screen.findByRole("button", { name: /期末复习题样例/ })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "生成课程" }));

    const dialog = screen.getByRole("dialog", { name: "从资料生成课程" });
    await user.clear(within(dialog).getByRole("textbox", { name: "课程名称" }));
    await user.type(within(dialog).getByRole("textbox", { name: "课程名称" }), "机器学习期末复习");
    await user.click(within(dialog).getByRole("button", { name: /期末复习题样例/ }));
    await user.click(within(dialog).getByRole("button", { name: "生成课程" }));

    expect(await screen.findByText("资料库建课已跳转")).toBeInTheDocument();
    expect(calls).toContainEqual(
      expect.objectContaining({
        method: "post",
        url: COURSE_ENDPOINTS.fromMaterials,
        payload: {
          material_ids: [302],
          course_title: "机器学习期末复习"
        }
      })
    );
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

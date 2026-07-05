import { render, screen, waitFor, within } from "@testing-library/react";
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
import { PROFILE_ENDPOINTS, type StudentProfileResponse, type ProfileEventResponse } from "../api/profiles";
import { RESOURCE_ENDPOINTS, type GeneratedResource, type ResourceQualityScore } from "../api/resources";
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
                  content: "模型回答：先把监督学习拆成概念、题型和错题三步复习。",
                  citation_json: [],
                  trace_id: "trace_home_model",
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

    expect(screen.queryByRole("status")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "打开资料库" }));

    expect(screen.getByRole("dialog", { name: "资料库" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /数据结构期末题.pdf/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "作为本次对话参考" })).toBeDisabled();

    const material = screen.getByRole("button", { name: /数据结构期末题.pdf/ });

    expect(material).toHaveAttribute("aria-pressed", "false");

    await user.click(material);

    expect(material).toHaveAttribute("aria-pressed", "true");
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "作为本次对话参考" })).toBeEnabled();

    await user.click(screen.getByRole("button", { name: "关闭资料库" }));
    expect(within(screen.getByRole("region", { name: "学习输入区" })).getByText("已选择 1 份资料。")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "发送" }));

    expect(screen.queryByRole("status")).not.toBeInTheDocument();

    await user.type(screen.getByRole("textbox", { name: "学习问题输入" }), "监督学习怎么复习？");
    await user.click(screen.getByRole("button", { name: "联网搜索" }));
    await user.click(screen.getByRole("button", { name: "深度思考" }));
    await user.click(screen.getByRole("button", { name: "发送" }));

    expect(screen.getByRole("button", { name: "联网搜索" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "深度思考" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.queryByText(/联网搜索已开/)).not.toBeInTheDocument();
    expect(screen.queryByText("已生成回答。")).not.toBeInTheDocument();
    expect(screen.getByRole("region", { name: "主页对话" })).toHaveTextContent("监督学习怎么复习？");
  });

  it("does not create local course answers when the course route context is missing", async () => {
    const user = userEvent.setup();
    renderPage(<CourseSpacePage />);

    await user.type(screen.getByRole("textbox", { name: "课程问题输入" }), "监督学习怎么复习？");
    await user.click(screen.getByRole("button", { name: "发送" }));

    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "课程问题输入" })).toHaveValue("监督学习怎么复习？");
    expect(screen.queryByRole("region", { name: "课程即时对话" })).not.toBeInTheDocument();
  });

  it("renders generated course detail and exposes knowledge points in study mode", async () => {
    const user = userEvent.setup();

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
    expect(screen.getByRole("region", { name: "课程提问引导" })).toHaveTextContent("推荐问题");

    await user.click(screen.getByRole("button", { name: "学习模式" }));

    const studyMode = screen.getByRole("region", { name: "课程学习模式" });
    expect(studyMode).toHaveTextContent("梯度下降");
    expect(studyMode).toHaveTextContent("模型评估");
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
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "课程即时对话" })).not.toBeInTheDocument();
    expect(screen.getByRole("region", { name: "历史对话" })).toHaveTextContent("还没有历史对话");
  });

  it("does not render static course history when no real course sessions exist", () => {
    renderPage(<CourseSpacePage />);

    const historyRail = screen.getByRole("region", { name: "历史对话" });

    expect(within(historyRail).queryByRole("button", { name: /解释泛化能力和过拟合的区别/ })).not.toBeInTheDocument();
    expect(historyRail).toHaveTextContent("还没有历史对话");
    expect(screen.queryByLabelText("课程内历史对话")).not.toBeInTheDocument();
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

    expect(screen.queryByRole("status")).not.toBeInTheDocument();

    await user.type(screen.getByRole("textbox", { name: "作答区" }), "需要把局部梯度沿计算图传回参数。");
    await user.click(screen.getByRole("button", { name: "提交答案" }));

    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    expect(screen.getByRole("region", { name: "批改反馈" })).toHaveTextContent("本次批改");
    expect(screen.getByRole("region", { name: "薄弱点复习队列" })).toHaveTextContent("下一题");
  });

  it("generates studio resources through the real resource API", async () => {
    const user = userEvent.setup();
    const calls: Array<{ url?: string; method?: string; data?: unknown; params?: unknown }> = [];
    let resources: GeneratedResource[] = [];
    const quality: ResourceQualityScore[] = [
      {
        id: "3001",
        resource_id: "901",
        score_name: "source_match",
        score_value: 0.55,
        rationale: "模型未配置，使用课程引用 fallback。",
        created_at: "2026-07-05T14:00:00Z"
      }
    ];

    apiClient.defaults.adapter = async (config) => {
      const method = (config.method ?? "get").toLowerCase();
      const url = config.url ?? "";
      const payload = parsePayload(config.data);
      calls.push({ url, method, data: payload, params: config.params });

      if (url === COURSE_ENDPOINTS.list) {
        return {
          data: {
            data: [
              {
                id: "808",
                title: "机器学习期末复习",
                description: "由 1 份资料生成",
                subject: "机器学习",
                source_type: "uploaded",
                status: "ready",
                progress_percent: 0,
                material_count: 1,
                knowledge_point_count: 1,
                chunk_count: 2
              }
            ],
            page: 1,
            page_size: 1,
            total: 1,
            trace_id: "trace_studio_courses"
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
                title: "反向传播",
                summary: "理解链式法则和梯度传递。",
                chapter: "神经网络",
                order_index: 1,
                difficulty: "标准"
              }
            ],
            trace_id: "trace_studio_points"
          },
          status: 200,
          statusText: "OK",
          headers: {},
          config
        };
      }

      if (url === RESOURCE_ENDPOINTS.list) {
        return {
          data: {
            data: resources,
            page: 1,
            page_size: resources.length,
            total: resources.length,
            trace_id: "trace_studio_resources"
          },
          status: 200,
          statusText: "OK",
          headers: {},
          config
        };
      }

      if (url === RESOURCE_ENDPOINTS.generate && method === "post") {
        resources = [
          {
            id: "901",
            course_id: "808",
            knowledge_point_id: "401",
            resource_type: "quiz",
            title: "反向传播练习",
            content_json: {
              markdown: "# 反向传播练习\n\n解释链式法则在计算图里的作用。",
              metadata: {
                agent_trace_id: "trace_resource_studio"
              }
            },
            citation_json: [
              {
                chunk_id: 501,
                source_title: "神经网络讲义.md",
                section_title: "反向传播"
              }
            ],
            status: "completed",
            review_status: "low_evidence",
            confidence_score: 0.55,
            agent_trace_id: "trace_resource_studio",
            created_at: "2026-07-05T14:00:00Z",
            updated_at: "2026-07-05T14:00:00Z"
          }
        ];

        return {
          data: {
            data: {
              agent_trace_id: "trace_resource_studio",
              resources,
              quality_scores: {
                "901": quality
              }
            },
            trace_id: "trace_studio_generate"
          },
          status: 200,
          statusText: "OK",
          headers: {},
          config
        };
      }

      return {
        data: { data: {}, trace_id: "trace_studio_default" },
        status: 200,
        statusText: "OK",
        headers: {},
        config
      };
    };

    renderPage(<StudioPage />);

    await waitFor(() => expect(screen.getByRole("region", { name: "生成队列" })).toHaveTextContent("机器学习期末复习"));
    expect(screen.getByRole("region", { name: "资源生成区" })).not.toHaveTextContent("反向传播练习");

    await waitFor(() => expect(screen.getByLabelText("知识点")).not.toBeDisabled());
    await user.selectOptions(screen.getByLabelText("知识点"), "401");
    await user.click(screen.getByRole("button", { name: "练习" }));
    await user.click(screen.getByRole("button", { name: "生成资源" }));

    await waitFor(() => {
      expect(calls).toContainEqual(
        expect.objectContaining({
          url: RESOURCE_ENDPOINTS.generate,
          method: "post",
          data: {
            course_id: 808,
            knowledge_point_id: 401,
            resource_types: ["doc", "quiz"],
            learning_goal: "",
            difficulty: "medium"
          }
        })
      );
    });
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    expect(screen.getByRole("region", { name: "资源生成区" })).toHaveTextContent("反向传播练习");
    expect(screen.getByRole("region", { name: "资源生成区" })).toHaveTextContent("低依据");
    expect(screen.getByRole("region", { name: "引用来源" })).toHaveTextContent("神经网络讲义.md");
  });

  it("updates profile goals and evidence through the real profile API", async () => {
    const user = userEvent.setup();
    const calls: Array<{ url?: string; method?: string; data?: unknown }> = [];
    let profile: StudentProfileResponse = {
      id: null,
      version: 0,
      has_profile: false,
      profile_json: {
        major_background: "",
        knowledge_foundation: "",
        learning_goal: "",
        cognitive_style: "",
        learning_preference: "",
        weak_points: [],
        learning_pace: "",
        motivation_interest: ""
      },
      confidence_score: 0,
      updated_reason: null,
      updated_at: null,
      next_question: "这门课你最想先解决什么问题？"
    };
    let events: ProfileEventResponse[] = [];

    apiClient.defaults.adapter = async (config) => {
      const method = (config.method ?? "get").toLowerCase();
      const url = config.url ?? "";
      calls.push({ url, method, data: parsePayload(config.data) });

      if (url === PROFILE_ENDPOINTS.me) {
        return { data: { data: profile, trace_id: "trace_profile_me" }, status: 200, statusText: "OK", headers: {}, config };
      }

      if (url === PROFILE_ENDPOINTS.events) {
        return { data: { data: events, trace_id: "trace_profile_events" }, status: 200, statusText: "OK", headers: {}, config };
      }

      if (url === PROFILE_ENDPOINTS.chat && method === "post") {
        const payload = parsePayload(config.data) as { message: string };
        const isGoal = payload.message.includes("两周冲刺软件杯演示");
        const event: ProfileEventResponse = {
          id: String(events.length + 1),
          dimension: "profile_chat",
          change_summary: isGoal ? "更新学习画像：学习目标" : "更新学习画像：薄弱点",
          evidence_json: { source_type: "profile_chat", summary: "学生画像对话" },
          created_at: "2026-07-05T09:01:00Z"
        };
        profile = {
          ...profile,
          id: "7",
          version: profile.version + 1,
          has_profile: true,
          confidence_score: 68,
          updated_reason: event.change_summary,
          updated_at: "2026-07-05T09:01:00Z",
          profile_json: {
            ...profile.profile_json,
            learning_goal: isGoal ? "两周冲刺软件杯演示" : profile.profile_json.learning_goal,
            weak_points: isGoal ? profile.profile_json.weak_points : ["反向传播推导"]
          }
        };
        events = [event, ...events];

        return {
          data: {
            data: {
              reply: "已更新你的学习画像。",
              profile,
              event
            },
            trace_id: "trace_profile_chat"
          },
          status: 200,
          statusText: "OK",
          headers: {},
          config
        };
      }

      return { data: { data: {}, trace_id: "trace_default" }, status: 200, statusText: "OK", headers: {}, config };
    };

    renderPage(<ProfilePage />);

    expect(await screen.findByText("待补充")).toBeInTheDocument();

    await user.click(await screen.findByRole("button", { name: "更新目标" }));
    await user.clear(screen.getByRole("textbox", { name: "学习目标" }));
    await user.type(screen.getByRole("textbox", { name: "学习目标" }), "两周冲刺软件杯演示");
    await user.click(screen.getByRole("button", { name: "保存目标" }));

    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    expect(await screen.findByText("两周冲刺软件杯演示")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "画像证据" })).toHaveTextContent("更新学习画像：学习目标");

    await user.type(screen.getByRole("textbox", { name: "画像问题回答" }), "最担心反向传播推导。");
    await user.click(screen.getByRole("button", { name: "更新画像" }));

    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    expect(await screen.findByText("反向传播推导")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "画像证据" })).toHaveTextContent("更新学习画像：薄弱点");
    expect(calls.filter((call) => call.url === PROFILE_ENDPOINTS.chat)).toEqual([
      { url: PROFILE_ENDPOINTS.chat, method: "post", data: { message: "两周冲刺软件杯演示" } },
      { url: PROFILE_ENDPOINTS.chat, method: "post", data: { message: "最担心反向传播推导。" } }
    ]);
  });

  it("prepares the report export state before real file generation is connected", async () => {
    const user = userEvent.setup();

    renderPage(<ReportsPage />);

    await user.click(screen.getByRole("button", { name: "导出档案" }));

    expect(screen.queryByRole("status")).not.toBeInTheDocument();
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

    expect(await screen.findByRole("button", { name: /课堂截图.png/ })).toBeInTheDocument();
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
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

  it("shows local library feedback when upload fails", async () => {
    const user = userEvent.setup();

    apiClient.defaults.adapter = async (config) => {
      const method = (config.method ?? "get").toLowerCase();
      const url = config.url ?? "";

      if (url === MATERIAL_ENDPOINTS.list && method === "get") {
        return {
          data: { data: [], trace_id: "trace_materials_empty" },
          status: 200,
          statusText: "OK",
          headers: {},
          config
        };
      }

      if (url === MATERIAL_ENDPOINTS.upload && method === "post") {
        throw new Error("upload failed");
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

    const uploadedFile = new File(["demo"], "失败资料.txt", { type: "text/plain" });
    await user.upload(screen.getByLabelText("上传资料文件"), uploadedFile);

    expect(await screen.findByRole("alert")).toHaveTextContent("资料上传失败，请稍后再试。");
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("shows dialog feedback and keeps material selection when course generation fails", async () => {
    const user = userEvent.setup();
    const materials: MaterialListItem[] = [
      {
        id: "501",
        title: "线性代数复习.md",
        type: "MD",
        detail: "已解析",
        modified: "今天",
        size: "12 KB",
        category: "document",
        extension: "MD",
        parse_status: "completed",
        course_ids: []
      }
    ];

    apiClient.defaults.adapter = async (config) => {
      const method = (config.method ?? "get").toLowerCase();
      const url = config.url ?? "";

      if (url === MATERIAL_ENDPOINTS.list && method === "get") {
        return {
          data: { data: materials, trace_id: "trace_materials_course_error" },
          status: 200,
          statusText: "OK",
          headers: {},
          config
        };
      }

      if (url === COURSE_ENDPOINTS.fromMaterials && method === "post") {
        throw new Error("course failed");
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

    expect(await screen.findByRole("button", { name: /线性代数复习.md/ })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "生成课程" }));

    const dialog = screen.getByRole("dialog", { name: "从资料生成课程" });
    const materialButton = within(dialog).getByRole("button", { name: /线性代数复习.md/ });
    await user.click(materialButton);
    await user.click(within(dialog).getByRole("button", { name: "生成课程" }));

    expect(await within(dialog).findByRole("alert")).toHaveTextContent("课程生成失败，请确认选择的是已解析的 TXT 或 Markdown 资料。");
    expect(materialButton).toHaveAttribute("aria-pressed", "true");
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
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

    await waitFor(() => expect(screen.getByRole("button", { name: /腾讯混元默认/ })).toBeInTheDocument());
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    expect(await screen.findByRole("alert")).toHaveTextContent("模型配置已保存。");
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
    await waitFor(() => expect(calls).toContainEqual({
      method: "post",
      url: SETTINGS_ENDPOINTS.defaultConfig(2)
    }));
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("已设为默认模型配置。"));

    await user.click(screen.getByRole("button", { name: "测试连接" }));

    await waitFor(() => expect(calls).toContainEqual({
      method: "post",
      url: SETTINGS_ENDPOINTS.testConfig(2)
    }));
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("模型连接成功。"));

    await user.click(screen.getByRole("button", { name: "删除配置" }));
    await waitFor(() => expect(screen.queryByRole("button", { name: /腾讯混元默认/ })).not.toBeInTheDocument());
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("模型配置已删除。"));
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

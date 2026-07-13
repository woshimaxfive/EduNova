import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { type ReactNode } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { PATHS } from "../app/routePaths";
import { AUTH_ENDPOINTS } from "../api/auth";
import { apiClient } from "../api/client";
import { COURSE_ENDPOINTS } from "../api/courses";
import { DASHBOARD_ENDPOINTS, type DashboardSummary } from "../api/dashboard";
import { MATERIAL_ENDPOINTS, type MaterialListItem } from "../api/materials";
import { PRACTICE_ENDPOINTS } from "../api/practice";
import { PROFILE_ENDPOINTS, type StudentProfileResponse, type ProfileEventResponse } from "../api/profiles";
import { REPORT_ENDPOINTS } from "../api/reports";
import { RESOURCE_ENDPOINTS, type GeneratedResource } from "../api/resources";
import { SETTINGS_ENDPOINTS, type ModelConfigSummary, type ModelSettingsListResponse } from "../api/settings";
import { TUTOR_ENDPOINTS } from "../api/tutor";
import { useAuthStore } from "../features/auth/authStore";
import { makeCompletedAiJob } from "../test/aiJobs";
import { CourseSpacePage } from "./CourseSpacePage";
import { LearningSpacePage } from "./LearningSpacePage";
import { LibraryPage } from "./LibraryPage";
import { PracticePage } from "./PracticePage";
import { ProfilePage } from "./ProfilePage";
import { ReportsPage } from "./ReportsPage";
import { SettingsPage } from "./SettingsPage";
import { StudioPage } from "./StudioPage";

let previousAdapter = apiClient.defaults.adapter;
let previousFetch = globalThis.fetch;

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
    previousFetch = globalThis.fetch;
    localStorage.clear();
    useAuthStore.getState().clearSession();
  });

  afterEach(() => {
    apiClient.defaults.adapter = previousAdapter;
    globalThis.fetch = previousFetch;
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

    globalThis.fetch = vi.fn(async (input, init) => {
      const rawUrl = typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;
      const url = rawUrl.replace(/^https?:\/\/[^/]+/, "").replace(/^\/api\/v1/, "");
      if (url !== TUTOR_ENDPOINTS.stream(session.id)) {
        return new Response(null, { status: 404 });
      }
      const payload = parsePayload(init?.body);
      const question = typeof payload === "object" && payload !== null && "message" in payload ? String(payload.message) : "";
      const detail = {
        session,
        messages: [
          {
            id: "701-u1",
            session_id: session.id,
            role: "user",
            content: question,
            citation_json: [],
            trace_id: null,
            created_at: "2026-07-03T12:00:30Z"
          },
          {
            id: "701-a1",
            session_id: session.id,
            role: "assistant",
            content: "## 监督学习复习\n\n先把概念、题型和错题拆成三步复习。",
            citation_json: [],
            trace_id: "trace_home_model",
            created_at: "2026-07-03T12:01:00Z"
          }
        ]
      };
      const body = [
        ["metadata", { session_id: session.id, trace_id: "trace_home_model", workflow: "home_tutor", citation_count: 0, used_model: true }],
        ["status", { stage: "answer", label: "正在生成回答" }],
        ["sources", { citations: [], warnings: [] }],
        ["token", { content: "## 监督学习复习\n\n先把概念、题型和错题拆成三步复习。" }],
        ["done", detail]
      ]
        .map(([event, data]) => `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`)
        .join("");

      return new Response(body, { status: 200, headers: { "Content-Type": "text/event-stream; charset=utf-8" } });
    });

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

    await user.click(screen.getByRole("button", { name: "作为本次对话参考" }));
    const composer = within(screen.getByRole("region", { name: "学习输入区" }));
    expect(composer.getByText("数据结构期末题.pdf")).toBeInTheDocument();
    expect(composer.getByText("共 1 份")).toBeInTheDocument();
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
  }, 15_000);

  it("does not create local course answers when the course route context is missing", async () => {
    const user = userEvent.setup();
    renderPage(<CourseSpacePage />);

    fireEvent.change(screen.getByRole("textbox", { name: "课程问题输入" }), {
      target: { value: "监督学习怎么复习？" },
    });
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

    await user.click(screen.getByRole("button", { name: "课程内容" }));

    const studyMode = screen.getByRole("region", { name: "课程内容模式" });
    expect(studyMode).toHaveTextContent("梯度下降");
    expect(studyMode).toHaveTextContent("模型评估");
  });

  it("keeps question practice and reports as course-context actions", async () => {
    const user = userEvent.setup();

    renderWithProviders(
      <MemoryRouter initialEntries={["/app/courses/808"]}>
        <Routes>
          <Route path={PATHS.courseDetail} element={<CourseSpacePage />} />
        </Routes>
      </MemoryRouter>
    );

    const courseActions = screen.getByRole("navigation", { name: "课程行动入口" });
    const expectedActions = [
      ["开始练习", `${PATHS.practice}?course_id=808`],
      ["查看学习报告", `${PATHS.reports}?course_id=808`]
    ] as const;

    for (const [label, path] of expectedActions) {
      expect(within(courseActions).getByRole("link", { name: label })).toHaveAttribute("href", path);
    }

    await user.click(within(courseActions).getByRole("link", { name: "开始提问" }));
    expect(screen.getByRole("textbox", { name: "课程问题输入" })).toHaveFocus();
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

  it("creates a real practice session and acknowledges submitted answers", async () => {
    const user = userEvent.setup();
    const session = {
      id: "501",
      course_id: "808",
      title: "机器学习期末复习 练习",
      status: "in_progress",
      score: null,
      questions: [
        {
          id: "q1",
          question_type: "short_answer",
          knowledge_point_id: "401",
          knowledge_point_title: "反向传播",
          prompt: "请解释反向传播的复习重点。",
          options: [],
          correct_answer: null,
          keywords: ["局部梯度", "计算图"],
          explanation: "围绕课程引用说明。",
          difficulty: "medium"
        }
      ],
      answers: [],
      created_at: "2026-07-05T10:00:00Z",
      updated_at: "2026-07-05T10:00:00Z"
    };
    apiClient.defaults.adapter = async (config) => {
      const method = (config.method ?? "get").toLowerCase();
      const url = config.url ?? "";

      if (url === COURSE_ENDPOINTS.list) {
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
                knowledge_point_count: 1,
                chunk_count: 5
              }
            ],
            trace_id: "trace_practice_courses"
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
                summary: "理解局部梯度和计算图。",
                chapter: "神经网络",
                order_index: 0,
                difficulty: null
              }
            ],
            trace_id: "trace_practice_points"
          },
          status: 200,
          statusText: "OK",
          headers: {},
          config
        };
      }

      if (url === PRACTICE_ENDPOINTS.sessions && method === "post") {
        return {
          data: { data: session, trace_id: "trace_practice_create" },
          status: 200,
          statusText: "OK",
          headers: {},
          config
        };
      }

      if (url === PRACTICE_ENDPOINTS.answers(501) && method === "post") {
        return {
          data: {
            data: {
              ...session,
              status: "completed",
              score: 100,
              answers: [
                {
                  question_id: "q1",
                  answer_text: "需要把局部梯度沿计算图传回参数。",
                  is_correct: true,
                  feedback: {
                    score: 100,
                    message: "已掌握关键依据。",
                    matched_keywords: ["局部梯度", "计算图"],
                    missing_keywords: [],
                    explanation: "围绕课程引用说明。"
                  }
                }
              ],
              updated_at: "2026-07-05T10:05:00Z"
            },
            trace_id: "trace_practice_submit"
          },
          status: 200,
          statusText: "OK",
          headers: {},
          config
        };
      }

      return { data: { data: {}, trace_id: "trace_practice_default" }, status: 200, statusText: "OK", headers: {}, config };
    };

    renderPage(<PracticePage />);

    await screen.findByRole("heading", { name: "反向传播" });
    const startPractice = screen.getByRole("button", { name: "开始针对性练习" });
    expect(startPractice).toBeEnabled();
    await user.click(startPractice);
    const settingsDrawer = await screen.findByRole("dialog", { name: "练习设置" });
    await user.click(within(settingsDrawer).getByRole("button", { name: "开始针对性练习" }));

    await user.type(await screen.findByRole("textbox", { name: "q1 作答区" }), "需要把局部梯度沿计算图传回参数。");
    await user.click(screen.getByRole("button", { name: "提交练习" }));

    const result = await screen.findByRole("region", { name: "练习结果摘要" });
    expect(result).toHaveTextContent("100");
    expect(screen.getByRole("button", { name: /回答正确 · 得分 100/ })).toHaveTextContent("已掌握关键依据。");
  });

  it("generates studio resources through the real resource API", async () => {
    const user = userEvent.setup();
    const calls: Array<{ url?: string; method?: string; data?: unknown; params?: unknown }> = [];
    let resources: GeneratedResource[] = [];
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

      if (url === RESOURCE_ENDPOINTS.generationJobs && method === "post") {
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
            data: makeCompletedAiJob({ result: { course_id: "808", resource_ids: ["901"] } }),
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

    await waitFor(() => expect(screen.getByRole("combobox", { name: "资源课程" })).toHaveValue("808"));
    expect(screen.getByRole("main", { name: "成果画布" })).not.toHaveTextContent("反向传播练习");

    await user.click(within(screen.getByRole("banner", { name: "资源工坊工具栏" })).getByRole("button", { name: "新建资源" }));
    const generateDrawer = screen.getByRole("dialog", { name: "生成设置" });
    await waitFor(() => expect(within(generateDrawer).getByRole("combobox", { name: "生成知识点" })).not.toBeDisabled());
    await user.selectOptions(within(generateDrawer).getByRole("combobox", { name: "生成知识点" }), "401");
    await user.click(within(generateDrawer).getByRole("checkbox", { name: "练习" }));
    await user.click(within(generateDrawer).getByRole("button", { name: "开始生成" }));

    await waitFor(() => {
      expect(calls).toContainEqual(
        expect.objectContaining({
          url: RESOURCE_ENDPOINTS.generationJobs,
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
    expect(await screen.findByRole("region", { name: "资源完整内容" })).toHaveTextContent("反向传播练习");
    expect(screen.getByRole("region", { name: "资源完整内容" })).toHaveTextContent("低依据");
    await user.click(screen.getByRole("button", { name: "成果详情" }));
    await user.click(screen.getByRole("tab", { name: "来源" }));
    expect(screen.getByRole("tabpanel", { name: "引用来源" })).toHaveTextContent("神经网络讲义.md");
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
      dimension_confidence: {},
      evidence_summary: { applied_count: 0, candidate_count: 0 },
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
          evidence_json: {
            source_type: "profile_chat",
            summary: "学生画像对话",
            updated_dimensions: [isGoal ? "learning_goal" : "weak_points"],
            candidate_dimensions: []
          },
          source_type: "profile_chat",
          status: "applied",
          confidence_score: 0.68,
          agent_trace_id: isGoal ? "trace_profile_goal" : "trace_profile_weakness",
          created_at: "2026-07-05T09:01:00Z"
        };
        profile = {
          ...profile,
          id: "7",
          version: profile.version + 1,
          has_profile: true,
          confidence_score: 68,
          dimension_confidence: {
            ...profile.dimension_confidence,
            [isGoal ? "learning_goal" : "weak_points"]: 68
          },
          evidence_summary: {
            applied_count: events.length + 1,
            candidate_count: 0
          },
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
              event,
              agent_trace_id: event.agent_trace_id
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

    expect(await screen.findByRole("region", { name: "动态学习画像工作台" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "更新目标" })).not.toBeInTheDocument();

    await user.type(screen.getByRole("textbox", { name: "画像问题回答" }), "两周冲刺软件杯演示");
    await user.click(screen.getByRole("button", { name: "更新画像" }));

    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    expect((await screen.findAllByText("两周冲刺软件杯演示")).length).toBeGreaterThan(0);
    expect(screen.getByRole("region", { name: "本次画像更新" })).toHaveTextContent("已应用学习目标");

    await user.type(screen.getByRole("textbox", { name: "画像问题回答" }), "最担心反向传播推导。");
    await user.click(screen.getByRole("button", { name: "更新画像" }));

    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    expect((await screen.findAllByText("反向传播推导")).length).toBeGreaterThan(0);
    expect(screen.getByRole("region", { name: "本次画像更新" })).toHaveTextContent("已应用学习难点");
    expect(calls.filter((call) => call.url === PROFILE_ENDPOINTS.chat)).toEqual([
      { url: PROFILE_ENDPOINTS.chat, method: "post", data: { message: "两周冲刺软件杯演示" } },
      { url: PROFILE_ENDPOINTS.chat, method: "post", data: { message: "最担心反向传播推导。" } }
    ]);
  });

  it("generates and renders a real learning report", async () => {
    const user = userEvent.setup();
    let reportReady = false;
    apiClient.defaults.adapter = async (config) => {
      const method = (config.method ?? "get").toLowerCase();
      const url = config.url ?? "";

      if (url === COURSE_ENDPOINTS.list) {
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
                knowledge_point_count: 1,
                chunk_count: 5
              }
            ],
            trace_id: "trace_report_courses"
          },
          status: 200,
          statusText: "OK",
          headers: {},
          config
        };
      }

      if (url === REPORT_ENDPOINTS.latest) {
        return {
          data: {
            data: reportReady
              ? {
                  id: "901",
                  course_id: "808",
                  practice_session_id: "501",
                  status: "ready",
                  score: 80,
                  report: {
                    summary: "本次评估得分 80，基于真实练习作答生成。",
                    mastery_update: { weak_count: 1, mastered_count: 2, learning_count: 1 },
                    weakness_list: [{ knowledge_point_id: "401", title: "反向传播", source_type: "practice_assessment" }],
                    evidence_refs: [{ practice_answer_id: "601", knowledge_point_id: "401", score: 50 }],
                    next_step_suggestions: ["优先复习反向传播。"],
                    review_queue_updates: [{ title: "反向传播", status: "confirmed", source_type: "practice_assessment" }],
                    profile_changes: []
                  },
                  created_at: "2026-07-05T10:10:00Z"
                }
              : {
                  id: null,
                  course_id: "808",
                  practice_session_id: null,
                  status: "empty",
                  score: null,
                  report: {
                    summary: "还没有真实学习报告。",
                    mastery_update: { weak_count: 0, mastered_count: 0, learning_count: 0 },
                    weakness_list: [],
                    evidence_refs: [],
                    next_step_suggestions: [],
                    review_queue_updates: [],
                    profile_changes: []
                  },
                  created_at: null
                },
            trace_id: "trace_report_latest"
          },
          status: 200,
          statusText: "OK",
          headers: {},
          config
        };
      }

      if (url === REPORT_ENDPOINTS.generate && method === "post") {
        reportReady = true;
        return {
          data: {
            data: {
              id: "901",
              course_id: "808",
              practice_session_id: "501",
              status: "ready",
              score: 80,
              report: {
                summary: "本次评估得分 80，基于真实练习作答生成。",
                mastery_update: { weak_count: 1, mastered_count: 2, learning_count: 1 },
                weakness_list: [{ knowledge_point_id: "401", title: "反向传播", source_type: "practice_assessment" }],
                evidence_refs: [{ practice_answer_id: "601", knowledge_point_id: "401", score: 50 }],
                next_step_suggestions: ["优先复习反向传播。"],
                review_queue_updates: [{ title: "反向传播", status: "confirmed", source_type: "practice_assessment" }],
                profile_changes: []
              },
              created_at: "2026-07-05T10:10:00Z"
            },
            trace_id: "trace_report_generate"
          },
          status: 200,
          statusText: "OK",
          headers: {},
          config
        };
      }

      if (url === PRACTICE_ENDPOINTS.recent) {
        return {
          data: {
            data: reportReady
              ? [{
                  id: "501",
                  course_id: "808",
                  title: "机器学习期末复习练习",
                  status: "completed",
                  score: 80,
                  effective_difficulty: "medium",
                  created_at: "2026-07-05T09:00:00Z",
                  updated_at: "2026-07-05T10:00:00Z"
                }]
              : [],
            trace_id: "trace_report_practice"
          },
          status: 200,
          statusText: "OK",
          headers: {},
          config
        };
      }

      return { data: { data: {}, trace_id: "trace_report_default" }, status: 200, statusText: "OK", headers: {}, config };
    };

    renderPage(<ReportsPage />);

    await user.click(await screen.findByRole("button", { name: "生成学习报告" }));

    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    expect(await screen.findByText("本次评估得分 80，基于真实练习作答生成。")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "最近报告快照" })).toHaveTextContent("本次评估得分 80");
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

      if (url === MATERIAL_ENDPOINTS.detail(301) && method === "get") {
        return {
          data: {
            data: {
              ...materials.find((material) => material.id === "301"),
              filename: "AI 导论讲义.docx",
              content_type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
              extracted_text_preview: "监督学习通过标注样本学习输入与输出之间的关系。",
              chunk_count: 4,
              section_count: 2,
              page_count: 6,
              sections: [
                { section_title: "监督学习", page_number: 2, chunk_count: 2, preview: "监督学习使用标注样本。" },
                { section_title: "模型评估", page_number: 5, chunk_count: 2, preview: "使用验证集评估模型。" }
              ],
              linked_courses: [{ id: "101", title: "人工智能导论", usage_type: "reference" }],
              agent_trace_id: "trace_material_detail"
            },
            trace_id: "trace_material_detail"
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
    expect(screen.getByText("已入库")).toBeInTheDocument();
    expect(screen.queryByText("等待提取说明")).not.toBeInTheDocument();
    expect(calls).toContainEqual({ method: "post", url: MATERIAL_ENDPOINTS.upload });

    await user.click(screen.getByRole("button", { name: "图片" }));

    expect(screen.getByRole("button", { name: "图片" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: /课堂截图.png/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /AI 导论讲义/ })).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "全部" }));
    await user.click(screen.getByRole("button", { name: /查看AI 导论讲义/ }));

    const detailDrawer = screen.getByRole("dialog", { name: /AI 导论讲义/ });
    expect(detailDrawer).toBeInTheDocument();
    expect(await within(detailDrawer).findByText("监督学习通过标注样本学习输入与输出之间的关系。")).toBeInTheDocument();
    await user.click(within(detailDrawer).getByRole("tab", { name: "章节" }));
    expect(within(detailDrawer).getByText("模型评估")).toBeInTheDocument();
    await user.click(within(detailDrawer).getByRole("button", { name: "生成课程" }));

    const courseDialog = screen.getByRole("dialog", { name: "从资料生成课程" });
    expect(courseDialog).toBeInTheDocument();
    const courseMaterial = within(courseDialog).getByRole("button", { name: /AI 导论讲义/ });

    expect(courseMaterial).toHaveAttribute("aria-pressed", "true");
    expect(within(courseDialog).getByRole("button", { name: "生成课程" })).toBeEnabled();

  });

  it("compares selected course materials without blocking other library actions", async () => {
    const user = userEvent.setup();
    const calls: Array<{ method: string; url: string; payload: unknown }> = [];
    const materials: MaterialListItem[] = [
      {
        id: "301",
        title: "AI 导论讲义.md",
        type: "MD",
        detail: "已解析",
        modified: "今天",
        size: "12 KB",
        category: "document",
        extension: "MD",
        parse_status: "completed",
        course_ids: ["101"]
      },
      {
        id: "302",
        title: "期末样题.md",
        type: "MD",
        detail: "已解析",
        modified: "今天",
        size: "8 KB",
        category: "document",
        extension: "MD",
        parse_status: "completed",
        course_ids: ["101"]
      },
      {
        id: "303",
        title: "课堂截图.png",
        type: "PNG",
        detail: "仅入库，暂不做 OCR",
        modified: "今天",
        size: "20 KB",
        category: "image",
        extension: "PNG",
        parse_status: "uploaded",
        course_ids: ["101"]
      },
      {
        id: "304",
        title: "其他课程资料.md",
        type: "MD",
        detail: "已解析",
        modified: "昨天",
        size: "6 KB",
        category: "document",
        extension: "MD",
        parse_status: "completed",
        course_ids: ["202"]
      }
    ];

    apiClient.defaults.adapter = async (config) => {
      const method = (config.method ?? "get").toLowerCase();
      const url = config.url ?? "";
      calls.push({ method, url, payload: parsePayload(config.data) });

      if (url === MATERIAL_ENDPOINTS.list && method === "get") {
        return {
          data: { data: materials, trace_id: "trace_materials_compare_list" },
          status: 200,
          statusText: "OK",
          headers: {},
          config
        };
      }

      if (url === COURSE_ENDPOINTS.list && method === "get") {
        return {
          data: {
            data: [
              {
                id: "101",
                title: "人工智能导论",
                description: "由资料生成",
                subject: "人工智能",
                source_type: "uploaded",
                status: "ready",
                progress_percent: 0,
                material_count: 2,
                knowledge_point_count: 3,
                chunk_count: 4
              }
            ],
            trace_id: "trace_materials_compare_courses"
          },
          status: 200,
          statusText: "OK",
          headers: {},
          config
        };
      }

      if (url === MATERIAL_ENDPOINTS.compare && method === "post") {
        return {
          data: {
            data: {
              course_id: "101",
              material_ids: ["301", "302"],
              summary: {
                compared_material_count: 2,
                comparable_material_count: 2,
                matched_concept_count: 4,
                citation_count: 2,
                message: "已基于课程知识切片和安全短摘录完成资料对比。"
              },
              repeated_concepts: [
                {
                  title: "启发式搜索",
                  material_ids: ["301", "302"],
                  source_titles: ["AI 导论讲义.md", "期末样题.md"],
                  reason: "多份资料重复出现。",
                  confidence: "high",
                  support_count: 2,
                  knowledge_point_id: "401"
                }
              ],
              exam_likely_points: [
                {
                  title: "启发式搜索",
                  material_ids: ["301", "302"],
                  source_titles: ["AI 导论讲义.md", "期末样题.md"],
                  reason: "疑似考点。",
                  confidence: "high",
                  support_count: 2,
                  knowledge_point_id: "401"
                }
              ],
              materials_only_points: [{ title: "反向传播", material_ids: ["301"], source_titles: ["AI 导论讲义.md"], reason: "单资料独有。", confidence: "medium", support_count: 1, knowledge_point_id: "402" }],
              questions_only_points: [{ title: "监督学习", material_ids: ["302"], source_titles: ["期末样题.md"], reason: "样题独有。", confidence: "medium", support_count: 1, knowledge_point_id: null }],
              missing_review_points: [{ title: "AI 伦理", material_ids: [], source_titles: [], reason: "所选资料暂未覆盖。", confidence: "low", support_count: 0, knowledge_point_id: "403" }],
              priority_order: [{ title: "启发式搜索", material_ids: ["301", "302"], source_titles: ["AI 导论讲义.md", "期末样题.md"], reason: "优先复习。", confidence: "high", support_count: 2, knowledge_point_id: "401" }],
              citations: [
                {
                  id: "m301-1",
                  material_id: "301",
                  source_title: "AI 导论讲义.md",
                  section_title: "启发式搜索",
                  page_number: null,
                  excerpt: "启发式搜索使用启发函数。",
                  confidence: "high"
                }
              ]
            },
            trace_id: "trace_materials_compare"
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

    await user.click(await screen.findByRole("button", { name: "资料对比" }));
    const compareDrawer = screen.getByRole("dialog", { name: "资料对比" });
    expect(within(compareDrawer).getByRole("button", { name: "生成资料对比" })).toBeDisabled();
    expect(screen.getByRole("button", { name: /课堂截图.png，图片暂不参与资料对比/ })).toBeDisabled();
    expect(screen.getByRole("button", { name: /其他课程资料.md/ })).toBeEnabled();

    await user.click(screen.getByRole("button", { name: /选择AI 导论讲义.md/ }));
    await user.click(screen.getByRole("button", { name: /选择期末样题.md/ }));
    await user.click(within(compareDrawer).getByRole("button", { name: "生成资料对比" }));

    const resultDrawer = await screen.findByRole("dialog", { name: "对比结果" });
    expect((await within(resultDrawer).findAllByText("启发式搜索")).length).toBeGreaterThan(1);
    await user.click(within(resultDrawer).getByRole("tab", { name: "差异遗漏" }));
    expect(resultDrawer).toHaveTextContent("反向传播");
    expect(resultDrawer).toHaveTextContent("监督学习");
    expect(resultDrawer).toHaveTextContent("AI 伦理");
    await user.click(within(resultDrawer).getByRole("tab", { name: "来源与轨迹" }));
    expect(resultDrawer).toHaveTextContent("启发式搜索使用启发函数。");
    expect(screen.getByRole("button", { name: "上传资料" })).toBeEnabled();
    expect(calls).toContainEqual({
      method: "post",
      url: MATERIAL_ENDPOINTS.compare,
      payload: { course_id: 101, material_ids: [301, 302] }
    });
  });

  it("keeps material comparison errors inside the comparison panel", async () => {
    const user = userEvent.setup();
    const materials: MaterialListItem[] = [
      {
        id: "301",
        title: "AI 导论讲义.md",
        type: "MD",
        detail: "已解析",
        modified: "今天",
        size: "12 KB",
        category: "document",
        extension: "MD",
        parse_status: "completed",
        course_ids: ["101"]
      },
      {
        id: "302",
        title: "期末样题.md",
        type: "MD",
        detail: "已解析",
        modified: "今天",
        size: "8 KB",
        category: "document",
        extension: "MD",
        parse_status: "completed",
        course_ids: ["101"]
      }
    ];

    apiClient.defaults.adapter = async (config) => {
      const method = (config.method ?? "get").toLowerCase();
      const url = config.url ?? "";

      if (url === MATERIAL_ENDPOINTS.list && method === "get") {
        return { data: { data: materials, trace_id: "trace_compare_error_materials" }, status: 200, statusText: "OK", headers: {}, config };
      }

      if (url === COURSE_ENDPOINTS.list && method === "get") {
        return {
          data: {
            data: [
              {
                id: "101",
                title: "人工智能导论",
                description: "由资料生成",
                subject: "人工智能",
                source_type: "uploaded",
                status: "ready",
                progress_percent: 0,
                material_count: 2,
                knowledge_point_count: 3,
                chunk_count: 4
              }
            ],
            trace_id: "trace_compare_error_courses"
          },
          status: 200,
          statusText: "OK",
          headers: {},
          config
        };
      }

      if (url === MATERIAL_ENDPOINTS.compare && method === "post") {
        throw new Error("compare failed");
      }

      return { data: { data: {}, trace_id: "trace_default" }, status: 200, statusText: "OK", headers: {}, config };
    };

    renderPage(<LibraryPage />);

    await user.click(await screen.findByRole("button", { name: "资料对比" }));
    const compareDrawer = screen.getByRole("dialog", { name: "资料对比" });
    await user.click(screen.getByRole("button", { name: /选择AI 导论讲义.md/ }));
    await user.click(screen.getByRole("button", { name: /选择期末样题.md/ }));
    await user.click(within(compareDrawer).getByRole("button", { name: "生成资料对比" }));

    expect(await within(compareDrawer).findByRole("alert")).toHaveTextContent("资料对比失败，请稍后重试。");
    expect(screen.getByRole("button", { name: "上传资料" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "生成课程" })).toBeEnabled();
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

      if (url === COURSE_ENDPOINTS.fromMaterialsJobs && method === "post") {
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

    expect(await within(dialog).findByRole("alert")).toHaveTextContent("课程生成失败，请确认选择的是已解析资料。");
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

    useAuthStore.getState().setSession({
      token: "settings-token",
      user: {
        id: 77,
        email: "settings@edunova.local",
        displayName: "设置学生",
        role: "student",
        starterMode: "blank"
      }
    });

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
              operation: "chat",
              model: "hunyuan-turbos-latest",
              code: null,
              retryable: false,
              tested_at: "2026-07-13T09:30:00Z",
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

      if (url === AUTH_ENDPOINTS.me && method === "patch") {
        return {
          data: {
            data: {
              id: 77,
              email: "settings@edunova.local",
              display_name: (payload as { display_name: string }).display_name,
              role: "student",
              starter_mode: "blank"
            },
            trace_id: "trace_auth_update"
          },
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
        embedding_model: "",
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

    await user.click(screen.getByRole("button", { name: "测试回答模型" }));

    await waitFor(() => expect(calls).toContainEqual({
      method: "post",
      url: SETTINGS_ENDPOINTS.testConfig(2),
      payload: { operation: "chat" }
    }));
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("模型连接成功。"));

    await user.click(screen.getByRole("button", { name: "删除配置" }));
    const deleteDialog = screen.getByRole("dialog", { name: "删除模型配置" });
    expect(within(deleteDialog).getByText(/如果它是默认配置/)).toBeInTheDocument();
    await user.click(within(deleteDialog).getByRole("button", { name: "确认删除" }));
    await waitFor(() => expect(screen.queryByRole("button", { name: /腾讯混元默认/ })).not.toBeInTheDocument());
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("模型配置已删除。"));

    await user.click(screen.getByRole("button", { name: /账号安全/ }));
    expect(screen.getByRole("textbox", { name: "昵称" })).toHaveValue("设置学生");
    await user.clear(screen.getByRole("textbox", { name: "昵称" }));
    await user.type(screen.getByRole("textbox", { name: "昵称" }), "新设置学生");
    await user.click(screen.getByRole("button", { name: "保存昵称" }));

    await waitFor(() => expect(calls).toContainEqual({
      method: "patch",
      url: AUTH_ENDPOINTS.me,
      payload: {
        display_name: "新设置学生"
      }
    }));
    expect(useAuthStore.getState().user?.displayName).toBe("新设置学生");
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("昵称已更新。"));
  });

  it("validates password changes and clears the current session after success", async () => {
    const user = userEvent.setup();
    const calls: Array<{ method: string; url: string; payload: unknown }> = [];

    useAuthStore.getState().setSession({
      token: "password-token",
      user: {
        id: 88,
        email: "password@edunova.local",
        displayName: "密码学生",
        role: "student",
        starterMode: "blank"
      }
    });

    apiClient.defaults.adapter = async (config) => {
      const method = (config.method ?? "get").toLowerCase();
      const url = config.url ?? "";
      const payload = parsePayload(config.data);
      calls.push({ method, url, payload });

      if (url === SETTINGS_ENDPOINTS.configs && method === "get") {
        return {
          data: {
            data: {
              configs: [],
              default_config_id: null,
              system_summary: {
                source: "system",
                provider: "openai_compatible",
                base_url: "https://system-model.example.local/v1",
                chat_model: "system-chat",
                embedding_model: null,
                has_api_key: true,
                api_key_masked: "sk-s...cret",
                can_use_model: true
              }
            },
            trace_id: "trace_settings_password"
          },
          status: 200,
          statusText: "OK",
          headers: {},
          config
        };
      }

      if (url === AUTH_ENDPOINTS.password && method === "patch") {
        return {
          data: { data: { ok: true }, trace_id: "trace_password_changed" },
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
      <MemoryRouter initialEntries={[`${PATHS.settings}?section=account`]}>
        <Routes>
          <Route path={PATHS.settings} element={<SettingsPage />} />
          <Route path={PATHS.login} element={<div>密码修改后登录页</div>} />
        </Routes>
      </MemoryRouter>
    );

    expect(await screen.findByRole("heading", { name: "账号安全" })).toBeInTheDocument();
    await user.type(screen.getByLabelText("当前密码"), "Password123");
    await user.type(screen.getByLabelText("新密码"), "NewPassword456");
    await user.type(screen.getByLabelText("确认新密码"), "Different789");
    await user.click(screen.getByRole("button", { name: "更新密码并退出登录" }));

    expect(screen.getByRole("alert")).toHaveTextContent("两次输入的新密码不一致。");
    expect(calls.some((call) => call.url === AUTH_ENDPOINTS.password)).toBe(false);

    await user.clear(screen.getByLabelText("确认新密码"));
    await user.type(screen.getByLabelText("确认新密码"), "NewPassword456");
    await user.click(screen.getByRole("button", { name: "更新密码并退出登录" }));

    await waitFor(() => expect(calls).toContainEqual({
      method: "patch",
      url: AUTH_ENDPOINTS.password,
      payload: {
        current_password: "Password123",
        new_password: "NewPassword456"
      }
    }));
    expect(await screen.findByText("密码修改后登录页")).toBeInTheDocument();
    expect(useAuthStore.getState().token).toBeNull();
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

      if (url === COURSE_ENDPOINTS.fromMaterialsJobs && method === "post") {
        return {
          data: {
            data: makeCompletedAiJob({ workflow: "course_builder", course_id: null, result: { course_id: "808" } }),
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
        url: COURSE_ENDPOINTS.fromMaterialsJobs,
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

    expect(screen.getByRole("heading", { name: /准备好一起学习了吗/ })).toBeInTheDocument();
  });
});

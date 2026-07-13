import { render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { type ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { apiClient } from "../api/client";
import { COURSE_ENDPOINTS } from "../api/courses";
import { DASHBOARD_ENDPOINTS } from "../api/dashboard";
import { MATERIAL_ENDPOINTS, type MaterialListItem } from "../api/materials";
import { PRACTICE_ENDPOINTS } from "../api/practice";
import { PROFILE_ENDPOINTS } from "../api/profiles";
import { REPORT_ENDPOINTS } from "../api/reports";
import { SETTINGS_ENDPOINTS } from "../api/settings";
import { LibraryPage } from "./LibraryPage";
import { PracticePage } from "./PracticePage";
import { ProfilePage } from "./ProfilePage";
import { ReportsPage } from "./ReportsPage";
import { SettingsPage } from "./SettingsPage";
import { StudioPage } from "./StudioPage";

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

function renderRoutePage(page: ReactNode, path: string) {
  renderWithProviders(<MemoryRouter initialEntries={[path]}>{page}</MemoryRouter>);
}

describe("student core pages", () => {
  beforeEach(() => {
    previousAdapter = apiClient.defaults.adapter;
    apiClient.defaults.adapter = async (config) => {
      const method = (config.method ?? "get").toLowerCase();
      if (config.url === MATERIAL_ENDPOINTS.list) {
        const materials: MaterialListItem[] = [
          {
            id: "301",
            title: "AI 导论讲义",
            type: "DOCX",
            detail: "12 个知识点",
            modified: "今天",
            size: "1.2 MB",
            category: "document",
            extension: "DOCX",
            parse_status: "completed",
            course_ids: ["101"]
          }
        ];

        return {
          data: { data: materials, trace_id: "trace_core_materials" },
          status: 200,
          statusText: "OK",
          headers: {},
          config
        };
      }

      if (config.url === DASHBOARD_ENDPOINTS.summary) {
        return {
          data: {
            data: {
              profile_summary: {
                display_name: "核心页面学生",
                starter_mode: "ai_intro",
                has_profile: true,
                knowledge_foundation: "机器学习刚入门",
                learning_goal: "期末前掌握神经网络"
              },
              recent_conversations: [
                {
                  id: "701",
                  title: "主页历史会话",
                  meta: "今天",
                  scope: "home",
                  updated_at: "2026-07-07T09:00:00Z"
                }
              ],
              recent_courses: [],
              material_library_summary: {
                material_count: 1,
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
                kind: "active",
                title: "继续学习",
                description: "从最近内容继续。",
                action_label: "继续学习"
              }
            },
            trace_id: "trace_core_dashboard"
          },
          status: 200,
          statusText: "OK",
          headers: {},
          config
        };
      }

      if (config.url === SETTINGS_ENDPOINTS.configs) {
        return {
          data: {
            data: {
              configs: [],
              default_config_id: null,
              system_summary: {
                source: "none",
                provider: "openai_compatible",
                base_url: null,
                chat_model: null,
                embedding_model: null,
                has_api_key: false,
                api_key_masked: null,
                can_use_model: false
              }
            },
            trace_id: "trace_core_settings"
          },
          status: 200,
          statusText: "OK",
          headers: {},
          config
        };
      }

      if (config.url === COURSE_ENDPOINTS.knowledgePoints(808)) {
        return {
          data: {
            data: [
              {
                id: "401",
                title: "启发式搜索",
                summary: "理解启发函数。",
                chapter: "搜索问题",
                order_index: 0,
                difficulty: null
              }
            ],
            trace_id: "trace_core_points"
          },
          status: 200,
          statusText: "OK",
          headers: {},
          config
        };
      }

      if (config.url === PRACTICE_ENDPOINTS.sessions && method === "post") {
        return {
          data: {
            data: {
              id: "501",
              course_id: "808",
              title: "AI 搜索复习 练习",
              status: "in_progress",
              score: null,
              questions: [
                {
                  id: "q1",
                  question_type: "short_answer",
                  knowledge_point_id: "401",
                  knowledge_point_title: "启发式搜索",
                  prompt: "请解释启发式搜索的复习重点。",
                  options: [],
                  correct_answer: null,
                  keywords: ["启发函数"],
                  explanation: "围绕课程引用说明。",
                  difficulty: "medium"
                }
              ],
              answers: [],
              created_at: "2026-07-05T10:00:00Z",
              updated_at: "2026-07-05T10:00:00Z"
            },
            trace_id: "trace_core_practice"
          },
          status: 200,
          statusText: "OK",
          headers: {},
          config
        };
      }

      if (config.url === REPORT_ENDPOINTS.latest) {
        return {
          data: {
            data: {
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
            trace_id: "trace_core_report"
          },
          status: 200,
          statusText: "OK",
          headers: {},
          config
        };
      }

      if (config.url === PROFILE_ENDPOINTS.me) {
        return {
          data: {
            data: {
              id: "77",
              version: 2,
              has_profile: true,
              profile_json: {
                major_background: "计算机专业大二",
                knowledge_foundation: "机器学习刚入门",
                learning_goal: "期末前掌握神经网络",
                cognitive_style: "案例驱动",
                learning_preference: "图解和代码",
                weak_points: ["链式法则"],
                learning_pace: "每天 45 分钟",
                motivation_interest: "提升 AI 实践能力"
              },
              confidence_score: 72,
              completeness_score: 100,
              evidence_confidence_score: 72,
              applied_version: 5,
              dimension_confidence: {
                major_background: 72,
                knowledge_foundation: 68,
                learning_goal: 88,
                cognitive_style: 63,
                learning_preference: 70,
                weak_points: 76,
                learning_pace: 58,
                motivation_interest: 66
              },
              evidence_summary: { applied_count: 5, candidate_count: 1 },
              updated_reason: "更新学习画像：学习目标、基础",
              updated_at: "2026-07-05T09:00:00Z",
              next_question: "这门课你最担心哪一章？",
              next_question_dimension: "weak_points"
            },
            trace_id: "trace_profile_me"
          },
          status: 200,
          statusText: "OK",
          headers: {},
          config
        };
      }

      if (config.url === PROFILE_ENDPOINTS.events) {
        return {
          data: {
            data: [
              {
                id: "91",
                dimension: "profile_chat",
                change_summary: "更新学习画像：学习目标、基础",
                evidence_json: {
                  source_type: "profile_chat",
                  summary: "学生画像对话",
                  updated_dimensions: ["learning_goal", "knowledge_foundation"],
                  candidate_dimensions: []
                },
                source_type: "profile_chat",
                status: "applied",
                confidence_score: 0.82,
                agent_trace_id: "trace_profile_91",
                created_at: "2026-07-05T09:01:00Z"
              }
            ],
            trace_id: "trace_profile_events"
          },
          status: 200,
          statusText: "OK",
          headers: {},
          config
        };
      }

      return {
        data: { data: {}, trace_id: "trace_core_default" },
        status: 200,
        statusText: "OK",
        headers: {},
        config
      };
    };
  });

  afterEach(() => {
    apiClient.defaults.adapter = previousAdapter;
  });

  it("renders the material library as a source workspace", async () => {
    renderPage(<LibraryPage />);

    expect(screen.getByRole("region", { name: "历史对话" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "资料库" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "资料工作台" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "资料文件列表" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "搜索资料" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "上传资料" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "生成课程" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "文档" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "图片" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "课程内置" })).not.toBeInTheDocument();
    expect(await screen.findByRole("button", { name: /AI 导论讲义/ })).toBeInTheDocument();
  });

  it("renders studio as a generated-resource workspace", () => {
    renderPage(<StudioPage />);

    expect(screen.getByRole("heading", { name: "资源工坊" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "资源成果工作台" })).toBeInTheDocument();
    expect(screen.getByRole("complementary", { name: "成果库" })).toBeInTheDocument();
    expect(screen.getByRole("main", { name: "成果画布" })).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "资源类型筛选" })).toBeInTheDocument();
    expect(screen.queryByText("加载状态")).not.toBeInTheDocument();
  });

  it("renders the learning profile workspace from the real profile API", async () => {
    renderPage(<ProfilePage />);

    expect(screen.getByRole("region", { name: "动态学习画像工作台" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "学习画像" })).toHaveClass("visually-hidden");
    expect(screen.getByRole("heading", { name: "动态学习画像" })).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText(/完整度/)).toHaveTextContent("完整度 100% · 证据可信度 72%");
    });
    expect(screen.getByRole("complementary", { name: "八维学习画像" })).toBeInTheDocument();
    expect(screen.getByRole("main", { name: "画像动态" })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "八维画像可信度雷达图" })).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "画像维度" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "画像问题回答" })).toBeInTheDocument();
    expect(await screen.findByText("期末前掌握神经网络")).toBeInTheDocument();
    expect(screen.getByText("建议补充 · 学习难点")).toBeInTheDocument();
    expect(screen.getByText("说说哪些内容正在影响你的理解或做题。")).toBeInTheDocument();
    expect(screen.getByText("可以说：难理解的概念、不会应用的公式、经常做错的题型。")).toBeInTheDocument();
    expect(screen.getByRole("main", { name: "画像动态" })).toHaveTextContent("更新学习画像：学习目标、基础");
    expect(screen.queryByRole("button", { name: "更新目标" })).not.toBeInTheDocument();
  });

  it("renders practice as a focused three-state workspace", async () => {
    renderPage(<PracticePage />);

    expect(screen.getByRole("heading", { name: "练习" })).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: "先到资料库创建课程" })).toHaveAttribute("href", "/app/library");
    expect(screen.getByRole("button", { name: "练习设置" })).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "练习作答" })).not.toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "批改反馈" })).not.toBeInTheDocument();
  });

  it("renders reports as an explainable learning record", async () => {
    renderPage(<ReportsPage />);

    expect(screen.getByRole("heading", { name: "学习报告" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "学习报告数据工作台" })).toBeInTheDocument();
    expect(screen.getByRole("main", { name: "学习数据仪表盘" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "实时学习指标" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "最近报告快照" })).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "生成学习报告" })).toBeInTheDocument();
    expect(screen.queryByText("引用覆盖：AI 导论内置讲义、期末复习题样例")).not.toBeInTheDocument();
  });

  it("renders settings with model, privacy, and account boundaries", () => {
    renderPage(<SettingsPage />);

    expect(screen.getByRole("heading", { name: "设置" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "模型设置" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "隐私与数据" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "账号设置" })).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "Provider 预设" })).toBeInTheDocument();
    expect(screen.getByText("讯飞星火 Spark")).toBeInTheDocument();
    expect(screen.queryByText("深度思考")).not.toBeInTheDocument();
    expect(screen.queryByText("联网搜索")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "保存设置" })).toBeInTheDocument();
  });

  it("keeps secondary routes inside the same shell with home history", async () => {
    renderRoutePage(<SettingsPage />, "/app/settings");

    const historyRail = screen.getByRole("region", { name: "历史对话" });

    expect(within(historyRail).getByRole("link", { name: "资料库" })).toHaveAttribute("href", "/app/library");
    expect(within(historyRail).getByRole("link", { name: "个人资料" })).toHaveAttribute("href", "/app/profile");
    expect(within(historyRail).getByRole("link", { name: "设置" })).toHaveAttribute("href", "/app/settings");
    expect(within(historyRail).getByRole("link", { name: "设置" })).toHaveAttribute("aria-current", "page");
    expect(within(historyRail).queryByRole("button", { name: /神经网络反向传播怎么复习/ })).not.toBeInTheDocument();
    expect(await within(historyRail).findByRole("button", { name: /主页历史会话/ })).toBeInTheDocument();
    expect(within(historyRail).queryByText("还没有历史对话")).not.toBeInTheDocument();
    expect(screen.queryByRole("navigation", { name: "应用导航" })).not.toBeInTheDocument();
  });
});

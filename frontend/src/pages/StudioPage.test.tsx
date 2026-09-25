import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { type ReactNode } from "react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { PATHS } from "../app/routePaths";
import { AGENT_ENDPOINTS } from "../api/agents";
import { AI_JOB_ENDPOINTS } from "../api/aiJobs";
import { apiClient } from "../api/client";
import { COURSE_ENDPOINTS } from "../api/courses";
import { RESOURCE_ENDPOINTS, type GeneratedResource, type ResourceQualityScore } from "../api/resources";
import { StudioPage } from "./StudioPage";
import { makeCompletedAiJob } from "../test/aiJobs";

let previousAdapter = apiClient.defaults.adapter;

function renderWithProviders(ui: ReactNode, initialPath: string = PATHS.studio) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false
      }
    }
  });

  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialPath]}>
        <LocationProbe />
        <Routes>
          <Route path={PATHS.studio} element={ui} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

function LocationProbe() {
  const location = useLocation();
  return <output data-testid="studio-location">{location.pathname}{location.search}</output>;
}

function parsePayload(data: unknown) {
  if (typeof data !== "string") {
    return data;
  }

  return JSON.parse(data);
}

function makeResource(overrides: Partial<GeneratedResource> = {}): GeneratedResource {
  return {
    id: "901",
    course_id: "808",
    knowledge_point_id: "401",
    resource_type: "doc",
    title: "启发式搜索个性化讲解",
    content_json: {
      markdown: "# 启发式搜索个性化讲解\n\n先理解启发函数，再对比 A*。",
      metadata: {
        agent_trace_id: "trace_resource",
        generation_mode: "model_enhanced"
      }
    },
    citation_json: [
      {
        chunk_id: 501,
        source_title: "人工智能导论讲义.md",
        section_title: "启发式搜索"
      }
    ],
    status: "completed",
    review_status: "passed",
    confidence_score: 0.82,
    agent_trace_id: "trace_resource",
    personalization: {
      status: "stale",
      profile_applied_version: 2,
      current_profile_applied_version: 3,
      reason: "学习画像已变化"
    },
    created_at: "2026-07-05T14:00:00Z",
    updated_at: "2026-07-05T14:00:00Z",
    ...overrides
  };
}

function makeQuality(resourceId = "901"): ResourceQualityScore[] {
  return [
    {
      id: "3001",
      resource_id: resourceId,
      score_name: "source_match",
      score_value: 0.82,
      rationale: "基于课程引用摘要生成。",
      created_at: "2026-07-05T14:00:00Z"
    },
    {
      id: "3002",
      resource_id: resourceId,
      score_name: "profile_fit",
      score_value: 0.78,
      rationale: "结合用户级画像叠层。",
      created_at: "2026-07-05T14:00:00Z"
    }
  ];
}

describe("StudioPage resource generation", () => {
  it("keeps home history while filtering courses and clears stale course return context", async () => {
    const calls: Array<{ method: string; url: string; params: unknown }> = [];
    apiClient.defaults.adapter = async (config) => {
      const url = config.url ?? "";
      calls.push({ method: config.method ?? "get", url, params: config.params });
      const data = url === COURSE_ENDPOINTS.list
        ? [{ id: "808", title: "课程甲", status: "ready" }, { id: "809", title: "课程乙", status: "ready" }]
        : url === "/tutor/sessions/history"
          ? { items: [{ id: "71", title: "主页学习对话", updated_at: "2026-09-25T08:00:00Z" }], page: 1, has_more: false }
          : [];
      return { data: { data }, status: 200, statusText: "OK", headers: {}, config };
    };
    renderWithProviders(<StudioPage />, `${PATHS.studio}?course_id=808&course_session_id=21&course_message_id=31&knowledge_point_id=401&return_to=course&return_view=graph&return_detail=knowledge`);
    expect(await screen.findByText("主页学习对话")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("combobox", { name: "资源课程" })).toHaveValue("808"));
    expect(screen.getByRole("link", { name: "返回课程空间" })).toHaveAttribute("href", "/app/courses/808?course_session_id=21&course_message_id=31&knowledge_point_id=401&mode=study&view=graph&detail=knowledge");

    await userEvent.setup().selectOptions(screen.getByRole("combobox", { name: "资源课程" }), "809");
    expect(screen.getByText("主页学习对话")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "返回课程空间" })).toHaveAttribute("href", "/app/courses/809");
    expect(screen.getByTestId("studio-location")).toHaveTextContent(`${PATHS.studio}?course_id=809`);
    await waitFor(() => expect(calls).toContainEqual(expect.objectContaining({ url: RESOURCE_ENDPOINTS.list, params: { course_id: 809 } })));
    expect(calls.filter(({ method }) => method !== "get")).toEqual([]);

    await userEvent.setup().click(screen.getByText("主页学习对话"));
    expect(screen.getByTestId("studio-location")).toHaveTextContent("/app?session_id=71");
  });

  it.each(["resource_id=999", "resource_id=901&path_task_id=61"])("does not substitute unrelated resources for %s", async (query) => {
    apiClient.defaults.adapter = async (config) => {
      const url = config.url ?? "";
      const data = url === COURSE_ENDPOINTS.list
        ? [{ id: "808", title: "课程", status: "ready" }]
        : url === RESOURCE_ENDPOINTS.list
          ? [makeResource()]
          : url === "/paths/tasks/61"
            ? { id: "61", course_id: "808", path_id: "71", learning_bundle: { items: [{ resource_id: "999", resource_type: "doc" }] } }
            : [];
      return { data: { data }, status: 200, statusText: "OK", headers: {}, config };
    };
    renderWithProviders(<StudioPage />, `${PATHS.studio}?course_id=808&${query}`);
    expect(await screen.findByRole("heading", { name: "资源暂时没有读取成功" })).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "资源完整内容" })).not.toBeInTheDocument();
  });
  beforeEach(() => {
    previousAdapter = apiClient.defaults.adapter;
  });

  it("leaves task context when the user explicitly selects a different library resource", async () => {
    apiClient.defaults.adapter = async (config) => {
      const url = config.url ?? "";
      const data = url === COURSE_ENDPOINTS.list
        ? [{ id: "808", title: "课程", status: "ready" }]
        : url === RESOURCE_ENDPOINTS.list
          ? [makeResource()]
          : url === "/paths/tasks/61"
            ? { id: "61", course_id: "808", path_id: "71", learning_bundle: { items: [{ resource_id: "999", resource_type: "doc" }] } }
            : [];
      return { data: { data }, status: 200, statusText: "OK", headers: {}, config };
    };
    renderWithProviders(<StudioPage />, `${PATHS.studio}?course_id=808&resource_id=999&path_task_id=61`);
    const open = await screen.findByRole("button", { name: /^打开成果 / });
    await userEvent.setup().click(open);
    await waitFor(() => expect(screen.getByTestId("studio-location")).not.toHaveTextContent("path_task_id"));
    expect(screen.getByTestId("studio-location")).toHaveTextContent("resource_id=901");
    expect(await screen.findByRole("region", { name: "资源完整内容" })).toBeInTheDocument();
  });

  afterEach(() => {
    apiClient.defaults.adapter = previousAdapter;
  });

  it("uses real resource APIs to generate and refresh course resources", async () => {
    const user = userEvent.setup();
    const calls: Array<{ method: string; url: string; payload: unknown; params: unknown }> = [];
    let resources: GeneratedResource[] = [];

    apiClient.defaults.adapter = async (config) => {
      const method = (config.method ?? "get").toLowerCase();
      const url = config.url ?? "";
      const payload = parsePayload(config.data);
      calls.push({ method, url, payload, params: config.params });

      if (url === COURSE_ENDPOINTS.list) {
        return {
          data: {
            data: [
              {
                id: "808",
                title: "AI 搜索复习",
                description: "由 1 份资料生成",
                subject: "人工智能",
                source_type: "uploaded",
                status: "ready",
                progress_percent: 0,
                material_count: 1,
                knowledge_point_count: 1,
                chunk_count: 3
              }
            ],
            page: 1,
            page_size: 1,
            total: 1,
            trace_id: "trace_courses"
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
            trace_id: "trace_points"
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
            trace_id: "trace_resources"
          },
          status: 200,
          statusText: "OK",
          headers: {},
          config
        };
      }

      if (url === RESOURCE_ENDPOINTS.generationJobs && method === "post") {
        resources = [makeResource()];
        return {
          data: {
            data: makeCompletedAiJob({ result: { course_id: "808", resource_ids: ["901"] } }),
            trace_id: "trace_generate"
          },
          status: 200,
          statusText: "OK",
          headers: {},
          config
        };
      }

      if (url === RESOURCE_ENDPOINTS.quality(901)) {
        return {
          data: { data: makeQuality(), trace_id: "trace_quality" },
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

    renderWithProviders(<StudioPage />, `${PATHS.studio}?course_id=808`);

    expect(await screen.findByRole("heading", { name: "资源工坊" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "资源成果工作台" })).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByRole("main", { name: "成果画布" })).toHaveTextContent("这门课还没有学习资源");
    });
    await user.click(within(screen.getByRole("banner", { name: "资源工坊工具栏" })).getByRole("button", { name: "新建资源" }));
    const generateDrawer = screen.getByRole("dialog", { name: "生成设置" });
    await user.type(within(generateDrawer).getByRole("textbox", { name: "生成目标" }), "期末前掌握搜索题");
    for (const type of ["思维导图", "练习题", "代码实操", "PPT", "动画图解"]) {
      await user.click(within(generateDrawer).getByRole("checkbox", { name: type }));
    }
    await user.click(within(generateDrawer).getByRole("button", { name: "开始生成" }));

    await waitFor(() => {
      expect(calls).toContainEqual(
        expect.objectContaining({
          method: "post",
          url: RESOURCE_ENDPOINTS.generationJobs,
          payload: {
            course_id: 808,
            knowledge_point_id: 401,
            resource_types: ["doc", "mindmap", "quiz", "code", "slide", "animation"],
            learning_goal: "期末前掌握搜索题",
            difficulty: "medium",
            generation_action: "new",
            source_resource_id: null
          }
        })
      );
    });
    expect(await screen.findByRole("button", { name: "打开成果 启发式搜索个性化讲解" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("region", { name: "资源完整内容" })).toHaveTextContent("先理解启发函数");
    await waitFor(() => {
      expect(screen.getByTestId("studio-location")).toHaveTextContent("course_id=808&resource_id=901");
    });
    expect(screen.queryByRole("dialog", { name: "生成设置" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "成果详情" }));
    expect(await screen.findByRole("tabpanel", { name: "资源质量" })).toHaveTextContent("来源匹配");
    await user.click(screen.getByRole("tab", { name: "来源" }));
    expect(screen.getByRole("tabpanel", { name: "引用来源" })).toHaveTextContent("人工智能导论讲义.md");
    expect(calls.filter((call) => call.url === RESOURCE_ENDPOINTS.list).length).toBeGreaterThanOrEqual(2);
  }, 20_000);

  it("shows a real empty state when there are no generated resources", async () => {
    apiClient.defaults.adapter = async (config) => {
      if (config.url === COURSE_ENDPOINTS.list) {
        return {
          data: { data: [], page: 1, page_size: 0, total: 0, trace_id: "trace_courses_empty" },
          status: 200,
          statusText: "OK",
          headers: {},
          config
        };
      }

      if (config.url === RESOURCE_ENDPOINTS.list) {
        return {
          data: { data: [], page: 1, page_size: 0, total: 0, trace_id: "trace_resources_empty" },
          status: 200,
          statusText: "OK",
          headers: {},
          config
        };
      }

      return {
        data: { data: [], trace_id: "trace_default" },
        status: 200,
        statusText: "OK",
        headers: {},
        config
      };
    };

    renderWithProviders(<StudioPage />);

    await waitFor(() => {
      expect(screen.getByRole("main", { name: "成果画布" })).toHaveTextContent("先准备一门课程");
    });
    expect(screen.getByRole("link", { name: "进入资料库" })).toHaveAttribute("href", PATHS.library);
    expect(screen.getByRole("complementary", { name: "成果库" })).toHaveTextContent("选择课程后查看成果");
    expect(screen.queryByText("监督学习个性化讲解")).not.toBeInTheDocument();
  });

  it("switches, compares and regenerates durable resource versions", async () => {
    const user = userEvent.setup();
    const calls: Array<{ url: string; method: string; payload: unknown }> = [];
    const v1 = makeResource({
      id: "901",
      version_family_id: "family-a-star",
      version_number: 1,
      generation_action: "new",
      intent_summary: {
        resource_type: "doc",
        learning_goal: "理解 A* 搜索",
        teaching_strategy: "evidence_to_concept",
        cognitive_level: "understand",
        example_direction: "课程真实情境",
        interaction_structure: "概念-证据-推导-自检"
      },
      personalization_summary: {
        status: "personalized",
        learning_problem: "理解启发函数",
        teaching_reason: "从课程证据建立概念",
        difference: "初始版本"
      }
    });
    const v2 = makeResource({
      id: "902",
      version_family_id: "family-a-star",
      revision_of_resource_id: "901",
      version_number: 2,
      generation_action: "alternative",
      created_at: "2026-07-06T14:00:00Z",
      updated_at: "2026-07-06T14:00:00Z",
      content_json: {
        markdown: "# A* 情境讲解\n\n从路线规划案例理解启发函数。",
        metadata: { generation_mode: "model_enhanced", difficulty: "medium" }
      },
      intent_summary: {
        resource_type: "doc",
        learning_goal: "理解 A* 搜索",
        teaching_strategy: "worked_example_first",
        cognitive_level: "apply",
        example_direction: "跨场景迁移应用",
        interaction_structure: "问题-示例-反例-复盘"
      },
      personalization_summary: {
        status: "personalized",
        learning_problem: "把评价函数用于新问题",
        teaching_reason: "先用完整案例建立直觉",
        difference: "相对上一版更换了案例和认知层级"
      }
    });

    apiClient.defaults.adapter = async (config) => {
      const url = config.url ?? "";
      const method = (config.method ?? "get").toLowerCase();
      calls.push({ url, method, payload: parsePayload(config.data) });
      if (url === COURSE_ENDPOINTS.list) {
        return { data: { data: [{ id: "808", title: "AI 搜索", status: "ready" }] }, status: 200, statusText: "OK", headers: {}, config };
      }
      if (url === COURSE_ENDPOINTS.knowledgePoints(808)) {
        return { data: { data: [{ id: "401", title: "启发式搜索", order_index: 1 }] }, status: 200, statusText: "OK", headers: {}, config };
      }
      if (url === RESOURCE_ENDPOINTS.list) {
        return { data: { data: [v2, v1], page: 1, page_size: 2, total: 2 }, status: 200, statusText: "OK", headers: {}, config };
      }
      if (url === RESOURCE_ENDPOINTS.generationJobs && method === "post") {
        return {
          data: { data: makeCompletedAiJob({ result: { course_id: "808", resource_ids: [] } }) },
          status: 200,
          statusText: "OK",
          headers: {},
          config
        };
      }
      return { data: { data: [] }, status: 200, statusText: "OK", headers: {}, config };
    };

    renderWithProviders(<StudioPage />, `${PATHS.studio}?course_id=808&resource_id=902`);

    expect(await screen.findByRole("combobox", { name: "资源版本" })).toHaveValue("902");
    expect(screen.getByRole("complementary", { name: "成果库" })).toHaveTextContent("2 个版本");
    expect(screen.getByLabelText("个性化生成依据")).toHaveTextContent("先用完整案例建立直觉");
    await user.selectOptions(screen.getByRole("combobox", { name: "资源版本" }), "901");
    await waitFor(() => expect(screen.getByTestId("studio-location")).toHaveTextContent("resource_id=901"));
    await user.click(screen.getByRole("button", { name: "比较" }));
    expect(screen.getByRole("dialog", { name: "比较资源版本" })).toHaveTextContent("从证据建立概念");
    await user.click(screen.getByRole("button", { name: "关闭版本比较" }));
    await user.click(within(screen.getByRole("banner", { name: "资源工坊工具栏" })).getByRole("button", { name: "重新生成" }));
    const dialog = screen.getByRole("dialog", { name: "重新生成资源" });
    await user.click(within(dialog).getByRole("button", { name: /换一种教法/ }));

    await waitFor(() => {
      expect(calls).toContainEqual(expect.objectContaining({
        url: RESOURCE_ENDPOINTS.generationJobs,
        method: "post",
        payload: expect.objectContaining({
          generation_action: "alternative",
          source_resource_id: 901,
          resource_types: ["doc"],
          learning_goal: "理解 A* 搜索"
        })
      }));
    });
  });

  it("opens generated resources and shows the selected full content with quality scores", async () => {
    const user = userEvent.setup();
    const resources: GeneratedResource[] = [
      makeResource({
        id: "901",
        agent_trace_id: "trace_doc",
        resource_type: "doc",
        title: "启发式搜索个性化讲解",
        content_json: {
          markdown: "# 启发式搜索个性化讲解\n\n第一段讲解。\n\n第二段复习建议。",
          metadata: { agent_trace_id: "trace_doc", generation_mode: "deterministic_source" }
        }
      }),
      makeResource({
        id: "902",
        agent_trace_id: "trace_quiz",
        resource_type: "quiz",
        title: "启发式搜索练习题",
        content_json: {
          markdown: "# 启发式搜索练习题\n\n## 单选题\n答案：B。",
          metadata: { agent_trace_id: "trace_quiz", generation_mode: "low_evidence_fallback" }
        },
        review_status: "low_evidence"
      })
    ];

    apiClient.defaults.adapter = async (config) => {
      if (config.url === COURSE_ENDPOINTS.list) {
        return {
          data: {
            data: [
              {
                id: "808",
                title: "AI 搜索复习",
                description: "由 1 份资料生成",
                subject: "人工智能",
                source_type: "uploaded",
                status: "ready",
                progress_percent: 0,
                material_count: 1,
                knowledge_point_count: 1,
                chunk_count: 3
              }
            ],
            page: 1,
            page_size: 1,
            total: 1,
            trace_id: "trace_courses"
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
                summary: "理解启发函数和 A*。",
                chapter: "搜索问题",
                order_index: 1,
                difficulty: "基础"
              }
            ],
            trace_id: "trace_points"
          },
          status: 200,
          statusText: "OK",
          headers: {},
          config
        };
      }

      if (config.url === RESOURCE_ENDPOINTS.list) {
        return {
          data: {
            data: resources,
            page: 1,
            page_size: resources.length,
            total: resources.length,
            trace_id: "trace_resources"
          },
          status: 200,
          statusText: "OK",
          headers: {},
          config
        };
      }

      if (config.url === RESOURCE_ENDPOINTS.quality(901)) {
        return {
          data: { data: makeQuality("901"), trace_id: "trace_quality_doc" },
          status: 200,
          statusText: "OK",
          headers: {},
          config
        };
      }

      if (config.url === RESOURCE_ENDPOINTS.quality(902)) {
        return {
          data: {
            data: [
              {
                id: "3003",
                resource_id: "902",
                score_name: "source_match",
                score_value: 0.66,
                rationale: "练习题基于课程引用摘要。",
                created_at: "2026-07-05T14:00:00Z"
              }
            ],
            trace_id: "trace_quality_quiz"
          },
          status: 200,
          statusText: "OK",
          headers: {},
          config
        };
      }

      if (config.url === AGENT_ENDPOINTS.trace("trace_doc")) {
        return {
          data: {
            data: {
              trace_id: "trace_doc",
              workflow: "resource_generation",
              artifact_type: "generated_resource",
              artifact_id: "901",
              course_id: "808",
              status: "completed",
              steps: [
                {
                  id: "trace-step-review",
                  agent_name: "review",
                  step_index: 7,
                  status: "completed",
                  input_summary: "审核资源",
                  output_summary: "资源审核通过",
                  duration_ms: 18,
                  metadata: {},
                  created_at: "2026-07-05T14:00:00Z"
                }
              ]
            },
            trace_id: "trace_doc"
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

    renderWithProviders(<StudioPage />, `${PATHS.studio}?course_id=808&resource_id=902`);

    expect(await screen.findByRole("button", { name: "打开成果 启发式搜索练习题" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByText("学习画像已变化，可重新生成以应用新的个性化依据。")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "资源完整内容" })).toHaveTextContent("资料依据不足");
    expect(screen.getByRole("region", { name: "资源完整内容" })).toHaveTextContent("答案：B。");

    await user.type(screen.getByRole("textbox", { name: "搜索成果" }), "个性化讲解");
    expect(screen.queryByRole("button", { name: "打开成果 启发式搜索练习题" })).not.toBeInTheDocument();
    await user.clear(screen.getByRole("textbox", { name: "搜索成果" }));
    await user.selectOptions(screen.getByRole("combobox", { name: "资源类型筛选" }), "quiz");
    expect(screen.queryByRole("button", { name: "打开成果 启发式搜索个性化讲解" })).not.toBeInTheDocument();
    await user.selectOptions(screen.getByRole("combobox", { name: "资源类型筛选" }), "all");
    await user.click(screen.getByRole("button", { name: "打开成果 启发式搜索个性化讲解" }));

    expect(screen.getByRole("region", { name: "资源完整内容" })).toHaveTextContent("第二段复习建议。");
    expect(screen.getByTestId("studio-location")).toHaveTextContent("resource_id=901");
    await user.click(screen.getByRole("button", { name: "成果详情" }));
    expect(screen.getByTestId("studio-drawer-layer").closest(".page-workbench")).toBeNull();
    expect(await screen.findByRole("tabpanel", { name: "资源质量" })).toHaveTextContent("基于课程引用摘要生成。");
    await user.click(screen.getByRole("tab", { name: "来源" }));
    expect(screen.getByRole("tabpanel", { name: "引用来源" })).toHaveTextContent("人工智能导论讲义.md");
    await user.click(screen.getByRole("tab", { name: "协作轨迹" }));
    expect(await screen.findByText("资源审核通过")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "关闭成果详情" }));
    expect(screen.queryByRole("dialog", { name: "成果详情" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "成果详情" }));
    fireEvent.mouseDown(screen.getByTestId("studio-drawer-layer"));
    expect(screen.queryByRole("dialog", { name: "成果详情" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "成果详情" }));
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog", { name: "成果详情" })).not.toBeInTheDocument();
    expect(screen.getByRole("main", { name: "成果画布" })).toBeInTheDocument();
  });

  it("keeps a failed generation drawer closable and deletes the durable task", async () => {
    const user = userEvent.setup();
    const calls: Array<{ method: string; url: string }> = [];

    apiClient.defaults.adapter = async (config) => {
      const method = (config.method ?? "get").toLowerCase();
      const url = config.url ?? "";
      calls.push({ method, url });
      if (config.url === COURSE_ENDPOINTS.list) {
        return {
          data: {
            data: [
              {
                id: "808",
                title: "AI 搜索复习",
                description: "由 1 份资料生成",
                subject: "人工智能",
                source_type: "uploaded",
                status: "ready",
                progress_percent: 0,
                material_count: 1,
                knowledge_point_count: 1,
                chunk_count: 3
              }
            ],
            page: 1,
            page_size: 1,
            total: 1,
            trace_id: "trace_courses"
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
                summary: "理解启发函数和 A*。",
                chapter: "搜索问题",
                order_index: 1,
                difficulty: "基础"
              }
            ],
            trace_id: "trace_points"
          },
          status: 200,
          statusText: "OK",
          headers: {},
          config
        };
      }

      if (config.url === RESOURCE_ENDPOINTS.list) {
        return {
          data: { data: [], page: 1, page_size: 0, total: 0, trace_id: "trace_resources" },
          status: 200,
          statusText: "OK",
          headers: {},
          config
        };
      }

      if (url === RESOURCE_ENDPOINTS.generationJobs) {
        return {
          data: {
            data: makeCompletedAiJob({
              job_id: "77",
              status: "failed",
              label: "任务执行失败",
              error_code: "VALIDATION_ERROR",
              error_message: "所有资源均未通过安全审核。",
              can_retry: true
            }),
            trace_id: "trace_failed_job"
          },
          status: 202,
          statusText: "Accepted",
          headers: {},
          config
        };
      }

      if (url === AI_JOB_ENDPOINTS.delete("77") && method === "delete") {
        return { data: undefined, status: 204, statusText: "No Content", headers: {}, config };
      }

      return {
        data: { data: {}, trace_id: "trace_default" },
        status: 200,
        statusText: "OK",
        headers: {},
        config
      };
    };

    renderWithProviders(<StudioPage />, `${PATHS.studio}?course_id=808`);

    await screen.findByRole("heading", { name: "资源工坊" });
    await waitFor(() => {
      expect(screen.getByRole("main", { name: "成果画布" })).toHaveTextContent("这门课还没有学习资源");
    });
    await user.click(within(screen.getByRole("banner", { name: "资源工坊工具栏" })).getByRole("button", { name: "新建资源" }));
    const generateDrawer = screen.getByRole("dialog", { name: "生成设置" });
    await user.type(within(generateDrawer).getByRole("textbox", { name: "生成目标" }), "保留我的生成目标");
    await user.click(within(generateDrawer).getByRole("button", { name: "开始生成" }));

    expect((await within(generateDrawer).findAllByText("所有资源均未通过安全审核。")).length).toBeGreaterThan(0);
    expect(within(generateDrawer).getByRole("textbox", { name: "生成目标" })).toHaveValue("保留我的生成目标");
    expect(screen.getByRole("main", { name: "成果画布", hidden: true })).toHaveTextContent("这门课还没有学习资源");

    await user.click(within(generateDrawer).getByRole("button", { name: "关闭生成设置" }));
    expect(screen.queryByRole("dialog", { name: "生成设置" })).not.toBeInTheDocument();
    expect(await screen.findByRole("alert")).toHaveTextContent("所有资源均未通过安全审核。");

    await user.click(within(screen.getByRole("banner", { name: "资源工坊工具栏" })).getByRole("button", { name: "新建资源" }));
    const reopenedDrawer = screen.getByRole("dialog", { name: "生成设置" });
    await user.click(within(reopenedDrawer).getByRole("button", { name: "删除任务" }));

    await waitFor(() => {
      expect(calls).toContainEqual({ method: "delete", url: AI_JOB_ENDPOINTS.delete("77") });
    });
    expect(screen.queryByRole("dialog", { name: "生成设置" })).not.toBeInTheDocument();
    expect(await screen.findByText("失败任务已删除。你可以调整设置后重新生成。")).toBeInTheDocument();
  });

  it("opens path resources in bundle order and advances only after resource completion", async () => {
    const user = userEvent.setup();
    let docCompleted = false;
    const resources = [
      makeResource({ id: "901", title: "第一项讲解", created_at: "2026-07-05T14:00:00Z" }),
      makeResource({ id: "902", resource_type: "quiz", title: "第二项练习", created_at: "2026-07-06T14:00:00Z" })
    ];

    apiClient.defaults.adapter = async (config) => {
      const url = config.url ?? "";
      const method = (config.method ?? "get").toLowerCase();
      if (url === COURSE_ENDPOINTS.list) {
        return { data: { data: [{ id: "808", title: "AI 搜索复习", description: "", subject: "人工智能", source_type: "uploaded", status: "ready", progress_percent: 0, material_count: 1, knowledge_point_count: 1, chunk_count: 3 }], page: 1, page_size: 1, total: 1 }, status: 200, statusText: "OK", headers: {}, config };
      }
      if (url === COURSE_ENDPOINTS.knowledgePoints(808)) {
        return { data: { data: [{ id: "401", title: "启发式搜索", summary: "", chapter: "搜索问题", order_index: 1, difficulty: "基础" }] }, status: 200, statusText: "OK", headers: {}, config };
      }
      if (url === RESOURCE_ENDPOINTS.list) {
        return { data: { data: resources, page: 1, page_size: 2, total: 2 }, status: 200, statusText: "OK", headers: {}, config };
      }
      if (url === "/paths/tasks/61") {
        return {
          data: { data: {
              id: "61", path_id: "71", course_id: "808", knowledge_point_id: "401", title: "本节任务", task_type: "learn", reason: "按顺序学习",
              recommended_resource_ids: ["901", "902"], recommended_resources: [], status: "doing", created_at: "2026-07-05T09:00:00Z", updated_at: "2026-07-05T09:00:00Z",
              learning_bundle: {
                strategy: "先讲后练", teaching_strategy: "worked_example", difficulty: "medium", used_profile_factor_codes: [], generation_mode: "model_enhanced", rationale: "按序完成",
                ready_count: 2, completed_count: docCompleted ? 1 : 0,
                items: [
                  { resource_type: "doc", role: "讲解", resource_id: "901", status: "ready", learning_status: docCompleted ? "completed" : "not_started" },
                  { resource_type: "quiz", role: "练习", resource_id: "902", status: "ready", learning_status: "not_started" }
                ]
              }
          } },
          status: 200, statusText: "OK", headers: {}, config
        };
      }
      if (url === RESOURCE_ENDPOINTS.learningState(901)) {
        return { data: { data: { resource_id: "901", opened: true, started: true, completed: docCompleted, progress_percent: docCompleted ? 100 : null, feedback: null, updated_at: null } }, status: 200, statusText: "OK", headers: {}, config };
      }
      if (url === RESOURCE_ENDPOINTS.learningState(902)) {
        return { data: { data: { resource_id: "902", opened: false, started: false, completed: false, progress_percent: null, feedback: null, updated_at: null } }, status: 200, statusText: "OK", headers: {}, config };
      }
      if (url === RESOURCE_ENDPOINTS.interactions(901) && method === "post") {
        const payload = parsePayload(config.data) as { event_type?: string };
        if (payload.event_type === "opened") {
          // Auto-recording an open may still be in flight; it must not lock explicit learning actions.
          return new Promise(() => undefined);
        }
        if (payload.event_type === "completed") docCompleted = true;
        return { data: { data: { resource_id: "901", opened: true, started: true, completed: docCompleted, progress_percent: docCompleted ? 100 : null, feedback: null, updated_at: null } }, status: 200, statusText: "OK", headers: {}, config };
      }
      if (url === RESOURCE_ENDPOINTS.interactions(902) && method === "post") {
        return { data: { data: { resource_id: "902", opened: true, started: false, completed: false, progress_percent: null, feedback: null, updated_at: null } }, status: 200, statusText: "OK", headers: {}, config };
      }
      return { data: { data: {} }, status: 200, statusText: "OK", headers: {}, config };
    };

    renderWithProviders(<StudioPage />, `${PATHS.studio}?course_id=808&path_task_id=61`);

    expect(await screen.findByRole("heading", { name: "第一项讲解" })).toBeInTheDocument();
    expect(screen.getByText("本节已完成 0/2 个可学习资源")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "学习下一项" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "完成学习" }));
    await user.click(await screen.findByRole("button", { name: "学习下一项" }));

    expect(await screen.findByRole("heading", { name: "第二项练习" })).toBeInTheDocument();
    expect(screen.getByTestId("studio-location")).toHaveTextContent("resource_id=902");
    expect(screen.queryByRole("button", { name: "完成这项学习" })).not.toBeInTheDocument();
  });
});

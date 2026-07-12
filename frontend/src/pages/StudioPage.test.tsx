import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { type ReactNode } from "react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { PATHS } from "../app/routePaths";
import { AGENT_ENDPOINTS } from "../api/agents";
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
  beforeEach(() => {
    previousAdapter = apiClient.defaults.adapter;
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
    for (const type of ["思维导图", "练习", "代码实操", "PPT", "动画图解"]) {
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
            difficulty: "medium"
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

  it("shows local feedback when resource generation fails", async () => {
    const user = userEvent.setup();

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
          data: { data: [], page: 1, page_size: 0, total: 0, trace_id: "trace_resources" },
          status: 200,
          statusText: "OK",
          headers: {},
          config
        };
      }

      if (config.url === RESOURCE_ENDPOINTS.generationJobs) {
        throw new Error("generate failed");
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

    expect(await within(generateDrawer).findByRole("alert")).toHaveTextContent("资源生成失败，请稍后重试。");
    expect(within(generateDrawer).getByRole("textbox", { name: "生成目标" })).toHaveValue("保留我的生成目标");
    expect(screen.getByRole("main", { name: "成果画布" })).toHaveTextContent("这门课还没有学习资源");
  });
});

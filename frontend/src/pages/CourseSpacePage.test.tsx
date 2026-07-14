import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { type ReactNode } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { PATHS } from "../app/routePaths";
import { AGENT_ENDPOINTS, type AgentTrace } from "../api/agents";
import { apiClient } from "../api/client";
import { COURSE_ENDPOINTS } from "../api/courses";
import { PATH_ENDPOINTS } from "../api/paths";
import { PRACTICE_ENDPOINTS } from "../api/practice";
import { REPORT_ENDPOINTS } from "../api/reports";
import { RESOURCE_ENDPOINTS } from "../api/resources";
import { TUTOR_ENDPOINTS, type TutorCitation, type TutorSessionDetail, type TutorSessionSummary } from "../api/tutor";
import { CourseSpacePage } from "./CourseSpacePage";
import { makeCompletedAiJob } from "../test/aiJobs";

let previousAdapter = apiClient.defaults.adapter;
const previousFetch = globalThis.fetch;

type ApiCall = {
  method: string;
  url: string;
  payload: unknown;
  params: unknown;
};

type CoursePageOptions = {
  initialEntry?: string;
  sessions?: TutorSessionSummary[];
  sendDetail?: TutorSessionDetail;
  historyDetail?: TutorSessionDetail;
  learningState?: unknown;
  refreshedLearningState?: unknown;
  masteryPoints?: unknown[];
  refreshedMasteryPoints?: unknown[];
  agentTrace?: AgentTrace;
  failLearningState?: boolean;
  failAgentTrace?: boolean;
  failWeaknessAction?: boolean;
  failResourceGeneration?: boolean;
  failSend?: boolean;
  streamEvents?: Array<{ event: string; data: unknown }>;
  controlledStream?: boolean;
  delayCourseDetail?: boolean;
  delayCourseData?: boolean;
  resources?: unknown[];
  refreshedResources?: unknown[];
  currentPath?: unknown;
  refreshedCurrentPath?: unknown;
  latestReport?: unknown;
  refreshedLatestReport?: unknown;
  failLearningStateRefreshOnce?: boolean;
  historyDetails?: Record<string, TutorSessionDetail>;
};

type FetchCall = {
  url: string;
  method: string;
  payload: unknown;
};

const citationItem: TutorCitation = {
  chunk_id: 501,
  course_id: 808,
  material_id: 301,
  knowledge_point_id: 401,
  content: "启发式搜索利用启发函数估计路径代价，A* 会结合实际代价和预估代价。",
  source_title: "人工智能导论讲义.md",
  page_number: null,
  section_title: "启发式搜索",
  score: 9.5,
  keyword_score: 3.5,
  vector_score: 6,
  retrieval_source: "hybrid",
  embedding_status: "local_fallback"
};

const emptyLearningState = {
  course_id: "808",
  profile_overlay: {
    learning_goal: "",
    knowledge_foundation: "",
    weak_points: []
  },
  learner_context: {
    profile_applied_version: 3,
    context_hash: "ctx-course-808",
    completeness_score: 50,
    evidence_confidence_score: 74,
    trusted_dimensions: ["learning_goal", "learning_preference"],
    advisory_dimensions: ["learning_pace"],
    course_goal: "掌握启发式搜索",
    foundation_summary: "机器学习入门；当前课程掌握度约 35%",
    active_weaknesses: [],
    mastery_average: 35,
    current_task_title: null,
    recent_practice_score: null,
    learning_preference: "图解和代码",
    cognitive_style: "",
    learning_pace: "每天 45 分钟",
    motivation_interest: ""
  },
  weakness_summary: {
    candidate_event_count: 0,
    pending_count: 0,
    confirmed_count: 0,
    reviewing_count: 0,
    completed_count: 0,
    dismissed_count: 0,
    latest_evidence_at: null
  },
  weakness_review_queue: [],
  path_summary: {
    status: "not_started",
    message: "学习路径尚未生成。",
    path_id: null,
    current_task_title: null,
    task_count: 0,
    completed_task_count: 0
  },
  mastery_summary: {
    total_count: 0,
    weak_count: 0,
    learning_count: 0,
    mastered_count: 0,
    recommended_review_count: 0,
    not_started_count: 0
  },
  evidence_summary: {
    candidate_event_count: 0,
    latest_trace_id: null,
    latest_source_title: null,
    latest_section_title: null
  }
};

const learningStateWithWeakness = {
  ...emptyLearningState,
  weakness_summary: {
    candidate_event_count: 2,
    pending_count: 1,
    confirmed_count: 0,
    reviewing_count: 0,
    completed_count: 0,
    dismissed_count: 0,
    latest_evidence_at: "2026-07-05T08:30:00Z"
  },
  weakness_review_queue: [
    {
      id: "701",
      title: "启发式搜索",
      status: "pending",
      source_type: "course_question",
      course_id: "808",
      knowledge_point_id: "401",
      recommended_resource_ids: [],
      recommended_resources: [],
      next_review_at: null,
      created_at: "2026-07-05T08:30:00Z",
      updated_at: "2026-07-05T08:30:00Z"
    }
  ],
  evidence_summary: {
    candidate_event_count: 2,
    latest_trace_id: "trace_candidate",
    latest_source_title: "人工智能导论讲义.md",
    latest_section_title: "启发式搜索"
  }
};

const agentTraceWithSteps: AgentTrace = {
  trace_id: "trace_candidate",
  workflow: "course_tutor",
  artifact_type: "chat_message",
  artifact_id: "2",
  course_id: "808",
  status: "completed",
  steps: [
    {
      id: "10",
      agent_name: "retrieve",
      step_index: 1,
      status: "completed",
      input_summary: "检索课程知识点",
      output_summary: "命中 2 条引用",
      duration_ms: 25,
      metadata: {
        citation_count: 2,
        context_message_count: 4,
        context_summary_used: true,
        retrieval_query_mode: "contextual",
        review_result: "pass"
      },
      created_at: "2026-07-05T10:00:01Z"
    },
    {
      id: "11",
      agent_name: "diagnosis",
      step_index: 2,
      status: "completed",
      input_summary: "结合画像和引用判断薄弱点",
      output_summary: "形成待确认证据",
      duration_ms: 18,
      metadata: {},
      created_at: "2026-07-05T10:00:02Z"
    }
  ]
};

const learningStateWithReviewFlow = {
  ...emptyLearningState,
  weakness_summary: {
    candidate_event_count: 5,
    pending_count: 1,
    confirmed_count: 1,
    reviewing_count: 1,
    completed_count: 1,
    dismissed_count: 1,
    latest_evidence_at: "2026-07-05T08:30:00Z"
  },
  weakness_review_queue: [
    {
      id: "701",
      title: "启发式搜索",
      status: "pending",
      source_type: "course_question",
      course_id: "808",
      knowledge_point_id: "401",
      recommended_resource_ids: [],
      recommended_resources: [],
      next_review_at: null,
      created_at: "2026-07-05T08:30:00Z",
      updated_at: "2026-07-05T08:30:00Z"
    },
    {
      id: "702",
      title: "反向传播",
      status: "confirmed",
      source_type: "course_question",
      course_id: "808",
      knowledge_point_id: "402",
      recommended_resource_ids: ["801"],
      recommended_resources: [
        {
          id: "801",
          title: "反向传播讲解",
          resource_type: "doc"
        }
      ],
      next_review_at: null,
      created_at: "2026-07-05T08:31:00Z",
      updated_at: "2026-07-05T08:31:00Z"
    },
    {
      id: "703",
      title: "A* 搜索",
      status: "reviewing",
      source_type: "course_question",
      course_id: "808",
      knowledge_point_id: "403",
      recommended_resource_ids: [],
      recommended_resources: [],
      next_review_at: null,
      created_at: "2026-07-05T08:32:00Z",
      updated_at: "2026-07-05T08:32:00Z"
    },
    {
      id: "704",
      title: "搜索复杂度",
      status: "completed",
      source_type: "course_question",
      course_id: "808",
      knowledge_point_id: "404",
      recommended_resource_ids: [],
      recommended_resources: [],
      next_review_at: null,
      created_at: "2026-07-05T08:33:00Z",
      updated_at: "2026-07-05T08:33:00Z"
    },
    {
      id: "705",
      title: "已忽略弱点",
      status: "dismissed",
      source_type: "course_question",
      course_id: "808",
      knowledge_point_id: "405",
      recommended_resource_ids: [],
      recommended_resources: [],
      next_review_at: null,
      created_at: "2026-07-05T08:34:00Z",
      updated_at: "2026-07-05T08:34:00Z"
    }
  ]
};

const learningStateWithPath = {
  ...learningStateWithWeakness,
  path_summary: {
    status: "active",
    message: "当前学习路径进行中。",
    path_id: "901",
    current_task_title: "复习启发式搜索",
    task_count: 3,
    completed_task_count: 1
  },
  mastery_summary: {
    total_count: 4,
    weak_count: 1,
    learning_count: 1,
    mastered_count: 1,
    recommended_review_count: 1,
    not_started_count: 0
  },
  weakness_review_queue: [
    {
      id: "701",
      title: "启发式搜索",
      status: "confirmed",
      source_type: "course_question",
      course_id: "808",
      knowledge_point_id: "401",
      recommended_resource_ids: ["801"],
      recommended_resources: [
        {
          id: "801",
          title: "启发式搜索讲解",
          resource_type: "doc"
        }
      ],
      next_review_at: "2026-07-12T08:30:00Z",
      created_at: "2026-07-05T08:30:00Z",
      updated_at: "2026-07-05T08:30:00Z"
    }
  ]
};

const generatedResourceItems = [
  {
    id: "801",
    course_id: "808",
    knowledge_point_id: "401",
    resource_type: "doc",
    title: "启发式搜索讲解",
    content_json: {
      markdown: "## 启发式搜索讲解",
      metadata: {
        agent_trace_id: "trace_resource"
      }
    },
    citation_json: [],
    status: "ready",
    review_status: "passed",
    confidence_score: 0.88,
    agent_trace_id: "trace_resource",
    created_at: "2026-07-05T08:40:00Z",
    updated_at: "2026-07-05T08:40:00Z"
  }
];

const activePathDetail = {
  course_id: "808",
  status: "active",
  message: "当前学习路径进行中。",
  agent_trace_id: "trace_path",
  path: {
    id: "901",
    course_id: "808",
    title: "启发式搜索复习路径",
    goal: "补强启发式搜索",
    status: "active",
    agent_trace_id: "trace_path",
    plan_json: {},
    created_at: "2026-07-05T08:40:00Z",
    updated_at: "2026-07-05T08:40:00Z"
  },
  tasks: [],
  evidence_summary: {
    knowledge_point_count: 1,
    confirmed_or_reviewing_weakness_count: 1,
    pending_weakness_count: 1,
    resource_count: 1,
    basis: ["启发式搜索"]
  }
};

const emptyReport = {
  id: null,
  course_id: "808",
  practice_session_id: null,
  status: "empty",
  agent_trace_id: null,
  score: null,
  report: {
    summary: "还没有真实学习报告。",
    mastery_update: {
      weak_count: 0,
      mastered_count: 0,
      learning_count: 0
    },
    weakness_list: [],
    evidence_refs: [],
    next_step_suggestions: [],
    review_queue_updates: [],
    profile_changes: []
  },
  created_at: null
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

function makeSession(id: string, title: string): TutorSessionSummary {
  return {
    id,
    scope: "course",
    course_id: "808",
    title,
    mode: "chat",
    archived_from_home: false,
    selected_material_ids: [],
    created_at: "2026-07-03T12:00:00Z",
    updated_at: "2026-07-03T12:01:00Z"
  };
}

function makeDetail(
  session: TutorSessionSummary,
  question: string,
  assistant: string,
  citation_json: TutorCitation[] = [citationItem],
  traceId: string | null = null
): TutorSessionDetail {
  return {
    session,
    messages: [
      {
        id: "m1",
        session_id: session.id,
        role: "user",
        content: question,
        citation_json: [],
        trace_id: null,
        created_at: "2026-07-03T12:00:00Z"
      },
      {
        id: "m2",
        session_id: session.id,
        role: "assistant",
        content: assistant,
        citation_json,
        trace_id: traceId,
        created_at: "2026-07-03T12:01:00Z"
      }
    ]
  };
}

function makeTwoTurnDetail(session: TutorSessionSummary): TutorSessionDetail {
  const secondCitation: TutorCitation = {
    ...citationItem,
    chunk_id: 502,
    content: "A* 搜索同时计算实际代价 g(n) 与启发式估价 h(n)。",
    source_title: "搜索算法进阶讲义.md",
    section_title: "A* 搜索"
  };

  return {
    session,
    messages: [
      {
        id: "turn-1-user",
        session_id: session.id,
        role: "user",
        content: "第一问：启发函数是什么？",
        citation_json: [],
        trace_id: null,
        created_at: "2026-07-03T12:00:00Z"
      },
      {
        id: "turn-1-assistant",
        session_id: session.id,
        role: "assistant",
        content: "第一答：启发函数用于估计剩余路径代价。",
        citation_json: [citationItem],
        trace_id: "trace_turn_1",
        created_at: "2026-07-03T12:01:00Z"
      },
      {
        id: "turn-2-user",
        session_id: session.id,
        role: "user",
        content: "第二问：A* 如何使用它？",
        citation_json: [],
        trace_id: null,
        created_at: "2026-07-03T12:02:00Z"
      },
      {
        id: "turn-2-assistant",
        session_id: session.id,
        role: "assistant",
        content: "第二答：A* 使用 f(n) = g(n) + h(n) 排序候选节点。",
        citation_json: [secondCitation],
        trace_id: "trace_turn_2",
        created_at: "2026-07-03T12:03:00Z"
      }
    ]
  };
}

function createSseStream(events: Array<{ event: string; data: unknown }>) {
  const encoder = new TextEncoder();

  return new ReadableStream<Uint8Array>({
    start(controller) {
      for (const event of events) {
        controller.enqueue(encoder.encode(`event: ${event.event}\n`));
        controller.enqueue(encoder.encode(`data: ${JSON.stringify(event.data)}\n\n`));
      }
      controller.close();
    }
  });
}

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

async function revealSecondaryActions(user: ReturnType<typeof userEvent.setup>, container: HTMLElement = document.body) {
  await waitFor(() => {
    expect(within(container).queryAllByRole("button", { name: "更多" }).length).toBeGreaterThan(0);
  });
  const buttons = within(container).getAllByRole("button", { name: "更多" });
  for (const button of buttons) {
    if (button.getAttribute("aria-expanded") !== "true") await user.click(button);
  }
}

function renderCoursePage(options: CoursePageOptions = {}) {
  const calls: ApiCall[] = [];
  const fetchCalls: FetchCall[] = [];
  let streamController: ReadableStreamDefaultController<Uint8Array> | null = null;
  const encoder = new TextEncoder();
  const createdSession = makeSession("901", "启发式搜索怎么复习？");
  let courseSessions = [...(options.sessions ?? [])];
  let learningStateRequestCount = 0;
  let masteryMapRequestCount = 0;
  let resourceListRequestCount = 0;
  let currentPathRequestCount = 0;
  let latestReportRequestCount = 0;
  const defaultSendDetail = makeDetail(
    createdSession,
    "启发式搜索怎么复习？",
    "模型回答：启发式搜索复习时先理解启发函数，再对比 A* 的实际代价和预估代价。"
  );

  apiClient.defaults.adapter = async (config) => {
    const method = (config.method ?? "get").toLowerCase();
    const url = config.url ?? "";
    const payload = parsePayload(config.data);
    calls.push({ method, url, payload, params: config.params });

    if (options.delayCourseDetail && url === COURSE_ENDPOINTS.detail(808)) {
      return new Promise(() => {});
    }

    if (options.delayCourseData && [COURSE_ENDPOINTS.detail(808), COURSE_ENDPOINTS.overview(808), COURSE_ENDPOINTS.knowledgePoints(808)].includes(url)) {
      return new Promise(() => {});
    }

    if (url === COURSE_ENDPOINTS.learningState(808)) {
      learningStateRequestCount += 1;
      if (options.failLearningState) {
        throw new Error("课程学习状态读取失败。");
      }
      if (options.failLearningStateRefreshOnce && learningStateRequestCount === 2) {
        throw new Error("课程学习状态刷新失败。");
      }

      return {
        data: {
          data:
            learningStateRequestCount > 1 && options.refreshedLearningState !== undefined
              ? options.refreshedLearningState
              : options.learningState ?? emptyLearningState,
          trace_id: "trace_learning_state"
        },
        status: 200,
        statusText: "OK",
        headers: {},
        config
      };
    }

    if (url.startsWith("/agents/traces/")) {
      if (options.failAgentTrace) {
        throw new Error("Agent 轨迹读取失败。");
      }
      const traceId = decodeURIComponent(url.split("/").pop() ?? "trace_candidate");

      return {
        data: {
          data: options.agentTrace ? { ...options.agentTrace, trace_id: traceId } : { ...agentTraceWithSteps, trace_id: traceId },
          trace_id: "trace_agent_page"
        },
        status: 200,
        statusText: "OK",
        headers: {},
        config
      };
    }

    if (url === RESOURCE_ENDPOINTS.list && method === "get") {
      resourceListRequestCount += 1;
      const resources =
        resourceListRequestCount > 1 && options.refreshedResources !== undefined
          ? options.refreshedResources
          : options.resources ?? generatedResourceItems;
      return {
        data: {
          data: resources,
          total: resources.length,
          trace_id: "trace_course_resources"
        },
        status: 200,
        statusText: "OK",
        headers: {},
        config
      };
    }

    if (url === RESOURCE_ENDPOINTS.generationJobs && method === "post") {
      if (options.failResourceGeneration) {
        throw new Error("课程资源生成失败。");
      }

      return {
        data: {
          data: makeCompletedAiJob({ result: { course_id: "808", resource_ids: generatedResourceItems.map((item) => item.id) } }),
          trace_id: "trace_course_resource_generation"
        },
        status: 200,
        statusText: "OK",
        headers: {},
        config
      };
    }

    if (url === PATH_ENDPOINTS.current && method === "get") {
      currentPathRequestCount += 1;
      return {
        data: {
          data:
            (currentPathRequestCount > 1 && options.refreshedCurrentPath !== undefined
              ? options.refreshedCurrentPath
              : options.currentPath) ??
            {
              course_id: "808",
              status: "not_started",
              message: "学习路径尚未生成。",
              agent_trace_id: null,
              path: null,
              tasks: [],
              evidence_summary: {
                knowledge_point_count: 1,
                confirmed_or_reviewing_weakness_count: 0,
                pending_weakness_count: 0,
                resource_count: 0,
                basis: []
              }
            },
          trace_id: "trace_current_path"
        },
        status: 200,
        statusText: "OK",
        headers: {},
        config
      };
    }

    if (url === REPORT_ENDPOINTS.latest && method === "get") {
      latestReportRequestCount += 1;
      return {
        data: {
          data:
            latestReportRequestCount > 1 && options.refreshedLatestReport !== undefined
              ? options.refreshedLatestReport
              : options.latestReport ?? emptyReport,
          trace_id: "trace_latest_report"
        },
        status: 200,
        statusText: "OK",
        headers: {},
        config
      };
    }

    if (url === PRACTICE_ENDPOINTS.latest && method === "get") {
      return {
        data: { data: null, trace_id: "trace_latest_practice" },
        status: 200,
        statusText: "OK",
        headers: {},
        config
      };
    }

    if (url.includes("/weakness-review-items/") && method === "post") {
      if (options.failWeaknessAction) {
        throw new Error("弱点状态更新失败。");
      }

      return {
        data: {
          data: {
            id: "701",
            title: "启发式搜索",
            status: "confirmed",
            source_type: "course_question",
            course_id: "808",
            knowledge_point_id: "401",
            recommended_resource_ids: [],
            recommended_resources: [],
            next_review_at: null,
            created_at: "2026-07-05T08:30:00Z",
            updated_at: "2026-07-05T08:40:00Z"
          },
          trace_id: "trace_weakness_action"
        },
        status: 200,
        statusText: "OK",
        headers: {},
        config
      };
    }

    if (url === COURSE_ENDPOINTS.detail(808)) {
      return {
        data: {
          data: {
            id: "808",
            title: "AI 搜索复习",
            description: "由 1 份资料生成",
            subject: "自主学习",
            source_type: "uploaded",
            status: "ready",
            progress_percent: 0,
            material_count: 1,
            knowledge_point_count: 2,
            chunk_count: 3
          },
          trace_id: "trace_course_detail"
        },
        status: 200,
        statusText: "OK",
        headers: {},
        config
      };
    }

    if (url === COURSE_ENDPOINTS.overview(808)) {
      return {
        data: {
          data: {
            course: {
              id: "808",
              title: "AI 搜索复习",
              description: "由 1 份资料生成",
              subject: "自主学习",
              source_type: "uploaded",
              status: "ready",
              progress_percent: 0,
              material_count: 1,
              knowledge_point_count: 2,
              chunk_count: 3
            },
            materials: ["人工智能导论讲义.md"],
            knowledge_points: [],
            chunk_count: 3
          },
          trace_id: "trace_course_overview"
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
          trace_id: "trace_course_points"
        },
        status: 200,
        statusText: "OK",
        headers: {},
        config
      };
    }

    if (url === COURSE_ENDPOINTS.knowledgePointContent(808, 401)) {
      return {
        data: {
          data: {
            knowledge_point: {
              id: "401",
              title: "启发式搜索",
              summary: "理解启发函数和 A*。",
              chapter: "搜索问题",
              order_index: 1,
              difficulty: "基础",
              prerequisite_ids: []
            },
            sections: [{
              chunk_id: "501",
              title: "启发式搜索",
              content: "启发式搜索使用启发函数估计剩余代价。",
              source_title: "人工智能导论讲义.md",
              page_number: null
            }],
            related_resources: [],
            previous_knowledge_point_id: null,
            next_knowledge_point_id: null
          },
          trace_id: "trace_course_content"
        },
        status: 200,
        statusText: "OK",
        headers: {},
        config
      };
    }

    if (url === COURSE_ENDPOINTS.masteryMap(808)) {
      masteryMapRequestCount += 1;
      const points =
        masteryMapRequestCount > 1 && options.refreshedMasteryPoints !== undefined
          ? options.refreshedMasteryPoints
          : options.masteryPoints ?? [];
      return {
        data: {
          data: {
            course_id: "808",
            summary: emptyLearningState.mastery_summary,
            points
          },
          trace_id: "trace_course_mastery"
        },
        status: 200,
        statusText: "OK",
        headers: {},
        config
      };
    }

    if (url === TUTOR_ENDPOINTS.sessions && method === "get") {
      return {
        data: {
          data: courseSessions,
          trace_id: "trace_course_sessions"
        },
        status: 200,
        statusText: "OK",
        headers: {},
        config
      };
    }

    const sessionDetailMatch = url.match(/^\/tutor\/sessions\/([^/]+)$/);
    if (sessionDetailMatch && method === "patch") {
      const sessionId = sessionDetailMatch[1];
      const title = typeof payload === "object" && payload !== null && "title" in payload ? String(payload.title).trim() : "";
      courseSessions = courseSessions.map((session) => (session.id === sessionId ? { ...session, title } : session));

      return {
        data: {
          data: courseSessions.find((session) => session.id === sessionId) ?? { ...makeSession(sessionId, title), title },
          trace_id: "trace_course_session_rename"
        },
        status: 200,
        statusText: "OK",
        headers: {},
        config
      };
    }

    if (sessionDetailMatch && method === "delete") {
      const sessionId = sessionDetailMatch[1];
      courseSessions = courseSessions.filter((session) => session.id !== sessionId);

      return {
        data: {
          data: {
            session_id: sessionId,
            deleted: true
          },
          trace_id: "trace_course_session_delete"
        },
        status: 200,
        statusText: "OK",
        headers: {},
        config
      };
    }

    if (url === TUTOR_ENDPOINTS.sessions && method === "post") {
      const title = typeof payload === "object" && payload !== null && "title" in payload ? String(payload.title) : "课程问题";
      createdSession.title = title;

      return {
        data: {
          data: createdSession,
          trace_id: "trace_create_course_session"
        },
        status: 200,
        statusText: "OK",
        headers: {},
        config
      };
    }

    if (
      sessionDetailMatch &&
      method === "get" &&
      (sessionDetailMatch[1] === "777" || Boolean(options.historyDetails?.[sessionDetailMatch[1]]) || Boolean(options.sessions?.some((session) => session.id === sessionDetailMatch[1])))
    ) {
      const sessionId = sessionDetailMatch[1];
      const fallbackSession =
        options.sessions?.find((session) => session.id === sessionId) ?? makeSession(sessionId, "已有课程历史");
      return {
        data: {
          data:
            options.historyDetails?.[sessionId] ??
            options.historyDetail ??
            makeDetail(
              fallbackSession,
              "历史里的问题",
              "历史里的回答保留真实引用。",
              [citationItem]
            ),
          trace_id: "trace_history_detail"
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

  globalThis.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = input instanceof Request ? input.url : String(input);
    const rawBody = typeof init?.body === "string" ? init.body : "";
    const payload = rawBody ? JSON.parse(rawBody) : null;
    fetchCalls.push({ url, method: init?.method ?? "GET", payload });

    if (options.failSend) {
      return new Response(
        createSseStream([
          {
            event: "error",
            data: {
              code: "MODEL_PROVIDER_ERROR",
              message: "模型暂不可用，请检查设置或稍后重试。"
            }
          }
        ]),
        { status: 200, headers: { "content-type": "text/event-stream" } }
      );
    }

    if (options.controlledStream) {
      const stream = new ReadableStream<Uint8Array>({
        start(controller) {
          streamController = controller;
        }
      });
      return new Response(stream, { status: 200, headers: { "content-type": "text/event-stream" } });
    }

    return new Response(
      createSseStream(
        options.streamEvents ?? [
          {
            event: "metadata",
            data: {
              session_id: createdSession.id,
              trace_id: "trace_stream_course_message",
              citation_count: 1,
              used_model: true
            }
          },
          { event: "token", data: { content: "模型回答：启发式搜索复习" } },
          { event: "token", data: { content: "时先理解启发函数。" } },
          { event: "done", data: options.sendDetail ?? defaultSendDetail }
        ]
      ),
      { status: 200, headers: { "content-type": "text/event-stream" } }
    );
  });

  renderWithProviders(
    <MemoryRouter initialEntries={[options.initialEntry ?? "/app/courses/808"]}>
      <Routes>
        <Route path={PATHS.courseDetail} element={<CourseSpacePage />} />
      </Routes>
    </MemoryRouter>
  );

  function emitStreamEvent(event: string, data: unknown) {
    if (streamController === null) {
      throw new Error("stream controller is not ready");
    }
    streamController.enqueue(encoder.encode(`event: ${event}\n`));
    streamController.enqueue(encoder.encode(`data: ${JSON.stringify(data)}\n\n`));
  }

  function closeStream() {
    streamController?.close();
  }

  return { calls, fetchCalls, emitStreamEvent, closeStream };
}

describe("CourseSpacePage course tutor sessions", () => {
  beforeEach(() => {
    previousAdapter = apiClient.defaults.adapter;
    localStorage.clear();
  });

  afterEach(() => {
    apiClient.defaults.adapter = previousAdapter;
    globalThis.fetch = previousFetch;
  });

  it("loads course-scoped tutor sessions for the current course", async () => {
    const { calls } = renderCoursePage({ sessions: [makeSession("777", "已有课程历史")] });

    const courseHistory = await screen.findByLabelText("历史对话");
    expect(await within(courseHistory).findByRole("button", { name: /已有课程历史/ })).toBeInTheDocument();
    expect(calls).toContainEqual(
      expect.objectContaining({
        method: "get",
        url: TUTOR_ENDPOINTS.sessions,
        params: {
          scope: "course",
          course_id: 808
        }
      })
    );
  });

  it("keeps course history order when selecting an older session", async () => {
    const user = userEvent.setup();
    const firstSession = makeSession("777", "上方课程历史");
    const secondSession = makeSession("778", "下方课程历史");

    renderCoursePage({
      sessions: [firstSession, secondSession],
      historyDetails: {
        "778": makeDetail(secondSession, "下方课程问题", "下方课程回答保留在原位置。")
      }
    });

    const courseHistory = await screen.findByLabelText("历史对话");
    expect((await within(courseHistory).findAllByRole("button", { name: /课程历史/ })).map((button) => button.textContent)).toEqual([
      "上方课程历史课程内",
      "下方课程历史课程内"
    ]);

    await user.click(within(courseHistory).getByRole("button", { name: /下方课程历史/ }));

    expect(await screen.findByText("下方课程问题")).toBeInTheDocument();
    expect(within(courseHistory).getAllByRole("button", { name: /课程历史/ }).map((button) => button.textContent)).toEqual([
      "上方课程历史课程内",
      "下方课程历史课程内"
    ]);
  });

  it("renames a course history conversation from the sidebar menu", async () => {
    const user = userEvent.setup();
    const { calls } = renderCoursePage({ sessions: [makeSession("777", "已有课程历史")] });

    const courseHistory = await screen.findByLabelText("历史对话");
    expect(await within(courseHistory).findByRole("button", { name: /已有课程历史/ })).toBeInTheDocument();

    await user.click(within(courseHistory).getByRole("button", { name: "打开会话操作菜单 777" }));
    await user.click(screen.getByRole("menuitem", { name: "重命名" }));

    const titleInput = screen.getByRole("textbox", { name: "会话名称" });
    await user.clear(titleInput);
    await user.type(titleInput, "A 星算法追问");
    await user.click(screen.getByRole("button", { name: "保存会话名称" }));

    expect(await within(courseHistory).findByRole("button", { name: /A 星算法追问/ })).toBeInTheDocument();
    await waitFor(() => {
      expect(calls).toContainEqual(
        expect.objectContaining({
          method: "patch",
          url: TUTOR_ENDPOINTS.detail(777),
          payload: { title: "A 星算法追问" }
        })
      );
    });
  });

  it("deletes the active course history conversation and returns to course guidance", async () => {
    const user = userEvent.setup();
    const { calls } = renderCoursePage({ sessions: [makeSession("777", "已有课程历史")] });

    const courseHistory = await screen.findByLabelText("历史对话");
    await user.click(await within(courseHistory).findByRole("button", { name: /已有课程历史/ }));
    expect(await screen.findByRole("region", { name: "课程即时对话" })).toBeInTheDocument();

    await user.click(within(courseHistory).getByRole("button", { name: "打开会话操作菜单 777" }));
    await user.click(screen.getByRole("menuitem", { name: "删除" }));
    await user.click(screen.getByRole("menuitem", { name: "确认删除" }));

    expect(await screen.findByRole("region", { name: "课程提问引导" })).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "课程即时对话" })).not.toBeInTheDocument();
    expect(within(courseHistory).queryByRole("button", { name: /已有课程历史/ })).not.toBeInTheDocument();
    await waitFor(() => {
      expect(calls).toContainEqual(
        expect.objectContaining({
          method: "delete",
          url: TUTOR_ENDPOINTS.detail(777)
        })
      );
    });
  });

  it("shows start guidance instead of a fixed assistant answer before any course message exists", async () => {
    renderCoursePage();

    expect(await screen.findByRole("heading", { name: "AI 搜索复习" })).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "待复习弱点" })).not.toBeInTheDocument();
    expect(screen.getByRole("region", { name: "课程提问引导" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "可以从这些问题开始" })).toBeInTheDocument();
    expect(screen.queryByText("从这门课开始学习")).not.toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "知识学习画布" })).not.toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "证据与 Agent 轨迹" })).not.toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "资源生成区" })).not.toBeInTheDocument();
    expect(screen.queryByText("监督学习先抓住“数据、目标、泛化”三件事")).not.toBeInTheDocument();
    expect(screen.queryByText("AI 辅导回答")).not.toBeInTheDocument();
  });

  it("shows the A3 learning loop in course space without replacing course chat", async () => {
    const user = userEvent.setup();
    renderCoursePage({ learningState: learningStateWithWeakness, currentPath: activePathDetail });

    expect(await screen.findByRole("banner", { name: "课程工作区标题栏" })).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "A3 学习步骤" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /学习进度/ }));
    expect(await screen.findByRole("dialog", { name: "学习进度" })).toBeInTheDocument();
    expect(screen.getByRole("dialog", { name: "学习进度" })).toHaveTextContent("课程画像");
    expect(screen.getByRole("dialog", { name: "学习进度" })).toHaveTextContent("总画像 + 本课程实时状态");
    expect(
      screen.getByText(/先确认问答或练习识别出的薄弱点/),
    ).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "A3 学习步骤" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "课程对话空间", hidden: true })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "进入你的学习空间" })).not.toBeInTheDocument();
  });

  it("shows course closed-loop actions after a real course answer", async () => {
    const user = userEvent.setup();
    renderCoursePage({
      sessions: [makeSession("777", "已有课程历史")],
      learningState: learningStateWithPath,
      currentPath: activePathDetail
    });

    expect(await screen.findByRole("heading", { name: "AI 搜索复习" })).toBeInTheDocument();
    const loopActions = await screen.findByRole("region", { name: "课程闭环行动" });
    await revealSecondaryActions(user, loopActions);

    expect(within(loopActions).getByRole("button", { name: /来源/ })).toBeInTheDocument();
    expect(within(loopActions).getByRole("button", { name: /生成资源/ })).toBeInTheDocument();
    expect(within(loopActions).getByRole("button", { name: /学习路径/ })).toBeInTheDocument();
    expect(within(loopActions).getByRole("link", { name: /进入练习/ }).getAttribute("href")).toContain(
      `${PATHS.practice}?course_id=808`
    );
    expect(within(loopActions).getByRole("link", { name: /学习报告/ }).getAttribute("href")).toContain(
      `${PATHS.reports}?course_id=808`
    );
    expect(within(loopActions).getByRole("button", { name: /课堂协作轨迹/ })).toBeInTheDocument();
  });

  it("hides echoed model context from persisted course answers", async () => {
    renderCoursePage({
      sessions: [makeSession("777", "已有课程历史")],
      historyDetail: makeDetail(
        makeSession("777", "已有课程历史"),
        "这门课最适合先复习哪些知识点？",
        [
          "学生问题：这门课最适合先复习哪些知识点？",
          "",
          "课程引用：",
          "[1] 来源：人工智能导论讲义.md",
          "章节：启发式搜索",
          "匹配度：9.5",
          "片段：启发式搜索利用启发函数估计路径代价。",
          "",
          "根据上述引用，可以先复习启发式搜索，再通过练习确认掌握度。"
        ].join("\n")
      )
    });

    expect(await screen.findByText("根据上述引用，可以先复习启发式搜索，再通过练习确认掌握度。")).toBeInTheDocument();
    expect(screen.queryByText(/学生问题：/)).not.toBeInTheDocument();
    expect(screen.queryByText(/课程引用：/)).not.toBeInTheDocument();
    expect(screen.queryByText(/匹配度：9.5/)).not.toBeInTheDocument();
  });

  it("keeps inline source metadata out of persisted answer text", async () => {
    renderCoursePage({
      sessions: [makeSession("777", "已有课程历史")],
      historyDetail: makeDetail(
        makeSession("777", "已有课程历史"),
        "请给我排序",
        "1. 符号知识表达（匹配度：2.4667） - 来源：[1] - 片段：知识表示关注如何把事实、概念、关系和规则编码成机器可处理的结构。"
      )
    });

    expect(await screen.findByText(/符号知识表达：知识表示关注/)).toBeInTheDocument();
    expect(screen.queryByText(/匹配度：2.4667/)).not.toBeInTheDocument();
    expect(screen.queryByText(/来源：\[1\]/)).not.toBeInTheDocument();
    expect(screen.queryByText(/片段：/)).not.toBeInTheDocument();
  });

  it("keeps numbered source detail sections out of persisted answer text", async () => {
    renderCoursePage({
      sessions: [makeSession("777", "已有课程历史")],
      historyDetail: makeDetail(
        makeSession("777", "已有课程历史"),
        "请解释一个知识点",
        [
          "**概念解释：** 符号知识表达关注如何把事实、概念、关系和规则编码成机器可处理的结构。",
          "**依据：** 1. 来源：人工智能导论内置课程包.md 2. 章节：符号知识表达 3. 片段：知识表示关注如何把事实、概念、关系和规则编码成机器可处理的结构。",
          "**易错点：** 不要把符号规则和统计学习混为一谈。",
          "**下一步练习：** 用自己的话写出一个 IF-THEN 规则。"
        ].join(" ")
      )
    });

    expect(await screen.findByText(/符号知识表达关注/)).toBeInTheDocument();
    expect(screen.getByText(/易错点/)).toBeInTheDocument();
    expect(screen.getByText(/下一步练习/)).toBeInTheDocument();
    expect(screen.queryByText(/来源：人工智能导论内置课程包/)).not.toBeInTheDocument();
    expect(screen.queryByText(/章节：符号知识表达/)).not.toBeInTheDocument();
    expect(screen.queryByText(/片段：知识表示/)).not.toBeInTheDocument();
  });

  it("lets the student generate six A3 resource types from course space", async () => {
    const user = userEvent.setup();
    const { calls } = renderCoursePage({
      sessions: [makeSession("777", "已有课程历史")],
      learningState: learningStateWithWeakness,
      resources: []
    });

    await screen.findByRole("heading", { name: "AI 搜索复习" });
    await revealSecondaryActions(user);
    await user.click(await screen.findByRole("button", { name: /生成资源/ }));

    const resourcePanel = await screen.findByRole("region", { name: "课程资源生成" });
    expect(within(resourcePanel).getByLabelText("讲解文档")).toBeChecked();
    expect(within(resourcePanel).getByLabelText("思维导图")).toBeChecked();
    expect(within(resourcePanel).getByLabelText("练习题")).toBeChecked();
    expect(within(resourcePanel).getByLabelText("代码实操")).not.toBeChecked();
    expect(within(resourcePanel).getByLabelText("PPT")).not.toBeChecked();
    expect(within(resourcePanel).getByLabelText("动画图解")).not.toBeChecked();
    await user.click(within(resourcePanel).getByLabelText("代码实操"));
    await user.click(within(resourcePanel).getByLabelText("PPT"));
    await user.click(within(resourcePanel).getByLabelText("动画图解"));

    await user.click(within(resourcePanel).getByRole("button", { name: "生成 6 类个性化资源" }));

    await waitFor(() => {
      expect(calls).toContainEqual(
        expect.objectContaining({
          method: "post",
          url: RESOURCE_ENDPOINTS.generationJobs,
          payload: expect.objectContaining({
            course_id: 808,
            resource_types: ["doc", "mindmap", "quiz", "code", "slide", "animation"]
          })
        })
      );
    });
  });

  it("keeps citations attached to their own assistant turn", async () => {
    const user = userEvent.setup();
    const session = makeSession("777", "两轮课程问答");
    renderCoursePage({
      sessions: [session],
      historyDetail: makeTwoTurnDetail(session)
    });

    const thread = await screen.findByRole("region", { name: "课程即时对话" });
    await revealSecondaryActions(user, thread);
    const sourceButtons = within(thread).getAllByRole("button", { name: "来源" });

    await user.click(sourceButtons[0]);
    let detailPanel = await screen.findByRole("region", { name: "回答展开详情" });
    expect(within(detailPanel).getByText("人工智能导论讲义.md")).toBeInTheDocument();
    expect(within(detailPanel).queryByText("搜索算法进阶讲义.md")).not.toBeInTheDocument();

    await user.click(sourceButtons[1]);
    detailPanel = await screen.findByRole("region", { name: "回答展开详情" });
    expect(within(detailPanel).getByText("搜索算法进阶讲义.md")).toBeInTheDocument();
    expect(within(detailPanel).queryByText("人工智能导论讲义.md")).not.toBeInTheDocument();
  });

  it("uses the matching historical question when generating resources from an answer", async () => {
    const user = userEvent.setup();
    const session = makeSession("777", "两轮课程问答");
    const { calls } = renderCoursePage({
      sessions: [session],
      historyDetail: makeTwoTurnDetail(session)
    });

    const thread = await screen.findByRole("region", { name: "课程即时对话" });
    await revealSecondaryActions(user, thread);
    await user.click(within(thread).getAllByRole("button", { name: "生成资源" })[0]);
    const resourcePanel = await screen.findByRole("region", { name: "课程资源生成" });
    await user.click(within(resourcePanel).getByRole("button", { name: "生成 3 类个性化资源" }));

    await waitFor(() => {
      expect(calls).toContainEqual(
        expect.objectContaining({
          method: "post",
          url: RESOURCE_ENDPOINTS.generationJobs,
          payload: expect.objectContaining({
            learning_goal: "第一问：启发函数是什么？",
            knowledge_point_id: 401,
            difficulty: "medium"
          })
        })
      );
    });
  });

  it("omits knowledge point context when an answer has no valid citation", async () => {
    const user = userEvent.setup();
    const session = makeSession("777", "无依据回答");
    const { calls } = renderCoursePage({
      sessions: [session],
      historyDetail: makeDetail(session, "量子通信怎么复习？", "课程资料暂时没有足够依据。", [])
    });

    const thread = await screen.findByRole("region", { name: "课程即时对话" });
    await revealSecondaryActions(user, thread);
    await user.click(within(thread).getByRole("button", { name: "生成资源" }));
    const resourcePanel = await screen.findByRole("region", { name: "课程资源生成" });
    await user.click(within(resourcePanel).getByRole("button", { name: "生成 3 类个性化资源" }));

    await waitFor(() => {
      const request = calls.find((call) => call.method === "post" && call.url === RESOURCE_ENDPOINTS.generationJobs);
      expect(request?.payload).toEqual(expect.objectContaining({ learning_goal: "量子通信怎么复习？", difficulty: "medium" }));
      expect(request?.payload).not.toHaveProperty("knowledge_point_id");
    });
  });

  it("links practice and reports entries with the current course preselected", async () => {
    renderCoursePage();

    const actionLinks = await screen.findByRole("navigation", { name: "课程行动入口" });
    expect(within(actionLinks).getByRole("link", { name: "开始练习" })).toHaveAttribute(
      "href",
      `${PATHS.practice}?course_id=808`
    );
    expect(within(actionLinks).getByRole("link", { name: "查看学习报告" })).toHaveAttribute(
      "href",
      `${PATHS.reports}?course_id=808`
    );
  });

  it("renders pending course weakness review items from learning state", async () => {
    const user = userEvent.setup();
    renderCoursePage({ learningState: learningStateWithWeakness });

    await user.click(await screen.findByRole("button", { name: /学习进度/ }));
    const weaknessRegion = await screen.findByRole("region", { name: "待复习弱点" });
    await within(weaknessRegion).findByText("启发式搜索");

    expect(weaknessRegion).toHaveTextContent(/待确认\s*1/);
    expect(weaknessRegion).toHaveTextContent(/候选证据\s*2/);
    expect(within(weaknessRegion).getByText("启发式搜索")).toBeInTheDocument();
    expect(within(weaknessRegion).getAllByText("待确认").length).toBeGreaterThanOrEqual(2);
    expect(within(weaknessRegion).queryByText("学习路径尚未生成")).not.toBeInTheDocument();
  });

  it("renders actionable course weakness review states", async () => {
    const user = userEvent.setup();
    renderCoursePage({ learningState: learningStateWithReviewFlow });

    await user.click(await screen.findByRole("button", { name: /学习进度/ }));
    const weaknessRegion = await screen.findByRole("region", { name: "待复习弱点" });
    await within(weaknessRegion).findByText("启发式搜索");

    expect(weaknessRegion).toHaveTextContent(/待确认\s*1/);
    expect(weaknessRegion).toHaveTextContent(/待复习\s*1/);
    expect(weaknessRegion).toHaveTextContent(/复习中\s*1/);
    expect(weaknessRegion).toHaveTextContent(/已完成\s*1/);
    expect(within(weaknessRegion).getByRole("button", { name: "确认 启发式搜索" })).toBeInTheDocument();
    expect(within(weaknessRegion).getByRole("button", { name: "开始 启发式搜索" })).toBeInTheDocument();
    expect(within(weaknessRegion).getByRole("button", { name: "忽略 启发式搜索" })).toBeInTheDocument();
    expect(within(weaknessRegion).getByRole("button", { name: "开始 反向传播" })).toBeInTheDocument();
    expect(within(weaknessRegion).getByRole("button", { name: "完成 A* 搜索" })).toBeInTheDocument();
    expect(within(weaknessRegion).getByRole("button", { name: "移除 搜索复杂度" })).toBeInTheDocument();
    expect(within(weaknessRegion).queryByText("已忽略弱点")).not.toBeInTheDocument();
  });

  it("updates a weakness review item and refreshes course learning state", async () => {
    const user = userEvent.setup();
    const { calls } = renderCoursePage({ learningState: learningStateWithReviewFlow });

    await user.click(await screen.findByRole("button", { name: /学习进度/ }));
    const weaknessRegion = await screen.findByRole("region", { name: "待复习弱点" });
    await user.click(await within(weaknessRegion).findByRole("button", { name: "确认 启发式搜索" }));

    await waitFor(() => {
      expect(calls).toContainEqual(
        expect.objectContaining({
          method: "post",
          url: COURSE_ENDPOINTS.weaknessReviewAction(808, "701", "confirm")
        })
      );
    });
    await waitFor(() => {
      expect(calls.filter((call) => call.url === COURSE_ENDPOINTS.learningState(808))).toHaveLength(3);
    });
  });

  it("refreshes the full course loop when the progress drawer opens", async () => {
    const user = userEvent.setup();
    const initialMasteryPoint = {
      id: "401",
      title: "启发式搜索",
      chapter: "搜索问题",
      order_index: 1,
      status: "learning",
      score: 20,
      prerequisite_ids: [],
      weakness_item_ids: [],
      recommended_resource_ids: []
    };
    const { calls } = renderCoursePage({
      learningState: emptyLearningState,
      refreshedLearningState: learningStateWithPath,
      masteryPoints: [initialMasteryPoint],
      refreshedMasteryPoints: [
        { ...initialMasteryPoint, status: "mastered", score: 91 },
        { ...initialMasteryPoint, id: "402", title: "A* 搜索", score: 62 }
      ],
      resources: [],
      refreshedResources: generatedResourceItems,
      currentPath: null,
      refreshedCurrentPath: activePathDetail,
      latestReport: emptyReport,
      refreshedLatestReport: { ...emptyReport, id: "990", status: "ready", score: 78 }
    });

    await waitFor(() => {
      expect(screen.getByLabelText("课程状态")).toHaveTextContent("掌握度 20%");
    });
    await user.click(screen.getByRole("button", { name: /学习进度/ }));

    await waitFor(() => {
      expect(screen.getByLabelText("课程状态")).toHaveTextContent("掌握度 77%");
    });
    const drawer = screen.getByRole("dialog", { name: "学习进度" });
    expect(within(drawer).getByText("通过自适应练习验证薄弱点是否已经掌握。")).toBeInTheDocument();
    expect(within(drawer).getByText("针对练习：启发式搜索")).toBeInTheDocument();
    expect(within(drawer).getByText(/1 份资料 · 2 个知识点 · 0 条引用 · 1 个资源/)).toBeInTheDocument();
    expect(within(drawer).getByText("启发式搜索")).toBeInTheDocument();

    for (const url of [
      COURSE_ENDPOINTS.learningState(808),
      COURSE_ENDPOINTS.masteryMap(808),
      RESOURCE_ENDPOINTS.list,
      PATH_ENDPOINTS.current,
      REPORT_ENDPOINTS.latest,
      PRACTICE_ENDPOINTS.latest
    ]) {
      expect(calls.filter((call) => call.url === url)).toHaveLength(2);
    }
  });

  it("keeps the last successful progress data when one refresh fails and can retry", async () => {
    const user = userEvent.setup();
    renderCoursePage({
      learningState: learningStateWithWeakness,
      refreshedLearningState: emptyLearningState,
      failLearningStateRefreshOnce: true,
      resources: [],
      currentPath: null,
      latestReport: emptyReport
    });

    await user.click(await screen.findByRole("button", { name: /学习进度/ }));
    const drawer = screen.getByRole("dialog", { name: "学习进度" });
    expect(await within(drawer).findByText("部分学习状态暂未更新，已保留上次成功结果。")).toBeInTheDocument();
    expect(within(drawer).getByText("启发式搜索")).toBeInTheDocument();
    expect(within(drawer).queryByText("课程学习状态读取失败，请稍后重试。")).not.toBeInTheDocument();

    await user.click(within(drawer).getByRole("button", { name: "刷新学习进度" }));
    await waitFor(() => {
      expect(within(drawer).queryByText("部分学习状态暂未更新，已保留上次成功结果。")).not.toBeInTheDocument();
    });
    expect(within(drawer).queryByText("启发式搜索")).not.toBeInTheDocument();
  });

  it("shows local feedback when weakness review item update fails without blocking course questions", async () => {
    const user = userEvent.setup();
    const { fetchCalls } = renderCoursePage({ learningState: learningStateWithReviewFlow, failWeaknessAction: true });

    await user.click(await screen.findByRole("button", { name: /学习进度/ }));
    const weaknessRegion = await screen.findByRole("region", { name: "待复习弱点" });
    await user.click(await within(weaknessRegion).findByRole("button", { name: "确认 启发式搜索" }));

    expect(await within(weaknessRegion).findByText("弱点状态更新失败，请稍后重试。")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "关闭学习进度" }));

    await user.type(screen.getByRole("textbox", { name: "课程问题输入" }), "为什么启发式搜索这么难？");
    await user.click(screen.getByRole("button", { name: "发送" }));

    await waitFor(() => {
      expect(fetchCalls).toContainEqual(
        expect.objectContaining({
          method: "POST",
          url: `/api/v1${TUTOR_ENDPOINTS.stream("901")}`
        })
      );
    });
  });

  it("shows local feedback when course learning state fails to load", async () => {
    const user = userEvent.setup();
    renderCoursePage({ failLearningState: true });

    await user.click(await screen.findByRole("button", { name: /学习进度/ }));
    expect(await screen.findByText("课程学习状态读取失败，请稍后重试。")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "AI 搜索复习", hidden: true })).toBeInTheDocument();
  });

  it("renders real agent trace steps in the thinking panel", async () => {
    const user = userEvent.setup();
    const { calls } = renderCoursePage({
      sessions: [makeSession("777", "已有课程历史")],
      learningState: learningStateWithWeakness,
      agentTrace: agentTraceWithSteps
    });

    await screen.findByRole("heading", { name: "AI 搜索复习" });
    await revealSecondaryActions(user);
    await user.click(await screen.findByRole("button", { name: /课堂协作轨迹/ }));

    const detailPanel = await screen.findByRole("region", { name: "回答展开详情" });
    expect(await within(detailPanel).findByLabelText("Agent 执行轨迹")).toBeInTheDocument();
    expect(within(detailPanel).getByText("retrieve")).toBeInTheDocument();
    expect(within(detailPanel).getByText("命中 2 条引用")).toBeInTheDocument();
    expect(within(detailPanel).getByText("已参考最近 4 条会话，并使用历史摘要")).toBeInTheDocument();
    expect(within(detailPanel).getByText("diagnosis")).toBeInTheDocument();
    expect(calls).toContainEqual(
      expect.objectContaining({
        method: "get",
        url: AGENT_ENDPOINTS.trace("trace_candidate")
      })
    );
  });

  it("prefers the current assistant trace over the learning-state fallback trace", async () => {
    const user = userEvent.setup();
    const session = makeSession("777", "已有课程历史");
    const { calls } = renderCoursePage({
      sessions: [session],
      learningState: learningStateWithWeakness,
      historyDetail: makeDetail(
        session,
        "A 星搜索和启发函数有什么关系？",
        "模型回答：A* 会同时看 g(n) 和 h(n)。",
        [citationItem],
        "trace_message_current"
      ),
      agentTrace: { ...agentTraceWithSteps, trace_id: "trace_message_current" }
    });

    await screen.findByRole("heading", { name: "AI 搜索复习" });
    await revealSecondaryActions(user);
    await user.click(await screen.findByRole("button", { name: /课堂协作轨迹/ }));

    const detailPanel = await screen.findByRole("region", { name: "回答展开详情" });
    expect(await within(detailPanel).findByLabelText("Agent 执行轨迹")).toBeInTheDocument();
    expect(calls).toContainEqual(
      expect.objectContaining({
        method: "get",
        url: AGENT_ENDPOINTS.trace("trace_message_current")
      })
    );
    expect(calls).not.toContainEqual(
      expect.objectContaining({
        method: "get",
        url: AGENT_ENDPOINTS.trace("trace_candidate")
      })
    );
  });

  it("links the resources panel to the real studio with the current course preselected", async () => {
    const user = userEvent.setup();
    renderCoursePage({
      sessions: [makeSession("777", "已有课程历史")],
      learningState: learningStateWithWeakness
    });

    await screen.findByRole("heading", { name: "AI 搜索复习" });
    await revealSecondaryActions(user);
    await user.click(await screen.findByRole("button", { name: /生成资源/ }));

    const detailPanel = await screen.findByRole("region", { name: "回答展开详情" });
    expect(within(detailPanel).getByRole("link", { name: "进入资源工坊" })).toHaveAttribute(
      "href",
      `${PATHS.studio}?course_id=808`
    );
    expect(within(detailPanel).queryByText(/后续阶段接入/)).not.toBeInTheDocument();
  });

  it("shows real learning path summary and links to the course path workspace", async () => {
    const user = userEvent.setup();
    renderCoursePage({
      sessions: [makeSession("777", "已有课程历史")],
      learningState: learningStateWithPath
    });

    await screen.findByRole("heading", { name: "AI 搜索复习" });
    await revealSecondaryActions(user);
    await user.click(await screen.findByRole("button", { name: /学习路径/ }));

    const detailPanel = await screen.findByRole("region", { name: "回答展开详情" });
    expect(within(detailPanel).getByText("当前学习路径进行中。")).toBeInTheDocument();
    expect(within(detailPanel).getByText("复习启发式搜索")).toBeInTheDocument();
    expect(within(detailPanel).getByRole("link", { name: "查看完整路径" }).getAttribute("href")).toContain(
      `${PATHS.path}?course_id=808`
    );
    expect(within(detailPanel).queryByText("先围绕本次命中的来源复习核心概念")).not.toBeInTheDocument();
  });

  it("renders a real empty state when the agent trace has no steps", async () => {
    const user = userEvent.setup();
    renderCoursePage({
      sessions: [makeSession("777", "已有课程历史")],
      learningState: learningStateWithWeakness,
      agentTrace: {
        trace_id: "trace_candidate",
        workflow: "course_tutor",
        artifact_type: "chat_message",
        artifact_id: "2",
        course_id: "808",
        status: "completed",
        steps: []
      }
    });

    await screen.findByRole("heading", { name: "AI 搜索复习" });
    await revealSecondaryActions(user);
    await user.click(await screen.findByRole("button", { name: /课堂协作轨迹/ }));

    const detailPanel = await screen.findByRole("region", { name: "回答展开详情" });
    expect(await within(detailPanel).findByText("当前 Agent trace 暂无可展示步骤。")).toBeInTheDocument();
    expect(within(detailPanel).queryByLabelText("Agent 执行轨迹")).not.toBeInTheDocument();
  });

  it("shows local thinking-panel feedback when agent trace loading fails", async () => {
    const user = userEvent.setup();
    renderCoursePage({
      sessions: [makeSession("777", "已有课程历史")],
      learningState: learningStateWithWeakness,
      failAgentTrace: true
    });

    await screen.findByRole("heading", { name: "AI 搜索复习" });
    await revealSecondaryActions(user);
    await user.click(await screen.findByRole("button", { name: /课堂协作轨迹/ }));

    const detailPanel = await screen.findByRole("region", { name: "回答展开详情" });
    expect(await within(detailPanel).findByText("Agent 轨迹读取失败，请稍后重试。")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /学习进度/ }));
    expect(screen.getByRole("region", { name: "待复习弱点" })).toHaveTextContent("启发式搜索");
  });

  it("does not show demo course fallback while real course data is loading", () => {
    renderCoursePage({ delayCourseData: true });

    expect(screen.queryByRole("heading", { name: "人工智能导论" })).not.toBeInTheDocument();
    expect(screen.queryByText("AI 导论内置讲义")).not.toBeInTheDocument();
    expect(screen.queryByText("监督学习与泛化")).not.toBeInTheDocument();
  });

  it("keeps the real course title when detail is pending but overview is available", async () => {
    renderCoursePage({ delayCourseDetail: true });

    expect(await screen.findByRole("heading", { name: "AI 搜索复习" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "课程加载中" })).not.toBeInTheDocument();
    expect(screen.getByLabelText("课程状态")).toHaveTextContent("1 份资料");
    expect(screen.getByLabelText("课程状态")).toHaveTextContent("2 个知识点");
  });

  it("creates a course session before sending the first course question and renders persisted citations", async () => {
    const user = userEvent.setup();
    const { calls, fetchCalls } = renderCoursePage();

    await screen.findByRole("heading", { name: "AI 搜索复习" });
    await user.type(screen.getByRole("textbox", { name: "课程问题输入" }), "启发式搜索怎么复习？");
    await user.click(screen.getByRole("button", { name: "发送" }));

    expect(calls).toContainEqual(
      expect.objectContaining({
        method: "post",
        url: TUTOR_ENDPOINTS.sessions,
        payload: {
          scope: "course",
          course_id: 808,
          mode: "chat",
          title: "启发式搜索怎么复习？"
        }
      })
    );
    await waitFor(() => {
      expect(fetchCalls).toContainEqual(
        expect.objectContaining({
          method: "POST",
          url: `/api/v1${TUTOR_ENDPOINTS.stream("901")}`,
          payload: {
            message: "启发式搜索怎么复习？"
          }
        })
      );
    });
    const thread = await screen.findByRole("region", { name: "课程即时对话" });
    await revealSecondaryActions(user, thread);
    await user.click(within(thread).getByRole("button", { name: "来源" }));
    expect(await screen.findAllByText("人工智能导论讲义.md")).not.toHaveLength(0);
    expect(screen.getByText(/模型回答：启发式搜索复习/)).toBeInTheDocument();
    expect(screen.getAllByText("启发式搜索")).not.toHaveLength(0);
    expect(screen.getAllByText("混合检索")).not.toHaveLength(0);
    expect(screen.getAllByText(/基础关键词检索/)).not.toHaveLength(0);
    expect(screen.getByText(/启发函数估计路径代价/)).toBeInTheDocument();
    expect(screen.queryByText("监督学习先抓住“数据、目标、泛化”三件事")).not.toBeInTheDocument();
  });

  it("refreshes course learning state after a course question is sent", async () => {
    const user = userEvent.setup();
    const { calls } = renderCoursePage();

    await screen.findByRole("heading", { name: "AI 搜索复习" });
    await user.type(screen.getByRole("textbox", { name: "课程问题输入" }), "为什么启发式搜索这么难？");
    await user.click(screen.getByRole("button", { name: "发送" }));

    await waitFor(() => {
      expect(calls.filter((call) => call.url === COURSE_ENDPOINTS.learningState(808))).toHaveLength(2);
    });
  });

  it("opens study mode from a course knowledge point", async () => {
    const user = userEvent.setup();

    renderCoursePage();

    await screen.findByRole("heading", { name: "AI 搜索复习" });
    expect(screen.getByRole("button", { name: "问答" })).toHaveAttribute("aria-pressed", "true");

    await user.click(screen.getByRole("button", { name: "课程内容" }));

    const studyMode = screen.getByRole("region", { name: "课程内容模式" });
    expect(studyMode).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "课程内容" })).toHaveAttribute("aria-pressed", "true");
    expect(within(studyMode).getByRole("heading", { name: "启发式搜索", level: 2 })).toBeInTheDocument();
    expect(within(studyMode).getByText("理解启发函数和 A*。")).toBeInTheDocument();
    expect(within(studyMode).getByLabelText("知识点信息")).toHaveTextContent("搜索问题");
    expect(screen.queryByRole("dialog", { name: "AI 辅导" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "围绕这里提问" }));
    expect(screen.getByRole("dialog", { name: "AI 辅导" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "关闭 AI 辅导" }));

    await user.click(screen.getByRole("button", { name: "问答" }));

    expect(screen.getByRole("region", { name: "课程提问引导" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "问答" })).toHaveAttribute("aria-pressed", "true");
  });

  it("reuses the active course session for follow-up questions", async () => {
    const user = userEvent.setup();
    const { calls, fetchCalls } = renderCoursePage();

    const input = await screen.findByRole("textbox", { name: "课程问题输入" });
    await user.type(input, "启发式搜索怎么复习？");
    await user.click(screen.getByRole("button", { name: "发送" }));
    await screen.findByText(/模型回答：启发式搜索复习/);
    await user.type(input, "再讲讲 A*。");
    await user.click(screen.getByRole("button", { name: "发送" }));

    expect(calls.filter((call) => call.method === "post" && call.url === TUTOR_ENDPOINTS.sessions)).toHaveLength(1);
    await waitFor(() => {
      expect(fetchCalls.filter((call) => call.url === `/api/v1${TUTOR_ENDPOINTS.stream("901")}`)).toHaveLength(2);
    });
  });

  it("renders streamed answer tokens before replacing them with persisted messages", async () => {
    const user = userEvent.setup();
    const { emitStreamEvent, closeStream } = renderCoursePage({ controlledStream: true });

    await screen.findByRole("heading", { name: "AI 搜索复习" });
    await user.type(screen.getByRole("textbox", { name: "课程问题输入" }), "启发式搜索怎么复习？");
    await user.click(screen.getByRole("button", { name: "发送" }));

    emitStreamEvent("metadata", {
      session_id: "901",
      trace_id: "trace_stream_course_message",
      citation_count: 1,
      used_model: true
    });
    emitStreamEvent("token", { content: "模型回答：" });

    expect(await screen.findByText("模型回答：")).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "课程闭环行动" })).not.toBeInTheDocument();

    emitStreamEvent("token", { content: "先看启发函数。" });
    emitStreamEvent("done", makeDetail(makeSession("901", "启发式搜索怎么复习？"), "启发式搜索怎么复习？", "持久化后的完整回答。", [citationItem]));
    closeStream();

    expect(await screen.findByText("持久化后的完整回答。")).toBeInTheDocument();
    expect(screen.queryByText("模型回答：先看启发函数。")).not.toBeInTheDocument();
    expect(screen.getByRole("region", { name: "课程闭环行动" })).toBeInTheDocument();
  });

  it("loads persisted messages and citations when selecting course history", async () => {
    const user = userEvent.setup();

    renderCoursePage({ sessions: [makeSession("777", "已有课程历史")] });

    const courseHistory = await screen.findByLabelText("历史对话");
    await user.click(await within(courseHistory).findByRole("button", { name: /已有课程历史/ }));

    const returnedThread = await screen.findByRole("region", { name: "课程即时对话" });
    expect(within(returnedThread).getByText("历史里的问题")).toBeInTheDocument();
    expect(within(returnedThread).getByText("历史里的回答保留真实引用。")).toBeInTheDocument();
    await revealSecondaryActions(user, returnedThread);
    await user.click(within(returnedThread).getByRole("button", { name: "来源" }));
    expect(screen.getAllByText("人工智能导论讲义.md")).not.toHaveLength(0);
    expect(screen.getByText(/启发函数估计路径代价/)).toBeInTheDocument();
  });

  it("opens study mode from a persisted citation and keeps the current session when returning", async () => {
    const user = userEvent.setup();

    renderCoursePage({ sessions: [makeSession("777", "已有课程历史")] });

    const courseHistory = await screen.findByLabelText("历史对话");
    await user.click(await within(courseHistory).findByRole("button", { name: /已有课程历史/ }));

    const thread = await screen.findByRole("region", { name: "课程即时对话" });
    await revealSecondaryActions(user, thread);
    await user.click(within(thread).getByRole("button", { name: "来源" }));
    await user.click(await screen.findByRole("button", { name: /人工智能导论讲义\.md/ }));

    const studyMode = screen.getByRole("region", { name: "课程内容模式" });
    expect(within(studyMode).getByText("从回答来源进入")).toBeInTheDocument();
    expect(within(studyMode).getByRole("heading", { name: "启发式搜索", level: 2 })).toBeInTheDocument();
    expect(within(studyMode).getByText(/启发函数估计路径代价/)).toBeInTheDocument();
    expect(within(studyMode).getByLabelText("本次回答引用")).toHaveTextContent("人工智能导论讲义.md");
    expect(within(studyMode).getByLabelText("本次回答引用")).toHaveTextContent("基础检索");
    expect(within(studyMode).getByText("启发式搜索使用启发函数估计剩余代价。")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "围绕这里提问" }));
    expect(screen.getByRole("dialog", { name: "AI 辅导" })).toHaveTextContent("历史里的回答保留真实引用。");
    await user.click(screen.getByRole("button", { name: "关闭 AI 辅导" }));

    await user.click(screen.getByRole("button", { name: "问答" }));

    const returnedThread = await screen.findByRole("region", { name: "课程即时对话" });
    expect(within(returnedThread).getByText("历史里的问题")).toBeInTheDocument();
    expect(within(returnedThread).getByText("历史里的回答保留真实引用。")).toBeInTheDocument();
  });

  it("restores the source answer before knowledge content when returning from practice", async () => {
    renderCoursePage({
      initialEntry: "/app/courses/808?course_session_id=777&course_message_id=m2&knowledge_point_id=401",
      sessions: [makeSession("777", "已有课程历史")]
    });

    const returnedThread = await screen.findByRole("region", { name: "课程即时对话" });
    expect(within(returnedThread).getByText("历史里的回答保留真实引用。")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "问答" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.queryByRole("region", { name: "课程内容模式" })).not.toBeInTheDocument();
  });

  it("shows an insufficient-evidence message from persisted assistant citations", async () => {
    const user = userEvent.setup();
    const session = makeSession("901", "量子通信怎么复习？");

    renderCoursePage({
      sendDetail: makeDetail(session, "量子通信怎么复习？", "我先检查了课程资料，但还没有足够依据支撑这个问题。", [])
    });

    await screen.findByRole("heading", { name: "AI 搜索复习" });
    await user.type(screen.getByRole("textbox", { name: "课程问题输入" }), "量子通信怎么复习？");
    await user.click(screen.getByRole("button", { name: "发送" }));

    const thread = await screen.findByRole("region", { name: "课程即时对话" });
    expect(within(thread).getByText("我先检查了课程资料，但还没有足够依据支撑这个问题。")).toBeInTheDocument();
    await revealSecondaryActions(user, thread);
    await user.click(within(thread).getByRole("button", { name: "来源" }));
    expect(screen.getByRole("region", { name: "回答展开详情" })).toHaveTextContent("当前课程资料里没有找到足够依据。");
  });

  it("keeps the typed question when course message persistence fails", async () => {
    const user = userEvent.setup();

    renderCoursePage({ failSend: true });

    const input = await screen.findByRole("textbox", { name: "课程问题输入" });
    await user.type(input, "这次保存会失败吗？");
    await user.click(screen.getByRole("button", { name: "发送" }));

    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    expect(await screen.findByRole("alert")).toHaveTextContent("模型暂不可用，请检查设置或稍后重试。");
    expect(input).toHaveValue("这次保存会失败吗？");
    expect(screen.queryByRole("region", { name: "课程即时对话" })).not.toBeInTheDocument();
  });
});

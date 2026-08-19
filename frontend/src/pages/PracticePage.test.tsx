import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { AGENT_ENDPOINTS } from "../api/agents";
import { AI_JOB_ENDPOINTS, type AiJob } from "../api/aiJobs";
import { apiClient } from "../api/client";
import { COURSE_ENDPOINTS } from "../api/courses";
import { PRACTICE_ENDPOINTS } from "../api/practice";
import { RESOURCE_ENDPOINTS } from "../api/resources";
import { PATHS } from "../app/routePaths";
import { courseLoopQueryKeys } from "../features/course-space/courseLoopQueries";
import { selectResumablePracticeJob } from "../features/practice/practiceJobSelection";
import { PracticePage } from "./PracticePage";

let previousAdapter = apiClient.defaults.adapter;

function LocationProbe() {
  const location = useLocation();
  return <output data-testid="location">{location.pathname}{location.search}</output>;
}

function renderWithProviders(initialPath = `${PATHS.practice}?course_id=808&new=1`, seedLatest = false) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  if (seedLatest) queryClient.setQueryData(courseLoopQueryKeys.latestPractice(808), { data: completedSession });
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialPath]}>
        <Routes>
          <Route path={PATHS.practice} element={<><PracticePage /><LocationProbe /></>} />
          <Route path={PATHS.coursePractice} element={<><PracticePage /><LocationProbe /></>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

function parsePayload(data: unknown) {
  return typeof data === "string" ? JSON.parse(data) : data;
}

const coursesResponse = {
  data: [{
    id: "808",
    title: "人工智能导论",
    description: "课程资料",
    subject: "人工智能",
    source_type: "uploaded",
    status: "ready",
    progress_percent: 0,
    material_count: 1,
    knowledge_point_count: 2,
    chunk_count: 4
  }],
  page: 1,
  page_size: 1,
  total: 1,
  trace_id: "trace_courses"
};

const pointsResponse = {
  data: [
    { id: "401", title: "启发式搜索", summary: "理解启发函数。", chapter: "搜索问题", order_index: 0, difficulty: null },
    { id: "402", title: "A* 搜索", summary: "理解代价函数。", chapter: "搜索问题", order_index: 1, difficulty: null }
  ],
  trace_id: "trace_points"
};

const questions = [
  {
    id: "q1",
    question_type: "single_choice",
    knowledge_point_id: "401",
    knowledge_point_title: "启发式搜索",
    prompt: "启发函数的主要作用是什么？",
    options: ["估计剩余代价", "保存完整路径"],
    correct_answer: null,
    keywords: ["估计", "代价"],
    explanation: "启发函数估计到目标的剩余代价。",
    difficulty: "easy"
  },
  {
    id: "q2",
    question_type: "multiple_choice",
    knowledge_point_id: "402",
    knowledge_point_title: "A* 搜索",
    prompt: "A* 评估函数包含哪些部分？",
    options: ["实际代价 g(n)", "估计代价 h(n)", "随机数"],
    correct_answer: null,
    keywords: ["g(n)", "h(n)"],
    explanation: "A* 使用 f(n)=g(n)+h(n)。",
    difficulty: "medium"
  },
  {
    id: "q3",
    question_type: "short_answer",
    knowledge_point_id: "402",
    knowledge_point_title: "A* 搜索",
    prompt: "说明 A* 为什么需要可采纳启发函数。",
    options: [],
    correct_answer: null,
    keywords: ["最优", "高估"],
    explanation: "可采纳启发函数不会高估剩余代价。",
    difficulty: "medium"
  }
] as const;

const inProgressSession = {
  id: "501",
  course_id: "808",
  title: "人工智能导论练习",
  status: "in_progress",
  score: null,
  grading_status: "ungraded",
  requested_difficulty: "adaptive",
  effective_difficulty: "easy",
  questions: questions.map((question) => ({ ...question })),
  answers: [],
  closure_update: null,
  created_at: "2026-07-05T10:00:00Z",
  updated_at: "2026-07-05T10:00:00Z"
};

const completedSession = {
  ...inProgressSession,
  targeted_weakness_id: "701",
  targeted_weakness_title: "启发式搜索",
  status: "completed",
  score: 66,
  grading_status: "complete",
  agent_trace_id: "trace_assessment",
  questions: [
    { ...questions[0], correct_answer: "估计剩余代价" },
    { ...questions[1], correct_answer: ["实际代价 g(n)", "估计代价 h(n)"] },
    { ...questions[2], correct_answer: "启发函数不能高估剩余代价" }
  ],
  answers: [
    {
      question_id: "q1",
      answer_text: "估计剩余代价",
      is_correct: true,
      feedback: { score: 100, message: "作答正确。", matched_keywords: ["估计"], missing_keywords: [], explanation: "已掌握启发函数作用。" }
    },
    {
      question_id: "q2",
      answer_text: "随机数",
      is_correct: false,
      feedback: {
        score: 0,
        message: "需要重新理解 A* 的评估函数。",
        matched_keywords: [],
        missing_keywords: ["g(n)", "h(n)"],
        explanation: "A* 使用实际代价和估计代价。",
        diagnosis: {
          misconception: "把评估函数误认为随机选择。",
          missing_concepts: ["实际代价", "估计代价"],
          recommended_action: "先复习 A* 评估函数，再完成一道同类题。",
          confidence: 0.9,
          evidence_ref: { type: "practice_answer", id: "602" }
        }
      }
    },
    {
      question_id: "q3",
      answer_text: "保证最优",
      is_correct: true,
      feedback: { score: 100, message: "核心方向正确。", matched_keywords: ["最优"], missing_keywords: [], explanation: "可采纳性保证最优性。" }
    }
  ],
  closure_update: {
    weaknesses_added: 1,
    weaknesses_updated: 0,
    path_update_status: "replanned",
    path_agent_trace_id: "trace_path_replan",
    recommended_resource_ids: ["801"],
    targeted_weakness_id: "701",
    targeted_weakness_status: "reviewing",
    targeted_weakness_improvement: 26,
    targeted_weakness_passed: false
  }
};

const resourceResponse = {
  data: [{
    id: "801",
    course_id: "808",
    knowledge_point_id: "402",
    resource_type: "doc",
    title: "A* 搜索针对性讲解",
    content_json: {},
    citation_json: [],
    status: "ready",
    review_status: "passed",
    confidence_score: 0.9,
    agent_trace_id: "trace_resource",
    created_at: "2026-07-05T10:00:00Z",
    updated_at: "2026-07-05T10:00:00Z"
  }],
  page: 1,
  page_size: 20,
  total: 1,
  trace_id: "trace_resources"
};

type AdapterOptions = {
  latest?: unknown;
  detail?: unknown;
  created?: unknown;
  submitted?: unknown;
  regraded?: unknown;
  failCreate?: boolean;
};

function installAdapter(options: AdapterOptions = {}) {
  const calls: Array<{ method: string; url: string; payload: unknown; params: unknown }> = [];
  apiClient.defaults.adapter = async (config) => {
    const method = (config.method ?? "get").toLowerCase();
    const url = config.url ?? "";
    const payload = parsePayload(config.data);
    calls.push({ method, url, payload, params: config.params });

    if (url === COURSE_ENDPOINTS.list) return { data: coursesResponse, status: 200, statusText: "OK", headers: {}, config };
    if (url === COURSE_ENDPOINTS.knowledgePoints(808)) return { data: pointsResponse, status: 200, statusText: "OK", headers: {}, config };
    if (url === RESOURCE_ENDPOINTS.list) return { data: resourceResponse, status: 200, statusText: "OK", headers: {}, config };
    if (url === PRACTICE_ENDPOINTS.latest) return { data: { data: options.latest ?? null }, status: 200, statusText: "OK", headers: {}, config };
    if (url === PRACTICE_ENDPOINTS.detail(501)) return { data: { data: options.detail ?? inProgressSession }, status: 200, statusText: "OK", headers: {}, config };
    if (url === AI_JOB_ENDPOINTS.practiceGeneration) {
      if (options.failCreate) throw new Error("practice failed");
      return {
        data: {
          data: {
            job_id: "practice-job-1",
            workflow: "practice_generation",
            status: "completed",
            course_id: "808",
            request: payload,
            result: { course_id: 808, session_id: 501, question_count: 3 },
            steps: [],
            warnings: []
          }
        },
        status: 202,
        statusText: "Accepted",
        headers: {},
        config
      };
    }
    if (url === PRACTICE_ENDPOINTS.answers(501)) return { data: { data: options.submitted ?? completedSession }, status: 200, statusText: "OK", headers: {}, config };
    if (url === PRACTICE_ENDPOINTS.regrade(501)) return { data: { data: options.regraded ?? completedSession }, status: 200, statusText: "OK", headers: {}, config };
    if (url === PRACTICE_ENDPOINTS.draft(501)) return { data: { data: options.detail ?? inProgressSession }, status: 200, statusText: "OK", headers: {}, config };
    if (url === AGENT_ENDPOINTS.trace("trace_assessment") || url === AGENT_ENDPOINTS.trace("trace_path_replan")) {
      return {
        data: {
          data: {
            trace_id: url.includes("path_replan") ? "trace_path_replan" : "trace_assessment",
            workflow: url.includes("path_replan") ? "path_planning" : "assessment",
            artifact_type: "practice_session",
            artifact_id: "501",
            course_id: "808",
            status: "completed",
            steps: [{ id: "1", agent_name: "diagnose_errors", step_index: 1, status: "completed", input_summary: "安全输入", output_summary: "已诊断", duration_ms: 12, metadata: {}, created_at: "2026-07-05T10:00:01Z" }]
          }
        },
        status: 200,
        statusText: "OK",
        headers: {},
        config
      };
    }
    throw new Error(`Unexpected request ${method} ${url}`);
  };
  return calls;
}

describe("PracticePage", () => {
  beforeEach(() => {
    previousAdapter = apiClient.defaults.adapter;
  });

  afterEach(() => {
    apiClient.defaults.adapter = previousAdapter;
  });

  it("does not restore an old completed practice when opening a targeted weakness retest", () => {
    const oldCompletedJob = {
      job_id: "old-practice-job",
      workflow: "practice_generation",
      status: "completed",
      course_id: "808",
      retry_of_job_id: null,
      progress_percent: 100,
      stage: "completed",
      label: "练习生成完成",
      request: { course_id: 808 },
      result: { course_id: 808, session_id: 501 },
      steps: [],
      warnings: [],
      agent_trace_id: "trace_old_practice",
      error_code: null,
      error_message: null,
      attempt_count: 1,
      can_cancel: false,
      can_retry: false,
      created_at: "2026-07-17T01:00:00Z",
      updated_at: "2026-07-17T01:00:10Z",
      started_at: "2026-07-17T01:00:01Z",
      completed_at: "2026-07-17T01:00:10Z"
    } satisfies AiJob;
    const targetedRunningJob = {
      ...oldCompletedJob,
      job_id: "targeted-practice-job",
      status: "running",
      request: { course_id: 808, weakness_item_id: 701 }
    } satisfies AiJob;

    expect(selectResumablePracticeJob([oldCompletedJob], 808, 701)).toBeUndefined();
    expect(selectResumablePracticeJob([oldCompletedJob, targetedRunningJob], 808, 701)?.job_id)
      .toBe("targeted-practice-job");
    expect(selectResumablePracticeJob([targetedRunningJob], 808, null)).toBeUndefined();
  });

  it("ignores a cached latest session while a new targeted weakness retest is requested", async () => {
    installAdapter();
    renderWithProviders(`${PATHS.practice}?course_id=808&knowledge_point_id=401&weakness_item_id=701&new=1`, true);

    expect(await screen.findByRole("heading", { name: "开始针对性练习" })).toBeInTheDocument();
    expect(screen.queryByText("本次得分")).not.toBeInTheDocument();
    expect(screen.getByTestId("location")).not.toHaveTextContent("session_id=501");
  });

  it("starts a targeted practice from the settings drawer and renders one question at a time", async () => {
    const user = userEvent.setup();
    const calls = installAdapter();
    renderWithProviders(`${PATHS.practice}?course_id=808&knowledge_point_id=401&weakness_item_id=701&new=1`);

    expect(await screen.findByRole("heading", { name: "开始针对性练习" })).toBeInTheDocument();
    expect(screen.getByText("启发式搜索")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "开始针对性练习" }));
    const drawer = screen.getByRole("dialog", { name: "练习设置" });
    expect(drawer.closest(".practice-focus-workspace")).toBeNull();
    expect(drawer).toHaveClass("practice-drawer-layer");
    expect(within(drawer).getByRole("button", { name: "5 题" })).toHaveAttribute("aria-pressed", "true");
    expect(within(drawer).getByRole("button", { name: /智能适配/ })).toHaveAttribute("aria-pressed", "true");
    await user.click(within(drawer).getByRole("button", { name: "开始针对性练习" }));

    expect(await screen.findByRole("heading", { name: "启发函数的主要作用是什么？" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "A* 评估函数包含哪些部分？" })).not.toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByTestId("location")).toHaveTextContent("session_id=501");
      expect(screen.getByTestId("location")).toHaveTextContent("question_id=q1");
    });
    expect(calls).toContainEqual(expect.objectContaining({
      method: "post",
      url: AI_JOB_ENDPOINTS.practiceGeneration,
      payload: { course_id: 808, knowledge_point_ids: [401], weakness_item_id: 701, question_count: 5, difficulty: "adaptive" }
    }));
  });

  it("navigates questions, restores draft choice state and keeps the selected question in the URL", async () => {
    const user = userEvent.setup();
    installAdapter({
      detail: {
        ...inProgressSession,
        draft_saved_at: "2026-07-05T10:01:00Z",
        answers: [{
          question_id: "q2",
          answer_text: "实际代价 g(n), 估计代价 h(n)",
          is_correct: null,
          feedback: { score: 0, message: "", matched_keywords: [], missing_keywords: [], explanation: "" }
        }]
      }
    });
    renderWithProviders(`${PATHS.practice}?course_id=808&session_id=501&question_id=q2`);

    expect(await screen.findByRole("heading", { name: "A* 评估函数包含哪些部分？" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /实际代价 g\(n\)/ })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: /估计代价 h\(n\)/ })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("progressbar", { name: "已回答 1 题，共 3 题" })).toHaveAttribute("value", "1");
    await user.click(screen.getByRole("button", { name: "了解智能适配依据" }));
    expect(await screen.findByText("根据当前掌握度、已确认薄弱点和最近练习结果调整。")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "第 3 题，未答" }));
    expect(await screen.findByRole("heading", { name: "说明 A* 为什么需要可采纳启发函数。" })).toBeInTheDocument();
    expect(screen.getByTestId("location")).toHaveTextContent("question_id=q3");
  });

  it("stores multiple-choice selections without confusing punctuation inside an option", async () => {
    const user = userEvent.setup();
    const calls = installAdapter();
    renderWithProviders(`${PATHS.practice}?course_id=808&session_id=501&question_id=q2`);

    await user.click(await screen.findByRole("button", { name: /实际代价 g\(n\)/ }));
    await user.click(screen.getByRole("button", { name: /估计代价 h\(n\)/ }));

    expect(screen.getByRole("button", { name: /实际代价 g\(n\)/ })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: /估计代价 h\(n\)/ })).toHaveAttribute("aria-pressed", "true");
    await waitFor(() => {
      expect(calls).toContainEqual(expect.objectContaining({
        method: "patch",
        url: PRACTICE_ENDPOINTS.draft(501),
        payload: {
          revision: 1,
          answers: expect.arrayContaining([
            { question_id: "q2", answer_text: JSON.stringify(["实际代价 g(n)", "估计代价 h(n)"]) }
          ])
        }
      }));
    });
  });

  it("confirms incomplete submission and moves back to the first unanswered question when cancelled", async () => {
    const user = userEvent.setup();
    const calls = installAdapter();
    renderWithProviders(`${PATHS.practice}?course_id=808&session_id=501&question_id=q1`);

    await user.click(await screen.findByRole("button", { name: /估计剩余代价/ }));
    await user.click(screen.getByRole("button", { name: "提交练习" }));
    const confirm = screen.getByRole("alertdialog", { name: "还有 2 题未作答" });
    await user.click(within(confirm).getByRole("button", { name: "返回未答题" }));
    expect(await screen.findByRole("heading", { name: "A* 评估函数包含哪些部分？" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "提交练习" }));
    await user.click(screen.getByRole("button", { name: "仍然提交" }));
    expect(await screen.findByRole("region", { name: "练习结果摘要" })).toBeInTheDocument();
    expect(calls).toContainEqual(expect.objectContaining({
      method: "post",
      url: PRACTICE_ENDPOINTS.answers(501),
      payload: {
        answers: [
          { question_id: "q1", answer_text: "估计剩余代价", answered: true },
          { question_id: "q2", answer_text: "", answered: false },
          { question_id: "q3", answer_text: "", answered: false }
        ]
      }
    }));
  });

  it("shows completed results, expands wrong diagnosis and resolves recommended resources", async () => {
    const user = userEvent.setup();
    installAdapter({ detail: completedSession });
    renderWithProviders(`${PATHS.practice}?course_id=808&session_id=501&question_id=q2&knowledge_point_id=402&return_to=course&course_session_id=77&course_message_id=88`);

    const summary = await screen.findByRole("region", { name: "练习结果摘要" });
    expect(within(summary).getByText("66")).toBeInTheDocument();
    expect(summary.querySelector(".practice-result-ring-value")).toBeInTheDocument();
    expect(within(summary).getByText("答对 2 / 3")).toBeInTheDocument();
    expect(within(summary).getByRole("button", { name: "开始新练习" })).toBeInTheDocument();
    expect(screen.getByText("把评估函数误认为随机选择。")).toBeInTheDocument();
    expect(screen.getByText("实际代价")).toBeInTheDocument();
    const wrongReview = screen.getByRole("region", { name: "q2 批改结果" });
    expect(within(wrongReview).getByText("正确答案")).toBeInTheDocument();
    expect(within(wrongReview).getByText("实际代价 g(n)、估计代价 h(n)")).toBeInTheDocument();
    expect(within(screen.getByRole("group", { name: "答案选项" })).getByRole("button", { name: /随机数/ })).toHaveClass("wrong");
    expect(within(screen.getByRole("group", { name: "答案选项" })).getByRole("button", { name: /实际代价 g\(n\)/ })).toHaveClass("correct");

    await user.click(screen.getByRole("button", { name: "第 1 题，正确" }));
    const correctChoice = within(screen.getByRole("group", { name: "答案选项" })).getByRole("button", { name: /估计剩余代价/ });
    expect(correctChoice).toHaveClass("correct");
    expect(correctChoice).not.toHaveClass("wrong");

    await user.click(within(summary).getByRole("button", { name: "查看学习更新" }));
    const drawer = screen.getByRole("dialog", { name: "学习结果" });
    expect(within(drawer).getByText("“启发式搜索”仍需复习")).toBeInTheDocument();
    expect(drawer).toHaveTextContent(/较起点\s*提升\s*26\s*分/);
    expect(within(drawer).getByText("A* 搜索针对性讲解")).toBeInTheDocument();
    await user.click(within(drawer).getByRole("button", { name: "查看 AssessmentGraph" }));
    expect(await within(drawer).findByText("diagnose_errors")).toBeInTheDocument();
    await user.click(within(drawer).getByRole("button", { name: "关闭学习结果" }));
    expect(screen.getByRole("link", { name: "返回课程空间" })).toHaveAttribute(
      "href",
      "/app/courses/808?course_session_id=77&course_message_id=88&knowledge_point_id=402"
    );
  });

  it("shows ungraded short answers without a red error state and can retry grading", async () => {
    const user = userEvent.setup();
    const partialSession = {
      ...completedSession,
      score: 50,
      grading_status: "partial",
      answers: completedSession.answers.map((answer) => answer.question_id === "q3" ? {
        ...answer,
        is_correct: null,
        feedback: {
          score: null,
          grading_status: "ungraded",
          message: "简答题暂未评分，可稍后重试。",
          matched_concepts: [],
          missing_concepts: [],
          confidence: null,
          matched_keywords: [],
          missing_keywords: [],
          explanation: answer.feedback.explanation
        }
      } : answer)
    };
    const calls = installAdapter({ detail: partialSession, regraded: completedSession });
    renderWithProviders(`${PATHS.practice}?course_id=808&session_id=501&question_id=q3`);

    const summary = await screen.findByRole("region", { name: "练习结果摘要" });
    expect(within(summary).getByText("部分评分")).toBeInTheDocument();
    expect(within(summary).getByText("已评分 2 / 3")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "q3 批改结果" })).toHaveClass("pending");
    expect(screen.getByText("简答题暂未评分")).toBeInTheDocument();
    await user.click(within(summary).getByRole("button", { name: "重试简答题评分" }));
    await waitFor(() => expect(within(summary).queryByRole("button", { name: "重试简答题评分" })).not.toBeInTheDocument());
    expect(calls).toContainEqual(expect.objectContaining({ method: "post", url: PRACTICE_ENDPOINTS.regrade(501) }));
  });

  it("does not display a zero score when every answer is ungraded", async () => {
    const ungradedSession = {
      ...completedSession,
      score: null,
      grading_status: "ungraded",
      answers: completedSession.answers.map((answer) => ({
        ...answer,
        is_correct: null,
        feedback: {
          ...answer.feedback,
          score: null,
          grading_status: "ungraded",
          message: "简答题暂未评分，可稍后重试。"
        }
      }))
    };
    installAdapter({ detail: ungradedSession });
    renderWithProviders(`${PATHS.practice}?course_id=808&session_id=501&question_id=q1`);

    expect((await screen.findAllByText("暂未评分")).length).toBeGreaterThan(0);
    const summary = screen.getByRole("region", { name: "练习结果摘要" });
    expect(within(summary).getByText("已评分 0 / 3")).toBeInTheDocument();
    expect(summary.querySelector(".practice-result-score")).toHaveClass("ungraded");
    expect(summary.querySelector(".practice-result-ring-value")).not.toBeInTheDocument();
    expect(screen.queryByText("得分 0")).not.toBeInTheDocument();
  });

  it("keeps settings and return context when generation fails", async () => {
    const user = userEvent.setup();
    installAdapter({ failCreate: true });
    renderWithProviders(`${PATHS.practice}?course_id=808&knowledge_point_id=401&new=1&return_to=course&course_session_id=77&course_message_id=88`);

    await user.click(await screen.findByRole("button", { name: "开始针对性练习" }));
    const drawer = screen.getByRole("dialog", { name: "练习设置" });
    await user.click(within(drawer).getByRole("button", { name: "开始针对性练习" }));
    expect(await within(drawer).findByText("练习任务创建失败，请稍后重试。")).toBeInTheDocument();
    expect(screen.getByTestId("location")).toHaveTextContent("course_session_id=77");
    expect(screen.getByTestId("location")).toHaveTextContent("course_message_id=88");
  });
});

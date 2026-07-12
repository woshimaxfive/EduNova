export type StudyStepKey =
  | "profile"
  | "retrieval"
  | "tutor"
  | "weakness"
  | "resource"
  | "path"
  | "assessment"
  | "report";

export type StudyStepStatus = "done" | "ready" | "next" | "empty";

export type CourseLoopInput = {
  courseTitle: string;
  materialCount: number;
  knowledgePointCount: number;
  progressPercent: number;
  latestQuestion: string | null;
  citationCount: number;
  pendingWeaknessCount: number;
  confirmedWeaknessCount: number;
  resourceCount: number;
  hasActivePath: boolean;
  latestTraceWorkflow: string | null;
  latestTraceId: string | null;
  hasLatestReport: boolean;
  hasProfileEvidence: boolean;
  hasCompletedPractice: boolean;
  recommendedGoal: string;
  recommendedAction: string;
};

export type CourseLoopSummary = {
  title: string;
  currentGoal: string;
  evidenceLine: string;
  nextAction: string;
  progressLabel: string;
  traceLabel: string | null;
};

export type StudyStep = {
  key: StudyStepKey;
  label: string;
  description: string;
  status: StudyStepStatus;
};

export function calculateMasteryPercent(points: Array<{ score: number }>) {
  if (points.length === 0) return 0;

  const total = points.reduce((sum, point) => {
    const score = Number.isFinite(point.score) ? point.score : 0;
    return sum + Math.min(100, Math.max(0, score));
  }, 0);

  return Math.min(100, Math.max(0, Math.round(total / points.length)));
}

export function buildCourseLoopSummary(input: CourseLoopInput): CourseLoopSummary {
  const traceLabel =
    input.latestTraceWorkflow && input.latestTraceId ? `${input.latestTraceWorkflow} · ${input.latestTraceId}` : null;

  return {
    title: input.courseTitle,
    currentGoal: input.recommendedGoal,
    evidenceLine: `${input.materialCount} 份资料 · ${input.knowledgePointCount} 个知识点 · ${input.citationCount} 条引用 · ${input.resourceCount} 个资源`,
    nextAction: input.recommendedAction,
    progressLabel: `${input.progressPercent}%`,
    traceLabel
  };
}

export function buildStudySteps(input: CourseLoopInput): StudyStep[] {
  const hasRetrieval = input.citationCount > 0;
  const hasTutor = Boolean(input.latestQuestion?.trim());
  const totalWeaknessCount = input.pendingWeaknessCount + input.confirmedWeaknessCount;
  const hasWeakness = totalWeaknessCount > 0;
  const hasResources = input.resourceCount > 0;

  return [
    {
      key: "profile",
      label: "画像",
      description: "用学生目标、历史和偏好确定课程目标",
      status: input.hasProfileEvidence ? "done" : "ready"
    },
    {
      key: "retrieval",
      label: "检索",
      description: hasRetrieval ? `找到 ${input.citationCount} 条课程依据` : "等待课程提问或知识点选择",
      status: hasRetrieval ? "done" : "ready"
    },
    {
      key: "tutor",
      label: "辅导",
      description: hasTutor ? "已围绕当前问题生成课程回答" : "等待学生发起课程问题",
      status: hasTutor ? "done" : "ready"
    },
    {
      key: "weakness",
      label: "弱点",
      description: hasWeakness ? `${totalWeaknessCount} 个弱点等待处理` : "等待练习或问答沉淀弱点",
      status: hasWeakness ? "ready" : "empty"
    },
    {
      key: "resource",
      label: "资源",
      description: hasResources ? `已有 ${input.resourceCount} 个个性化资源` : "可生成讲解、思维导图、练习、拓展和代码资源",
      status: hasResources ? "ready" : hasWeakness || hasRetrieval ? "next" : "empty"
    },
    {
      key: "path",
      label: "路径",
      description: input.hasActivePath ? "已有学习路径，可继续推进" : "可根据资料、弱点和资源生成路径",
      status: input.hasActivePath ? "ready" : hasResources ? "next" : "empty"
    },
    {
      key: "assessment",
      label: "评估",
      description: input.hasCompletedPractice ? "最近练习已更新掌握度和复习队列" : "用练习结果更新掌握度和复习队列",
      status: input.hasCompletedPractice ? "done" : input.hasActivePath || hasResources ? "next" : "empty"
    },
    {
      key: "report",
      label: "报告",
      description: input.hasLatestReport ? "已有学习报告证据" : "完成练习后生成阶段报告",
      status: input.hasLatestReport ? "ready" : "empty"
    }
  ];
}

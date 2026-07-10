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

export function buildCourseLoopSummary(input: CourseLoopInput): CourseLoopSummary {
  const totalWeaknessCount = input.pendingWeaknessCount + input.confirmedWeaknessCount;
  const hasWeakness = totalWeaknessCount > 0;
  const hasQuestion = Boolean(input.latestQuestion?.trim());
  const hasGeneratedEvidence = input.citationCount > 0 || input.resourceCount > 0 || input.hasActivePath;
  const currentGoal =
    hasQuestion && hasWeakness
      ? `围绕最新问题处理 ${totalWeaknessCount} 个待处理弱点`
      : hasQuestion
        ? "围绕最新问题建立资料依据和下一步行动"
        : hasGeneratedEvidence
          ? "根据课程证据推进下一步个性化学习"
          : "从课程资料和知识点开始建立学习闭环";
  const nextAction = hasWeakness
    ? "先确认薄弱点，再生成针对性资源并进入路径任务"
    : input.hasActivePath
      ? "继续完成路径任务，并用练习结果更新掌握度"
      : input.resourceCount > 0
        ? "基于已生成资源进入路径或练习，形成评估回流"
        : input.citationCount > 0
          ? "基于当前引用生成 6 类资源，或直接进入练习"
          : "先提问或选择知识点，生成第一批个性化学习依据";
  const traceLabel =
    input.latestTraceWorkflow && input.latestTraceId ? `${input.latestTraceWorkflow} · ${input.latestTraceId}` : null;

  return {
    title: input.courseTitle,
    currentGoal,
    evidenceLine: `${input.materialCount} 份资料 · ${input.knowledgePointCount} 个知识点 · ${input.citationCount} 条引用 · ${input.resourceCount} 个资源`,
    nextAction,
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
      status: "done"
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
      description: "用练习结果更新掌握度和复习队列",
      status: input.hasActivePath || hasResources ? "next" : "empty"
    },
    {
      key: "report",
      label: "报告",
      description: input.hasLatestReport ? "已有学习报告证据" : "完成练习后生成阶段报告",
      status: input.hasLatestReport ? "ready" : "empty"
    }
  ];
}

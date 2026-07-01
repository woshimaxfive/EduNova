import {
  type MaterialProgressStatus,
  type WorkflowStage,
  type WorkspaceStatePanel
} from "../../types/api";

type WorkflowDefinition = {
  id: Exclude<MaterialProgressStatus, "failed">;
  label: string;
  message: string;
};

export const WORKFLOW_STAGE_ORDER = [
  "uploaded",
  "parsing",
  "building_course",
  "chunking",
  "embedding",
  "path_generating",
  "completed"
] as const satisfies ReadonlyArray<Exclude<MaterialProgressStatus, "failed">>;

const workflowDefinitions: WorkflowDefinition[] = [
  {
    id: "uploaded",
    label: "资料入库",
    message: "文件已进入个人资料库"
  },
  {
    id: "parsing",
    label: "解析内容",
    message: "正在提取文本、章节和基础结构"
  },
  {
    id: "building_course",
    label: "生成课程",
    message: "正在抽取章节、知识点和先修关系"
  },
  {
    id: "chunking",
    label: "切分知识片段",
    message: "正在切分知识片段"
  },
  {
    id: "embedding",
    label: "写入索引",
    message: "正在写入向量索引并绑定引用"
  },
  {
    id: "path_generating",
    label: "规划路径",
    message: "正在生成初始学习路径"
  },
  {
    id: "completed",
    label: "进入画布",
    message: "课程已进入学习画布"
  }
];

const workspaceStatePanels: WorkspaceStatePanel[] = [
  {
    kind: "empty",
    title: "空状态",
    description: "还没有课程上下文时，学生可以从内置课程、上传资料或画像对话开始。",
    actionLabel: "选择开始方式"
  },
  {
    kind: "loading",
    title: "加载状态",
    description: "长任务显示具体阶段和进度，避免学生面对普通转圈等待。",
    actionLabel: "查看进度"
  },
  {
    kind: "error",
    title: "错误恢复",
    description: "上传或生成失败时保留原因摘要，并给出重试、换格式或稍后再试。",
    actionLabel: "恢复任务"
  },
  {
    kind: "low_evidence",
    title: "低依据提示",
    description: "资料不足时明确标记低依据，不把扩展内容伪装成课程结论。",
    actionLabel: "补充资料"
  },
  {
    kind: "demo_fallback",
    title: "演示兜底内容",
    description: "演示数据和 fallback 输出必须标记来源，保证比赛演示可复现。",
    actionLabel: "查看标记"
  }
];

function clampProgress(progressPercent: number) {
  return Math.min(100, Math.max(0, progressPercent));
}

export function buildMaterialLifecycle(
  currentStatus: MaterialProgressStatus,
  progressPercent = 0
): WorkflowStage[] {
  const safeProgress = clampProgress(progressPercent);

  if (currentStatus === "failed") {
    return [
      ...workflowDefinitions.map<WorkflowStage>((definition, index) => ({
        ...definition,
        status: index === 0 ? "completed" : "queued",
        progressPercent: index === 0 ? 100 : 0
      })),
      {
        id: "failed",
        label: "处理失败",
        message: "资料处理没有完成，失败记录已保留",
        status: "failed",
        progressPercent: safeProgress,
        nextAction: "重新上传，或换成文本版资料"
      }
    ];
  }

  const activeIndex = WORKFLOW_STAGE_ORDER.indexOf(currentStatus);

  return workflowDefinitions.map<WorkflowStage>((definition, index) => {
    if (currentStatus === "completed" || index < activeIndex) {
      return {
        ...definition,
        status: "completed",
        progressPercent: 100
      };
    }

    if (index === activeIndex) {
      return {
        ...definition,
        status: "active",
        progressPercent: currentStatus === "uploaded" ? Math.max(15, safeProgress) : safeProgress
      };
    }

    return {
      ...definition,
      status: "queued",
      progressPercent: 0
    };
  });
}

export function getWorkspaceStatePanels() {
  return workspaceStatePanels;
}

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
  "pending",
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
    id: "pending",
    label: "等待处理",
    message: "资料任务已创建，正在等待处理"
  },
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
    description: "从课程、资料或画像开始。",
    actionLabel: "选择开始方式"
  },
  {
    kind: "loading",
    title: "加载状态",
    description: "显示阶段和进度。",
    actionLabel: "查看进度"
  },
  {
    kind: "error",
    title: "错误恢复",
    description: "保留原因并给出下一步。",
    actionLabel: "恢复任务"
  },
  {
    kind: "low_evidence",
    title: "低依据提示",
    description: "资料不足时明确标记。",
    actionLabel: "补充资料"
  },
  {
    kind: "local_preview",
    title: "本地预备反馈",
    description: "未接真实能力时只给出短反馈。",
    actionLabel: "查看边界"
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
        progressPercent: currentStatus === "pending" || currentStatus === "uploaded" ? Math.max(15, safeProgress) : safeProgress
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

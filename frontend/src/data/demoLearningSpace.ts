import { type LearningSpaceSnapshot } from "../types/api";

export const demoLearningSpace: LearningSpaceSnapshot = {
  currentCourse: {
    id: 1,
    title: "人工智能导论",
    description: "从搜索、知识表示、机器学习到智能体安全的课程样例。",
    subject: "人工智能",
    sourceType: "builtin",
    progressPercent: 32
  },
  materials: [
    {
      id: 1,
      title: "AI 导论内置讲义",
      type: "builtin",
      parseStatus: "completed",
      coverageLabel: "12 个知识点"
    },
    {
      id: 2,
      title: "期末复习题样例",
      type: "markdown",
      parseStatus: "completed",
      coverageLabel: "24 道练习"
    }
  ],
  knowledgeNodes: [
    { id: "overview", title: "人工智能概述", chapter: "绪论", status: "mastered", x: 10, y: 44 },
    { id: "search", title: "启发式搜索", chapter: "搜索", status: "learning", x: 28, y: 20 },
    { id: "knowledge", title: "知识表示", chapter: "推理", status: "ready", x: 47, y: 50 },
    { id: "ml", title: "监督学习", chapter: "机器学习", status: "focus", x: 65, y: 26 },
    { id: "nn", title: "神经网络", chapter: "深度学习", status: "weak", x: 82, y: 58 }
  ],
  todayTasks: [
    { id: 1, title: "补齐监督学习核心概念", type: "read", status: "doing" },
    { id: 2, title: "生成反向传播错题讲解", type: "generate", status: "todo" },
    { id: 3, title: "完成 8 道期末题", type: "practice", status: "todo" }
  ],
  studioOutputs: [
    { id: 1, title: "监督学习个性化讲解", resourceType: "讲解", reviewStatus: "可使用" },
    { id: 2, title: "反向传播薄弱点练习", resourceType: "练习", reviewStatus: "审核中" },
    { id: 3, title: "神经网络知识图谱", resourceType: "思维导图", reviewStatus: "待生成" },
    { id: 4, title: "Python 代码实操案例", resourceType: "代码实操", reviewStatus: "低依据" },
    { id: 5, title: "期末冲刺讲稿", resourceType: "PPT 大纲", reviewStatus: "待生成" }
  ],
  citations: [
    {
      id: "c1",
      sourceTitle: "AI 导论内置讲义",
      sectionTitle: "监督学习与泛化",
      pageNumber: 6,
      confidence: "high"
    },
    {
      id: "c2",
      sourceTitle: "期末复习题样例",
      sectionTitle: "反向传播常见错误",
      pageNumber: 2,
      confidence: "medium"
    }
  ],
  agentTrace: [
    {
      id: "a1",
      agentName: "ProfileAgent",
      summary: "读取学习画像和近期错因",
      status: "completed",
      durationMs: 92
    },
    {
      id: "a2",
      agentName: "RetrieverAgent",
      summary: "检索课程切片并绑定引用",
      status: "completed",
      durationMs: 168
    },
    {
      id: "a3",
      agentName: "ReviewAgent",
      summary: "检查依据强度和难度匹配",
      status: "warning",
      durationMs: 121
    }
  ]
};

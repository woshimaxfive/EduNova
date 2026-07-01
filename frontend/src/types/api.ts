export type ApiUser = {
  id: number;
  email: string;
  display_name: string;
  role: "student" | "admin";
};

export type CourseSummary = {
  id: number;
  title: string;
  description: string;
  subject: string;
  sourceType: "builtin" | "uploaded" | "demo_fallback";
  progressPercent: number;
};

export type MaterialSource = {
  id: number;
  title: string;
  type: "pdf" | "pptx" | "docx" | "markdown" | "txt" | "builtin";
  parseStatus: "uploaded" | "parsing" | "chunking" | "embedding" | "completed" | "failed";
  coverageLabel: string;
};

export type KnowledgeNode = {
  id: string;
  title: string;
  chapter: string;
  status: "focus" | "learning" | "weak" | "ready" | "mastered";
  x: number;
  y: number;
};

export type LearningTask = {
  id: number;
  title: string;
  type: "read" | "practice" | "review" | "generate";
  status: "todo" | "doing" | "done";
};

export type StudioOutput = {
  id: number;
  title: string;
  resourceType: "讲解" | "练习" | "思维导图" | "复盘报告" | "PPT 大纲";
  reviewStatus: "待生成" | "审核中" | "可使用" | "低依据";
};

export type CitationRef = {
  id: string;
  sourceTitle: string;
  sectionTitle: string;
  pageNumber?: number;
  confidence: "high" | "medium" | "low";
};

export type AgentTraceEvent = {
  id: string;
  agentName: string;
  summary: string;
  status: "pending" | "running" | "completed" | "warning";
  durationMs?: number;
};

export type LearningSpaceSnapshot = {
  currentCourse: CourseSummary;
  materials: MaterialSource[];
  knowledgeNodes: KnowledgeNode[];
  todayTasks: LearningTask[];
  studioOutputs: StudioOutput[];
  citations: CitationRef[];
  agentTrace: AgentTraceEvent[];
};

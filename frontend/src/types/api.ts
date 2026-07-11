export type ApiUser = {
  id: number;
  email: string;
  display_name: string;
  role: "student" | "admin";
  starter_mode: "blank" | "ai_intro";
};

export type ApiEnvelope<T> = {
  data: T;
  trace_id: string;
};

export type ApiListEnvelope<T> = {
  data: T[];
  page: number;
  page_size: number;
  total: number;
  trace_id: string;
};

export type CourseSummary = {
  id: number;
  title: string;
  description: string;
  subject: string;
  sourceType: "builtin" | "uploaded" | "generated";
  progressPercent: number;
};

export type MaterialSource = {
  id: number;
  title: string;
  type: "pdf" | "pptx" | "docx" | "markdown" | "txt" | "builtin";
  parseStatus: MaterialProgressStatus;
  coverageLabel: string;
};

export type MaterialProgressStatus =
  | "uploaded"
  | "parsing"
  | "building_course"
  | "chunking"
  | "embedding"
  | "path_generating"
  | "completed"
  | "failed";

export type WorkflowStageStatus = "completed" | "active" | "queued" | "failed";

export type WorkflowStage = {
  id: MaterialProgressStatus;
  label: string;
  message: string;
  status: WorkflowStageStatus;
  progressPercent: number;
  nextAction?: string;
};

export type WorkspacePanelKind = "empty" | "loading" | "error" | "low_evidence" | "local_preview";

export type WorkspaceStatePanel = {
  kind: WorkspacePanelKind;
  title: string;
  description: string;
  actionLabel: string;
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
  resourceType: "讲解" | "练习" | "思维导图" | "代码实操" | "PPT" | "动画图解";
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
  contextMessageCount?: number;
  contextSummaryUsed?: boolean;
  retrievalQueryMode?: "direct" | "contextual";
  modelCallCount?: number;
  modelRetryCount?: number;
  modelLatencyMs?: number;
  modelOutcome?: string;
  modelErrorCategory?: string;
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

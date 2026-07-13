import type { ProfileEventResponse, ProfileJson, StudentProfileResponse } from "../../api/profiles";

export type ProfileDimensionKey = keyof ProfileJson;

export type ProfileDimensionMeta = {
  key: ProfileDimensionKey;
  label: string;
  shortLabel: string;
  description: string;
  guidance: string;
  examples: string;
  legacyLabels: string[];
};

export type ProfileDimensionView = ProfileDimensionMeta & {
  value: string;
  confidence: number;
  appliedCount: number;
  candidateCount: number;
};

export type ProfileEventView = {
  event: ProfileEventResponse;
  dimensions: ProfileDimensionKey[];
  appliedDimensions: ProfileDimensionKey[];
  candidateDimensions: ProfileDimensionKey[];
  sourceLabel: string;
  status: "applied" | "candidate" | "mixed";
  statusLabel: string;
  confidencePercent: number | null;
  generationMode: "model_enhanced" | "rules_only" | "unknown";
  generationModeLabel: string;
  parseStatus: string | null;
  repairCount: number;
  reviewMode: string | null;
};

export type ProfileUpdateReceipt = {
  appliedDimensions: ProfileDimensionKey[];
  candidateDimensions: ProfileDimensionKey[];
  changedDimensions: ProfileDimensionKey[];
};

export const PROFILE_DIMENSIONS: ProfileDimensionMeta[] = [
  {
    key: "major_background",
    label: "学习背景",
    shortLabel: "背景",
    description: "你目前在学什么，以及接触过哪些相关内容",
    guidance: "说说你目前所学的方向、阶段或相关经历。",
    examples: "所学专业、当前阶段、自学经历或做过的相关项目。",
    legacyLabels: ["专业背景"]
  },
  {
    key: "knowledge_foundation",
    label: "已有基础",
    shortLabel: "基础",
    description: "你已经掌握的知识、概念和工具",
    guidance: "说说你已经会什么，以及目前熟悉到什么程度。",
    examples: "学过的课程、掌握的工具、了解的概念，或者目前刚入门。",
    legacyLabels: ["知识基础"]
  },
  {
    key: "learning_goal",
    label: "学习目标",
    shortLabel: "目标",
    description: "你接下来希望学会、完成或解决的事情",
    guidance: "说说你现阶段最想达到什么结果。",
    examples: "想掌握的知识、想完成的项目、职业或考试目标。",
    legacyLabels: ["学习目标"]
  },
  {
    key: "cognitive_style",
    label: "理解习惯",
    shortLabel: "理解",
    description: "你通常怎样把陌生内容弄懂并整理清楚",
    guidance: "说说面对新知识时，你通常会先做什么、怎样逐步理解。",
    examples: "先看整体框架、逐步推导、通过类比理解，或者边做边总结。",
    legacyLabels: ["认知风格"]
  },
  {
    key: "learning_preference",
    label: "学习方式",
    shortLabel: "方式",
    description: "你更愿意使用的内容和练习形式",
    guidance: "说说什么样的讲解和练习方式更适合你。",
    examples: "图解、案例、视频、代码实操、练习题或阅读讲解。",
    legacyLabels: ["学习偏好"]
  },
  {
    key: "weak_points",
    label: "学习难点",
    shortLabel: "难点",
    description: "你目前难理解、容易出错或经常卡住的内容",
    guidance: "说说哪些内容正在影响你的理解或做题。",
    examples: "难理解的概念、不会应用的公式、经常做错的题型。",
    legacyLabels: ["薄弱点"]
  },
  {
    key: "learning_pace",
    label: "学习节奏",
    shortLabel: "节奏",
    description: "你能投入的时间和习惯的学习频率",
    guidance: "说说你通常能安排多少时间，以及喜欢怎样分配。",
    examples: "每天学习多久、每周学习几次，或者集中学习还是少量多次。",
    legacyLabels: ["学习节奏"]
  },
  {
    key: "motivation_interest",
    label: "学习动力",
    shortLabel: "动力",
    description: "你为什么想学，以及真正感兴趣的方向",
    guidance: "说说促使你学习的原因、期待或感兴趣的方向。",
    examples: "感兴趣的领域、未来想从事的工作、想解决的问题或希望作出的贡献。",
    legacyLabels: ["动机兴趣", "学习动机"]
  }
];

const dimensionKeySet = new Set<ProfileDimensionKey>(PROFILE_DIMENSIONS.map((item) => item.key));

export function isProfileDimensionKey(value: unknown): value is ProfileDimensionKey {
  return typeof value === "string" && dimensionKeySet.has(value as ProfileDimensionKey);
}

export function profileDimensionMeta(key: ProfileDimensionKey) {
  return PROFILE_DIMENSIONS.find((item) => item.key === key) ?? PROFILE_DIMENSIONS[0];
}

export function profileQuestionGuidance(key: unknown) {
  return isProfileDimensionKey(key)
    ? profileDimensionMeta(key)
    : null;
}

export function profileValue(profile: StudentProfileResponse, key: ProfileDimensionKey) {
  const value = profile.profile_json[key];
  if (Array.isArray(value)) return value.length > 0 ? value.join("、") : "等待有效证据";
  return value.trim() || "等待有效证据";
}

export function profileSourceLabel(sourceType?: string) {
  if (sourceType === "profile_chat") return "主动回答";
  if (sourceType === "practice_assessment") return "练习诊断";
  if (sourceType === "course_question") return "课程问答";
  if (sourceType === "learning_signal") return "学习行为";
  return "学习证据";
}

function safeDimensionList(value: unknown) {
  if (!Array.isArray(value)) return [];
  return value.filter(isProfileDimensionKey);
}

function legacyDimensions(event: ProfileEventResponse) {
  if (isProfileDimensionKey(event.dimension)) return [event.dimension];
  return PROFILE_DIMENSIONS
    .filter((item) => (
      event.change_summary.includes(item.label)
      || event.change_summary.includes(item.shortLabel)
      || item.legacyLabels.some((label) => event.change_summary.includes(label))
    ))
    .map((item) => item.key);
}

export function buildProfileEventView(event: ProfileEventResponse): ProfileEventView {
  const evidenceSourceType = typeof event.evidence_json.source_type === "string"
    ? event.evidence_json.source_type
    : undefined;
  const appliedDimensions = safeDimensionList(event.evidence_json.updated_dimensions);
  const candidateDimensions = safeDimensionList(event.evidence_json.candidate_dimensions)
    .filter((key) => !appliedDimensions.includes(key));
  const fallbackDimensions = appliedDimensions.length === 0 && candidateDimensions.length === 0
    ? legacyDimensions(event)
    : [];
  const eventIsCandidate = event.status === "candidate";
  const generationMode = event.evidence_json.generation_mode === "model_enhanced"
    ? "model_enhanced"
    : event.evidence_json.generation_mode === "rules_only"
      ? "rules_only"
      : "unknown";
  const resolvedApplied = eventIsCandidate ? [] : [...appliedDimensions, ...fallbackDimensions];
  const resolvedCandidate = eventIsCandidate ? [...candidateDimensions, ...fallbackDimensions] : candidateDimensions;
  const dimensions = Array.from(new Set([...resolvedApplied, ...resolvedCandidate]));
  const status = resolvedApplied.length > 0 && resolvedCandidate.length > 0
    ? "mixed"
    : resolvedApplied.length > 0
      ? "applied"
      : "candidate";
  return {
    event,
    dimensions,
    appliedDimensions: resolvedApplied,
    candidateDimensions: resolvedCandidate,
    sourceLabel: profileSourceLabel(event.source_type || evidenceSourceType),
    status,
    statusLabel: status === "mixed" ? "部分已应用" : status === "applied" ? "已应用" : "候选证据",
    confidencePercent: typeof event.confidence_score === "number"
      ? Math.round(Math.max(0, Math.min(1, event.confidence_score)) * 100)
      : null,
    generationMode,
    generationModeLabel: generationMode === "model_enhanced"
      ? "模型增强"
      : generationMode === "rules_only"
        ? "规则提取"
        : "历史记录",
    parseStatus: typeof event.evidence_json.parse_status === "string" ? event.evidence_json.parse_status : null,
    repairCount: typeof event.evidence_json.repair_count === "number"
      ? Math.max(0, Math.round(event.evidence_json.repair_count))
      : 0,
    reviewMode: typeof event.evidence_json.review_mode === "string" ? event.evidence_json.review_mode : null
  };
}

export function buildProfileDimensions(profile: StudentProfileResponse, events: ProfileEventResponse[]): ProfileDimensionView[] {
  const eventViews = events.map(buildProfileEventView);
  return PROFILE_DIMENSIONS.map((item) => ({
    ...item,
    value: profileValue(profile, item.key),
    confidence: Math.round(Math.max(0, Math.min(100, profile.dimension_confidence?.[item.key] ?? 0))),
    appliedCount: eventViews.filter((event) => event.appliedDimensions.includes(item.key)).length,
    candidateCount: eventViews.filter((event) => event.candidateDimensions.includes(item.key)).length
  }));
}

export function profileEventsForDimension(events: ProfileEventResponse[], key: ProfileDimensionKey | null) {
  if (!key) return events;
  return events.filter((event) => buildProfileEventView(event).dimensions.includes(key));
}

function normalizedValue(value: string | string[]) {
  return Array.isArray(value) ? value.join("|") : value.trim();
}

export function buildProfileUpdateReceipt(
  previous: StudentProfileResponse,
  next: StudentProfileResponse,
  event: ProfileEventResponse
): ProfileUpdateReceipt {
  const eventView = buildProfileEventView(event);
  const changedDimensions = PROFILE_DIMENSIONS
    .filter(({ key }) => (
      normalizedValue(previous.profile_json[key]) !== normalizedValue(next.profile_json[key])
      || Math.round(previous.dimension_confidence?.[key] ?? 0) !== Math.round(next.dimension_confidence?.[key] ?? 0)
    ))
    .map((item) => item.key);
  const appliedDimensions = eventView.appliedDimensions.length > 0
    ? eventView.appliedDimensions
    : event.status === "applied"
      ? changedDimensions
      : [];
  return {
    appliedDimensions,
    candidateDimensions: eventView.candidateDimensions,
    changedDimensions
  };
}

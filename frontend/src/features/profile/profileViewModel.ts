import type { ProfileEventResponse, ProfileJson, StudentProfileResponse } from "../../api/profiles";

export type ProfileDimensionKey = keyof ProfileJson;

export type ProfileDimensionMeta = {
  key: ProfileDimensionKey;
  label: string;
  shortLabel: string;
  description: string;
  guidance: string;
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
  { key: "major_background", label: "专业背景", shortLabel: "背景", description: "专业方向与已有学习经历", guidance: "描述你目前所学的方向、阶段或相关学习经历即可。" },
  { key: "knowledge_foundation", label: "知识基础", shortLabel: "基础", description: "当前知识储备与先修能力", guidance: "说说你已经接触过的相关课程、概念或技能即可。" },
  { key: "learning_goal", label: "学习目标", shortLabel: "目标", description: "希望达成的学习结果", guidance: "说明你现阶段最想掌握、完成或解决的内容即可。" },
  { key: "cognitive_style", label: "认知风格", shortLabel: "认知", description: "理解、推理与组织知识的方式", guidance: "描述你理解、分析和整理新知识时的习惯即可。" },
  { key: "learning_preference", label: "学习偏好", shortLabel: "偏好", description: "更适合的内容与练习形式", guidance: "说明什么样的内容呈现和练习方式更适合你即可。" },
  { key: "weak_points", label: "薄弱点", shortLabel: "薄弱", description: "重复出现且有证据支持的困难", guidance: "指出目前最难理解、最容易出错或经常卡住的部分即可。" },
  { key: "learning_pace", label: "学习节奏", shortLabel: "节奏", description: "任务密度与复习节奏偏好", guidance: "描述你通常能投入的学习时间和学习频率即可。" },
  { key: "motivation_interest", label: "动机兴趣", shortLabel: "动机", description: "持续学习的兴趣与驱动力", guidance: "说说促使你学习的原因、期待或感兴趣的方向即可。" }
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
    .filter((item) => event.change_summary.includes(item.label) || event.change_summary.includes(item.shortLabel))
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

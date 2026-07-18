import {
  Article,
  Brain,
  Code,
  ListChecks,
  PlayCircle,
  PresentationChart
} from "@phosphor-icons/react";
import { type ComponentType } from "react";

import { type GeneratedResource, type ResourceType } from "../../api/resources";

type ResourceIcon = ComponentType<{ size?: number; weight?: "regular" | "duotone" | "fill" }>;

export const resourceTypeMeta: Record<ResourceType, { label: string; Icon: ResourceIcon }> = {
  doc: { label: "讲解文档", Icon: Article },
  mindmap: { label: "思维导图", Icon: Brain },
  quiz: { label: "练习题", Icon: ListChecks },
  code: { label: "代码实操", Icon: Code },
  slide: { label: "PPT", Icon: PresentationChart },
  animation: { label: "动画图解", Icon: PlayCircle },
  video: { label: "外部视频", Icon: PlayCircle }
};

export const resourceTypeLabels = Object.fromEntries(
  Object.entries(resourceTypeMeta).map(([resourceType, meta]) => [resourceType, meta.label])
) as Record<ResourceType, string>;

const resourceRoleLabels: Record<string, string> = {
  core: "核心学习",
  structure: "建立结构",
  assessment: "检查理解",
  practice: "应用验证",
  intuition: "直观理解",
  review: "巩固复习",
  extension: "拓展学习"
};

export function resourceRoleLabel(role: string) {
  const normalized = role.trim();
  return resourceRoleLabels[normalized] ?? (normalized || "辅助学习");
}

export function isResourceType(value: string): value is ResourceType {
  return value in resourceTypeMeta;
}

export function isLowEvidenceResource(resource: GeneratedResource) {
  return resource.review_status === "low_evidence"
    || resource.content_json.metadata?.generation_mode === "low_evidence_fallback";
}

export function generationModeLabel(resource: GeneratedResource) {
  const generationMode = resource.content_json.metadata?.generation_mode;
  if (isLowEvidenceResource(resource)) return "低依据";
  if (generationMode === "model_enhanced") return "模型增强";
  if (generationMode === "deterministic_source") return "本地可用稿";
  if (generationMode === "curated_external") return "联网精选";
  if (resource.review_status === "failed") return "生成失败";
  if (resource.review_status === "passed") return "可使用";
  return "待审核";
}

export function formatResourceDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString("zh-CN", { month: "2-digit", day: "2-digit" });
}

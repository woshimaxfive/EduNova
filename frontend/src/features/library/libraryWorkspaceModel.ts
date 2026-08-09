import type {
  MaterialComparisonResult,
  MaterialListItem,
  MaterialOutline
} from "../../api/materials";

export type DrawerMode = "detail" | "compare" | null;
export type DetailTab = "overview" | "outline" | "chunks" | "courses";
export type CompareTab = "common" | "exam" | "differences" | "sources";
export type CompareView = "setup" | "result" | "recent";

export function parsePositiveId(value: string | null) {
  if (!value) return null;
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

export function asArray<T>(value: unknown): T[] {
  return Array.isArray(value) ? (value as T[]) : [];
}

export function asMaterialComparison(value: unknown): MaterialComparisonResult | null {
  if (!value || typeof value !== "object" || !("summary" in value) || !("citations" in value)) return null;
  return value as MaterialComparisonResult;
}

export function asMaterialOutline(value: unknown): MaterialOutline | null {
  if (!value || typeof value !== "object") return null;
  const outline = value as Partial<MaterialOutline>;
  if (typeof outline.version !== "number" || !Array.isArray(outline.sections) || !Array.isArray(outline.chunks)) {
    return null;
  }
  return {
    ...outline,
    quality: outline.quality ?? {},
    warnings: outline.warnings ?? [],
    sections: outline.sections,
    chunks: outline.chunks
  } as MaterialOutline;
}

function stripExtension(title: string) {
  return title.replace(/\.[^.]+$/, "").trim() || title;
}

export function buildSuggestedCourseTitle(materials: MaterialListItem[]) {
  if (materials.length === 0) return "资料生成课程";
  const firstTitle = stripExtension(materials[0].title);
  return materials.length === 1 ? `${firstTitle}课程` : `${firstTitle}等资料课程`;
}

export function commonCourseIds(materials: MaterialListItem[]) {
  if (materials.length === 0) return [];
  return materials.slice(1).reduce(
    (common, material) => common.filter((courseId) => material.course_ids.includes(courseId)),
    [...materials[0].course_ids]
  );
}

export function pointConfidenceLabel(confidence: string) {
  if (confidence === "high") return "高";
  if (confidence === "low") return "低";
  return "中";
}

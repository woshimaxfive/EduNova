import { type MaterialListItem } from "../../api/materials";

export function isComparableMaterial(material: MaterialListItem) {
  return material.category === "document" && material.ingestion_status === "confirmed" && material.course_ids.length > 0;
}

export function materialUnavailableReason(material: MaterialListItem) {
  if (material.category === "image") return "图片暂不参与资料对比";
  if (material.ingestion_status !== "confirmed") return "确认资料目录后可参与对比";
  if (material.course_ids.length === 0) return "尚未关联课程";
  return null;
}

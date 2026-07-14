import { BookOpen, Check, FileText, Image, WarningCircle } from "@phosphor-icons/react";

import { type MaterialListItem } from "../../api/materials";
import { isComparableMaterial, materialUnavailableReason } from "./libraryMaterialState";

type LibraryFileTableProps = {
  materials: MaterialListItem[];
  courseTitles: Map<string, string>;
  compareMode: boolean;
  selectedMaterialIds: string[];
  isLoading: boolean;
  isError: boolean;
  onOpenMaterial: (material: MaterialListItem) => void;
  onToggleCompare: (material: MaterialListItem) => void;
};

function statusLabel(material: MaterialListItem) {
  if (material.ingestion_status === "confirmed") return "目录已确认";
  if (material.ingestion_status === "awaiting_confirmation") return "待确认目录";
  if (material.ingestion_status === "pending") return "等待精细解析";
  if (material.ingestion_status === "running") return "精细解析中";
  if (material.ingestion_status === "failed") return "精细解析失败";
  if ((material.ingestion_status === "legacy" || !material.ingestion_status) && material.parse_status === "completed") return "旧版解析";
  if (material.parse_status === "completed") return "已解析";
  if (material.parse_status === "failed") return "解析失败";
  if (material.category === "image" || material.parse_status === "uploaded") return "已入库";
  return "解析中";
}

export function LibraryFileTable(props: LibraryFileTableProps) {
  return (
    <section className="library-file-workspace" aria-label="资料文件列表">
      <div className={props.compareMode ? "library-table-head compare" : "library-table-head"} aria-hidden="true">
        {props.compareMode ? <span>选择</span> : null}
        <span>名称</span>
        <span>状态</span>
        <span>关联课程</span>
        <span>修改时间</span>
        <span>大小</span>
      </div>

      {props.isLoading ? <div className="library-table-state">正在读取资料库。</div> : null}
      {!props.isLoading && props.isError ? <div className="library-table-state warning">资料库暂时没有读取成功，请稍后重试。</div> : null}
      {!props.isLoading && !props.isError && props.materials.length === 0 ? <div className="library-table-state">没有匹配的资料。</div> : null}

      {!props.isLoading && !props.isError ? props.materials.map((material) => {
        const selected = props.selectedMaterialIds.includes(material.id);
        const comparable = isComparableMaterial(material);
        const courseNames = material.course_ids.map((id) => props.courseTitles.get(id)).filter(Boolean);
        const rowClass = ["library-table-row", props.compareMode ? "compare" : "", selected ? "selected" : "", props.compareMode && !comparable ? "disabled" : ""].filter(Boolean).join(" ");
        const rowLabel = props.compareMode
          ? `${selected ? "取消选择" : "选择"}${material.title}${comparable ? "" : `，${materialUnavailableReason(material)}`}`
          : `查看${material.title}`;

        return (
          <div className={rowClass} key={material.id}>
            {props.compareMode ? (
              <span className="library-row-selector" aria-hidden="true">
                {selected ? <Check size={15} weight="bold" /> : null}
              </span>
            ) : null}
            <button
              className="library-row-action"
              type="button"
              aria-label={rowLabel}
              disabled={props.compareMode && !comparable}
              onClick={() => props.compareMode ? props.onToggleCompare(material) : props.onOpenMaterial(material)}
            >
              <span className="library-row-icon" data-category={material.category} aria-hidden="true">
                {material.category === "image" ? <Image size={19} weight="duotone" /> : <FileText size={19} weight="duotone" />}
              </span>
              <span className="library-row-name">
                <strong>{material.title}</strong>
                <small>{material.extension}{materialUnavailableReason(material) && props.compareMode ? ` · ${materialUnavailableReason(material)}` : ""}</small>
              </span>
            </button>
            <span className={`library-status-label status-${material.ingestion_status ?? material.parse_status}`}>
              {material.ingestion_status === "failed" || material.parse_status === "failed" ? <WarningCircle size={14} aria-hidden="true" /> : null}
              {statusLabel(material)}
            </span>
            <span className="library-course-cell" title={courseNames.join("、")}>
              <BookOpen size={15} aria-hidden="true" />
              {courseNames.length > 0 ? (courseNames.length === 1 ? courseNames[0] : `${courseNames[0]} 等 ${courseNames.length} 门`) : "未关联"}
            </span>
            <span>{material.modified}</span>
            <span>{material.size || "—"}</span>
          </div>
        );
      }) : null}
    </section>
  );
}

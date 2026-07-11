import { MagnifyingGlass } from "@phosphor-icons/react";

import { type GeneratedResource, type ResourceType } from "../../api/resources";
import { formatResourceDate, generationModeLabel, isLowEvidenceResource, resourceTypeMeta } from "./studioResourceMeta";

type StudioResourceLibraryProps = {
  hasCourse: boolean;
  resources: GeneratedResource[];
  selectedResourceId: string | null;
  search: string;
  typeFilter: "all" | ResourceType;
  isLoading: boolean;
  onSearchChange: (value: string) => void;
  onTypeFilterChange: (value: "all" | ResourceType) => void;
  onSelectResource: (resourceId: string) => void;
};

export function StudioResourceLibrary({
  hasCourse,
  resources,
  selectedResourceId,
  search,
  typeFilter,
  isLoading,
  onSearchChange,
  onTypeFilterChange,
  onSelectResource
}: StudioResourceLibraryProps) {
  return (
    <aside className="studio-resource-library" aria-label="成果库">
      <header>
        <div>
          <h2>成果库</h2>
          <span>{resources.length} 项</span>
        </div>
        <label className="studio-resource-search">
          <MagnifyingGlass size={16} aria-hidden="true" />
          <span className="visually-hidden">搜索成果</span>
          <input
            aria-label="搜索成果"
            value={search}
            onChange={(event) => onSearchChange(event.target.value)}
            placeholder="搜索标题"
          />
        </label>
        <label className="studio-resource-filter">
          <span className="visually-hidden">资源类型筛选</span>
          <select
            aria-label="资源类型筛选"
            value={typeFilter}
            onChange={(event) => onTypeFilterChange(event.target.value as "all" | ResourceType)}
          >
            <option value="all">全部类型</option>
            {Object.entries(resourceTypeMeta).map(([type, meta]) => (
              <option key={type} value={type}>{meta.label}</option>
            ))}
          </select>
        </label>
      </header>

      <div className="studio-resource-list">
        {isLoading ? (
          <div className="studio-library-skeleton" aria-label="正在读取成果">
            <span /><span /><span />
          </div>
        ) : resources.length > 0 ? (
          resources.map((resource) => {
            const { Icon, label } = resourceTypeMeta[resource.resource_type];
            const selected = resource.id === selectedResourceId;
            return (
              <button
                className={`studio-resource-row${selected ? " active" : ""}${isLowEvidenceResource(resource) ? " low-evidence" : ""}`}
                type="button"
                key={resource.id}
                aria-label={`打开成果 ${resource.title}`}
                aria-pressed={selected}
                onClick={() => onSelectResource(resource.id)}
              >
                <span className="studio-resource-row-icon"><Icon size={18} weight="duotone" /></span>
                <span className="studio-resource-row-copy">
                  <strong>{resource.title}</strong>
                  <small>{label} · {formatResourceDate(resource.created_at)}</small>
                </span>
                <em>{generationModeLabel(resource)}</em>
              </button>
            );
          })
        ) : (
          <p className="studio-library-empty">
            {!hasCourse
              ? "选择课程后查看成果。"
              : search.trim() || typeFilter !== "all"
                ? "没有匹配的成果。"
                : "这门课还没有资源。"}
          </p>
        )}
      </div>
    </aside>
  );
}

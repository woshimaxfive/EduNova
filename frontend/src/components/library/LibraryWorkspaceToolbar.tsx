import { ArrowsLeftRight, ClockCounterClockwise, FileArrowUp, MagnifyingGlass, Sparkle } from "@phosphor-icons/react";

export type LibraryFilter = "all" | "document" | "image";

type LibraryWorkspaceToolbarProps = {
  search: string;
  filter: LibraryFilter;
  materialCount: number;
  parsedCount: number;
  isUploading: boolean;
  hasCourses: boolean;
  onSearchChange: (value: string) => void;
  onFilterChange: (filter: LibraryFilter) => void;
  onUpload: () => void;
  onGenerateCourse: () => void;
  onStartCompare: () => void;
  onOpenRecentComparison: () => void;
};

const filters: Array<{ value: LibraryFilter; label: string }> = [
  { value: "all", label: "全部" },
  { value: "document", label: "文档" },
  { value: "image", label: "图片" }
];

export function LibraryWorkspaceToolbar(props: LibraryWorkspaceToolbarProps) {
  return (
    <header className="library-workspace-toolbar">
      <div className="library-toolbar-summary">
        <strong><span className="library-toolbar-kicker">资料库</span>{props.materialCount} 份资料</strong>
        <span>{props.parsedCount} 份已解析，可用于问答与建课</span>
      </div>

      <label className="library-workspace-search">
        <MagnifyingGlass size={17} weight="duotone" aria-hidden="true" />
        <input aria-label="搜索资料" placeholder="搜索名称或格式" value={props.search} onChange={(event) => props.onSearchChange(event.target.value)} />
      </label>

      <div className="library-workspace-filters" role="group" aria-label="资料类型">
        {filters.map((filter) => (
          <button key={filter.value} type="button" aria-pressed={props.filter === filter.value} onClick={() => props.onFilterChange(filter.value)}>
            {filter.label}
          </button>
        ))}
      </div>

      <div className="library-toolbar-actions">
        <button className="soft-button" type="button" disabled={!props.hasCourses} onClick={props.onOpenRecentComparison}>
          <ClockCounterClockwise size={17} aria-hidden="true" />
          <span>最近对比</span>
        </button>
        <button className="soft-button" type="button" disabled={!props.hasCourses} onClick={props.onStartCompare}>
          <ArrowsLeftRight size={17} aria-hidden="true" />
          <span>资料对比</span>
        </button>
        <button className="soft-button" type="button" onClick={props.onGenerateCourse}>
          <Sparkle size={17} aria-hidden="true" />
          <span>生成课程</span>
        </button>
        <button className="primary-action" type="button" aria-label="上传资料" disabled={props.isUploading} onClick={props.onUpload}>
          <FileArrowUp size={17} aria-hidden="true" />
          <span>{props.isUploading ? "上传中" : "上传"}</span>
        </button>
      </div>
    </header>
  );
}

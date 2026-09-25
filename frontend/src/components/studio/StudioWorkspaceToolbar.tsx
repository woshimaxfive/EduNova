import { ArrowClockwise, Info, Sparkle } from "@phosphor-icons/react";

import { type ApiCourseSummary } from "../../api/courses";
import { type GeneratedResource } from "../../api/resources";
import { CourseReturnLink } from "../course-space/CourseReturnLink";
import { generationModeLabel, resourceTypeMeta } from "./studioResourceMeta";

type StudioWorkspaceToolbarProps = {
  courses: ApiCourseSummary[];
  courseId: number | null;
  resourceCount: number;
  selectedResource: GeneratedResource | null;
  isGenerating: boolean;
  onCourseChange: (courseId: number | null) => void;
  onOpenGenerate: () => void;
  onOpenDetails: () => void;
  onRegenerate: () => void;
};

export function StudioWorkspaceToolbar({
  courses,
  courseId,
  resourceCount,
  selectedResource,
  isGenerating,
  onCourseChange,
  onOpenGenerate,
  onOpenDetails,
  onRegenerate
}: StudioWorkspaceToolbarProps) {
  const selectedType = selectedResource ? resourceTypeMeta[selectedResource.resource_type].label : null;
  return (
    <header className="studio-workspace-toolbar" aria-label="资源工坊工具栏">
      <label className="studio-course-select">
        <span>资源工坊 · 课程</span>
        <select
          aria-label="资源课程"
          value={courseId ?? ""}
          disabled={courses.length === 0}
          onChange={(event) => onCourseChange(event.target.value ? Number.parseInt(event.target.value, 10) : null)}
        >
          {courses.length > 0 ? courses.map((course) => (
            <option key={course.id} value={course.id}>{course.title}{course.learning_status === "archived" ? "（已完成）" : course.is_current ? "（当前学习）" : ""}</option>
          )) : <option value="">还没有课程</option>}
        </select>
      </label>

      <div className="studio-toolbar-context">
        <strong>{selectedResource?.title ?? "尚未选择成果"}</strong>
        <span>{selectedResource ? `${selectedType} · ${generationModeLabel(selectedResource)}` : `${resourceCount} 项课程资源`}</span>
      </div>

      <div className="studio-toolbar-actions">
        <CourseReturnLink courseId={courseId} compact alwaysShow />
        <button className="soft-button" type="button" disabled={!selectedResource || isGenerating} onClick={onRegenerate}>
          <ArrowClockwise size={17} weight="duotone" aria-hidden="true" />
          <span>重新生成</span>
        </button>
        <button className="soft-button" type="button" disabled={!selectedResource} onClick={onOpenDetails}>
          <Info size={17} weight="duotone" aria-hidden="true" />
          <span>成果详情</span>
        </button>
        <button className="primary-action" type="button" disabled={courseId === null} onClick={onOpenGenerate}>
          <Sparkle size={17} weight="fill" aria-hidden="true" />
          <span>{isGenerating ? "生成中" : "新建资源"}</span>
        </button>
      </div>
    </header>
  );
}

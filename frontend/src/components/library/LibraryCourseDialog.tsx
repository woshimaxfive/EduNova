import { X } from "@phosphor-icons/react";

import type { AiJob } from "../../api/aiJobs";
import type { MaterialListItem } from "../../api/materials";
import { AiJobProgress } from "../feedback/AiJobProgress";
import { InlineFeedback } from "../feedback/InlineFeedback";
import { ModalFrame } from "../primitives/Dialog";

type LibraryCourseDialogProps = {
  materials: MaterialListItem[];
  selectedMaterialIds: string[];
  courseTitle: string;
  isCreatingCourse: boolean;
  job?: AiJob;
  feedback: string | null;
  onCourseTitleChange: (courseTitle: string) => void;
  onToggleMaterial: (materialId: string) => void;
  onClose: () => void;
  onCreate: () => void;
  onCancelJob: () => void;
  onRetryJob: () => void;
};

export function LibraryCourseDialog(props: LibraryCourseDialogProps) {
  const selectedCount = props.selectedMaterialIds.length;

  return (
    <ModalFrame title="从资料生成课程" layerClassName="course-dialog-backdrop" onClose={props.onClose} dismissible={!props.isCreatingCourse}>
      <section className="course-dialog library-course-dialog" aria-labelledby="library-course-dialog-title">
        <button className="course-dialog-close" type="button" aria-label="关闭生成课程" onClick={props.onClose}>
          <X size={18} aria-hidden="true" />
        </button>
        <div className="dialog-copy"><h2 id="library-course-dialog-title">从资料生成课程</h2><p>选择已解析资料，生成目录、知识点和复习任务。</p></div>
        <label className="dialog-field">
          <span>课程名称</span>
          <input aria-label="课程名称" value={props.courseTitle} onChange={(event) => props.onCourseTitleChange(event.target.value)} />
        </label>
        <div className="library-course-materials">
          {props.materials.length === 0 ? <p className="library-table-state">还没有可生成课程的资料。</p> : null}
          {props.materials.map((material) => {
            const available = material.category === "document" && material.ingestion_status === "confirmed";
            const selected = props.selectedMaterialIds.includes(material.id);
            return (
              <button
                className={selected ? "active" : ""}
                key={material.id}
                type="button"
                disabled={!available}
                aria-pressed={selected}
                onClick={() => props.onToggleMaterial(material.id)}
              >
                <span>{material.extension}</span>
                <strong>{material.title}</strong>
                <small>{available ? material.detail : "需要先完成精细解析并确认目录"}</small>
              </button>
            );
          })}
        </div>
        <InlineFeedback message={props.feedback} tone="warning" className="dialog-inline-feedback" />
        {props.job ? <AiJobProgress job={props.job} onCancel={props.onCancelJob} onRetry={props.onRetryJob} /> : null}
        <button
          className={selectedCount > 0 ? "dialog-primary-button" : "dialog-primary-button disabled"}
          type="button"
          disabled={selectedCount === 0 || props.isCreatingCourse}
          onClick={props.onCreate}
        >
          {props.isCreatingCourse ? "生成中" : "生成课程"}
        </button>
      </section>
    </ModalFrame>
  );
}

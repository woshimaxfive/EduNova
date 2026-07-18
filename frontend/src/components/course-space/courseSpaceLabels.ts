import { type StudyStepStatus } from "../../features/course-space/a3Loop";
export { resourceTypeLabels } from "../resources/resourceDisplayMeta";

export const studyStepStatusLabels: Record<StudyStepStatus, string> = {
  done: "已完成",
  ready: "可继续",
  next: "建议下一步",
  empty: "待产生"
};

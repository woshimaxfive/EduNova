import { type ResourceType } from "../../api/resources";
import { type StudyStepStatus } from "../../features/course-space/a3Loop";

export const resourceTypeLabels: Record<ResourceType, string> = {
  doc: "讲解文档",
  mindmap: "思维导图",
  quiz: "练习题",
  code: "代码实操",
  slide: "PPT 大纲"
};

export const studyStepStatusLabels: Record<StudyStepStatus, string> = {
  done: "已完成",
  ready: "可继续",
  next: "建议下一步",
  empty: "待产生"
};

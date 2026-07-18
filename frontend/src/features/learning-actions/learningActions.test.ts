import { describe, expect, it } from "vitest";

import { type LearningNextAction } from "../../api/learning";
import { learningActionButtonLabel, learningActionHref } from "./learningActions";

function action(kind: string, overrides: Partial<LearningNextAction> = {}): LearningNextAction {
  return {
    kind,
    status: "ready",
    label: "下一步",
    description: "继续学习",
    course_id: "8",
    material_id: null,
    knowledge_point_id: null,
    path_task_id: null,
    resource_id: null,
    ...overrides
  };
}

describe("learning action routes", () => {
  it("uses an explicit verb for each primary action", () => {
    expect(learningActionButtonLabel(action("upload_material"))).toBe("上传资料");
    expect(learningActionButtonLabel(action("review_material"))).toBe("确认目录");
    expect(learningActionButtonLabel(action("practice_weakness"))).toBe("开始练习");
    expect(learningActionButtonLabel(action("update_report"))).toBe("更新报告");
  });

  it("routes the material lifecycle to the selected material", () => {
    expect(learningActionHref(action("review_material", { course_id: null, material_id: "12" }))).toBe("/app/library?material_id=12");
    expect(learningActionHref(action("upload_material", { course_id: null }))).toBe("/app/library");
  });

  it("routes path tasks to real resources or course knowledge", () => {
    expect(learningActionHref(action("continue_path_task", { resource_id: "18", path_task_id: "9" }))).toBe("/app/studio?course_id=8&resource_id=18&path_task_id=9");
    expect(learningActionHref(action("continue_path_task", { knowledge_point_id: "42", path_task_id: "9" }))).toBe("/app/courses/8?mode=study&view=overview&knowledge_point_id=42&path_task_id=9");
  });

  it("routes practice, path and report actions deterministically", () => {
    expect(learningActionHref(action("practice_weakness", { knowledge_point_id: "42", weakness_item_id: "61" }))).toBe("/app/practice?course_id=8&knowledge_point_id=42&weakness_item_id=61&new=1");
    expect(learningActionHref(action("generate_path"))).toBe("/app/path?course_id=8");
    expect(learningActionHref(action("update_report"))).toBe("/app/reports?course_id=8");
    expect(learningActionHref(action("wait_for_practice"))).toBe("/app/practice?course_id=8");
    expect(learningActionHref(action("wait_for_report"))).toBe("/app/reports?course_id=8");
  });
});

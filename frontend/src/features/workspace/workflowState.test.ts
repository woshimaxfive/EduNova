import { describe, expect, it } from "vitest";

import { buildMaterialLifecycle, getWorkspaceStatePanels, WORKFLOW_STAGE_ORDER } from "./workflowState";

describe("workspace workflow state", () => {
  it("maps material progress to a visible lifecycle rail", () => {
    const stages = buildMaterialLifecycle("chunking", 60);

    expect(WORKFLOW_STAGE_ORDER).toEqual([
      "uploaded",
      "parsing",
      "building_course",
      "chunking",
      "embedding",
      "path_generating",
      "completed"
    ]);
    expect(stages.map((stage) => stage.status)).toEqual([
      "completed",
      "completed",
      "completed",
      "active",
      "queued",
      "queued",
      "queued"
    ]);
    expect(stages[3]).toMatchObject({
      id: "chunking",
      label: "切分知识片段",
      progressPercent: 60
    });
  });

  it("turns failed parsing into a recoverable state", () => {
    const stages = buildMaterialLifecycle("failed", 42);
    const failedStage = stages.find((stage) => stage.status === "failed");

    expect(failedStage).toMatchObject({
      id: "failed",
      label: "处理失败",
      nextAction: "重新上传，或换成文本版资料"
    });
  });

  it("exposes the required empty, loading, error, low evidence and local preview states", () => {
    expect(getWorkspaceStatePanels().map((panel) => panel.kind)).toEqual([
      "empty",
      "loading",
      "error",
      "low_evidence",
      "local_preview"
    ]);
  });
});

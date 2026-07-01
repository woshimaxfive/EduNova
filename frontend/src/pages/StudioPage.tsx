import { StudioDock } from "../components/studio/StudioDock";
import { WorkspaceStateStrip } from "../components/states/WorkspaceStateStrip";
import { demoLearningSpace } from "../data/demoLearningSpace";
import { getWorkspaceStatePanels } from "../features/workspace/workflowState";
import { PageFrame } from "./PageFrame";

export function StudioPage() {
  const evidencePanels = getWorkspaceStatePanels().filter((panel) =>
    ["loading", "low_evidence", "demo_fallback"].includes(panel.kind)
  );

  return (
    <PageFrame kicker="Studio" title="把知识点生成可学习资源" description="讲解、练习、思维导图、复盘报告和 PPT 大纲会绑定引用与审核状态。">
      <WorkspaceStateStrip panels={evidencePanels} />
      <StudioDock outputs={demoLearningSpace.studioOutputs} />
    </PageFrame>
  );
}

import { CommandBar } from "../components/command/CommandBar";
import { EvidenceLayer } from "../components/evidence/EvidenceLayer";
import { LearningCanvas } from "../components/canvas/LearningCanvas";
import { LearningSpaceShell } from "../components/layout/LearningSpaceShell";
import { WorkflowStatusRail } from "../components/states/WorkflowStatusRail";
import { WorkspaceStateStrip } from "../components/states/WorkspaceStateStrip";
import { StudioDock } from "../components/studio/StudioDock";
import { demoLearningSpace } from "../data/demoLearningSpace";
import { FirstRunGuide } from "../features/onboarding/FirstRunGuide";
import { buildMaterialLifecycle, getWorkspaceStatePanels } from "../features/workspace/workflowState";

export function LearningSpacePage() {
  const materialLifecycle = buildMaterialLifecycle("embedding", 74);
  const workspaceStatePanels = getWorkspaceStatePanels();

  return (
    <LearningSpaceShell>
      <section className="workspace-hero">
        <div>
          <p className="section-kicker">学生端学习闭环</p>
          <h1>今天的 AI 学习空间</h1>
          <p>围绕一门课程，把资料、路径、练习、Studio 和证据链放在同一个工作台里。</p>
        </div>
        <div className="hero-status" aria-label="当前学习状态">
          <strong>{demoLearningSpace.currentCourse.title}</strong>
          <span>焦点：监督学习</span>
        </div>
      </section>
      <div className="workspace-grid">
        <div className="workspace-main">
          <LearningCanvas snapshot={demoLearningSpace} />
          <WorkflowStatusRail
            title="资料正在变成课程"
            description="上传、解析、生成课程、切片、索引和路径规划都在同一条进度轨道中呈现。"
            stages={materialLifecycle}
          />
          <WorkspaceStateStrip panels={workspaceStatePanels} />
          <FirstRunGuide />
          <StudioDock outputs={demoLearningSpace.studioOutputs} />
        </div>
        <EvidenceLayer snapshot={demoLearningSpace} />
      </div>
      <CommandBar />
    </LearningSpaceShell>
  );
}

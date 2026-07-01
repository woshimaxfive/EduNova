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
  const currentCourse = demoLearningSpace.currentCourse;

  return (
    <LearningSpaceShell>
      <section className="workspace-hero">
        <div>
          <p className="section-kicker">学习操作系统</p>
          <h1>今天的 AI 学习空间</h1>
          <p>资料流入知识画布，AI 命令驱动路径、练习、资源和证据链。</p>
        </div>
      </section>
      <section className="workspace-status-bar" aria-label="当前学习上下文">
        <div className="status-course">
          <span>当前课程</span>
          <strong>{currentCourse.title}</strong>
        </div>
        <dl className="status-metrics">
          <div>
            <dt>焦点</dt>
            <dd>监督学习</dd>
          </div>
          <div>
            <dt>路径进度</dt>
            <dd>{currentCourse.progressPercent}%</dd>
          </div>
          <div>
            <dt>资料状态</dt>
            <dd>索引中</dd>
          </div>
        </dl>
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
          <StudioDock outputs={demoLearningSpace.studioOutputs} />
          <FirstRunGuide />
        </div>
        <EvidenceLayer snapshot={demoLearningSpace} />
      </div>
      <CommandBar />
    </LearningSpaceShell>
  );
}

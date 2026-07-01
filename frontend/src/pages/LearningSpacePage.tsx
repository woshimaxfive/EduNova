import { CommandBar } from "../components/command/CommandBar";
import { EvidenceLayer } from "../components/evidence/EvidenceLayer";
import { LearningCanvas } from "../components/canvas/LearningCanvas";
import { LearningSpaceShell } from "../components/layout/LearningSpaceShell";
import { StudioDock } from "../components/studio/StudioDock";
import { demoLearningSpace } from "../data/demoLearningSpace";
import { FirstRunGuide } from "../features/onboarding/FirstRunGuide";

export function LearningSpacePage() {
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
          <FirstRunGuide />
          <StudioDock outputs={demoLearningSpace.studioOutputs} />
        </div>
        <EvidenceLayer snapshot={demoLearningSpace} />
      </div>
      <CommandBar />
    </LearningSpaceShell>
  );
}

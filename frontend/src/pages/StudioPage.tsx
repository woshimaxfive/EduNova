import { ClockCounterClockwise, FileText, Sparkle } from "@phosphor-icons/react";

import { ActionNotice } from "../components/feedback/ActionNotice";
import { useActionNotice } from "../components/feedback/useActionNotice";
import { StudioDock } from "../components/studio/StudioDock";
import { WorkspaceStateStrip } from "../components/states/WorkspaceStateStrip";
import { demoLearningSpace } from "../data/demoLearningSpace";
import { getWorkspaceStatePanels } from "../features/workspace/workflowState";
import { PageFrame } from "./PageFrame";

export function StudioPage() {
  const evidencePanels = getWorkspaceStatePanels().filter((panel) =>
    ["loading", "low_evidence", "demo_fallback"].includes(panel.kind)
  );
  const { notice, showNotice } = useActionNotice();

  return (
    <PageFrame title="资源工坊" description="把知识点生成讲解、练习、思维导图、复盘报告和 PPT 大纲，并绑定引用与审核状态。">
      <section className="student-panel studio-workbench" role="region" aria-label="资源生成工作台">
        <div className="student-panel-heading">
          <div>
            <p className="section-kicker">生成队列</p>
            <h2>先选知识点，再决定生成什么</h2>
          </div>
          <button className="primary-action" type="button" onClick={() => showNotice("已加入资源生成演示队列，真实任务 API 接入后会显示进度。", "success")}>
            <Sparkle size={18} weight="fill" aria-hidden="true" />
            <span>生成资源</span>
          </button>
        </div>
        <ActionNotice notice={notice} />

        <WorkspaceStateStrip panels={evidencePanels} />

        <section className="generation-queue" role="region" aria-label="生成队列">
          {[
            { title: "监督学习个性化讲解", meta: "绑定 2 条引用 · 待审核", icon: FileText },
            { title: "反向传播薄弱点练习", meta: "8 道递进题 · 生成中", icon: ClockCounterClockwise },
            { title: "神经网络知识图谱", meta: "等待选择输出格式", icon: Sparkle }
          ].map((item) => {
            const Icon = item.icon;

            return (
              <article className="queue-row" key={item.title}>
                <span className="queue-row-icon" aria-hidden="true">
                  <Icon size={19} weight="duotone" />
                </span>
                <span>
                  <strong>{item.title}</strong>
                  <small>{item.meta}</small>
                </span>
              </article>
            );
          })}
        </section>
      </section>

      <StudioDock outputs={demoLearningSpace.studioOutputs} />
    </PageFrame>
  );
}

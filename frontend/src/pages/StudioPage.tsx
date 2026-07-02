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
    <PageFrame title="资源工坊" description="生成讲解、练习、导图和复盘。">
      <section className="student-panel studio-workbench" role="region" aria-label="资源生成工作台">
        <div className="student-panel-heading">
          <div>
            <h2>选择知识点，生成资源</h2>
          </div>
          <button className="primary-action" type="button" onClick={() => showNotice("已加入生成队列。", "success")}>
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

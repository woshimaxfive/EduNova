import { ClockCounterClockwise, Sparkle } from "@phosphor-icons/react";
import { useState } from "react";

import { StudioDock } from "../components/studio/StudioDock";
import { WorkspaceStateStrip } from "../components/states/WorkspaceStateStrip";
import { getWorkspaceStatePanels } from "../features/workspace/workflowState";
import { type StudioOutput } from "../types/api";
import { PageFrame } from "./PageFrame";

const resourceTypes: StudioOutput["resourceType"][] = ["讲解", "练习", "思维导图", "代码实操", "PPT 大纲"];
const knowledgeOptions = ["监督学习", "反向传播", "神经网络", "搜索与知识表示"];

export function StudioPage() {
  const evidencePanels = getWorkspaceStatePanels().filter((panel) =>
    ["loading", "low_evidence", "local_preview"].includes(panel.kind)
  );
  const [selectedKnowledge, setSelectedKnowledge] = useState(knowledgeOptions[0]);
  const [selectedResourceType, setSelectedResourceType] = useState<StudioOutput["resourceType"]>("讲解");
  const [queueItems, setQueueItems] = useState<Array<{ title: string; meta: string; icon: typeof ClockCounterClockwise }>>([]);
  const [outputs, setOutputs] = useState<StudioOutput[]>([]);

  function generateResource() {
    const title = `${selectedKnowledge}${selectedResourceType}`;
    const nextOutput: StudioOutput = {
      id: Date.now(),
      title,
      resourceType: selectedResourceType,
      reviewStatus: "审核中"
    };

    setQueueItems((current) => [
      {
        title,
        meta: `${selectedResourceType} · 已加入队列`,
        icon: ClockCounterClockwise
      },
      ...current
    ]);
    setOutputs((current) => [nextOutput, ...current]);
  }

  return (
    <PageFrame title="资源工坊">
      <section className="student-panel studio-workbench" role="region" aria-label="资源生成工作台">
        <div className="student-panel-heading">
          <div>
            <h2>选择知识点，生成资源</h2>
          </div>
          <button className="primary-action" type="button" onClick={generateResource}>
            <Sparkle size={18} weight="fill" aria-hidden="true" />
            <span>生成资源</span>
          </button>
        </div>

        <div className="studio-control-grid">
          <label>
            <span>知识点</span>
            <select value={selectedKnowledge} onChange={(event) => setSelectedKnowledge(event.target.value)}>
              {knowledgeOptions.map((option) => (
                <option key={option}>{option}</option>
              ))}
            </select>
          </label>
          <div className="resource-type-row" aria-label="资源类型">
            {resourceTypes.map((type) => (
              <button
                className={selectedResourceType === type ? "active" : ""}
                key={type}
                type="button"
                aria-pressed={selectedResourceType === type}
                onClick={() => setSelectedResourceType(type)}
              >
                {type}
              </button>
            ))}
          </div>
        </div>

        <WorkspaceStateStrip panels={evidencePanels} />

        <section className="generation-queue" role="region" aria-label="生成队列">
          {queueItems.length > 0 ? queueItems.map((item) => {
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
          }) : <p className="empty-inline-note">还没有生成任务。选择知识点和资源类型后再生成。</p>}
        </section>
      </section>

      <StudioDock outputs={outputs} onGenerate={generateResource} showGenerateAction={false} />
    </PageFrame>
  );
}

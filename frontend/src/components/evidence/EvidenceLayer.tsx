import { ShieldCheck } from "@phosphor-icons/react";

import { AgentTimeline } from "./AgentTimeline";
import { type LearningSpaceSnapshot } from "../../types/api";

type EvidenceLayerProps = {
  snapshot: LearningSpaceSnapshot;
};

const confidenceLabel = {
  high: "高依据",
  medium: "中等依据",
  low: "低依据"
} as const;

export function EvidenceLayer({ snapshot }: EvidenceLayerProps) {
  return (
    <aside className="evidence-layer" role="region" aria-label="证据与 Agent 轨迹">
      <div className="section-heading-line">
        <div>
          <p className="section-kicker">证据层</p>
          <h2>引用和推理轨迹</h2>
        </div>
        <ShieldCheck size={22} weight="duotone" aria-hidden="true" />
      </div>
      <div className="citation-list">
        {snapshot.citations.map((citation) => (
          <article key={citation.id} className="citation-item">
            <strong>{citation.sourceTitle}</strong>
            <span>{citation.sectionTitle}</span>
            <small>
              {citation.pageNumber ? `第 ${citation.pageNumber} 页` : "课程资料"} · {confidenceLabel[citation.confidence]}
            </small>
          </article>
        ))}
      </div>
      <AgentTimeline events={snapshot.agentTrace} />
    </aside>
  );
}

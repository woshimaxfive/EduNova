import { Brain, Compass, Lightning } from "@phosphor-icons/react";
import { useState } from "react";

import { SourceCluster } from "./SourceCluster";
import { type KnowledgeNode, type LearningSpaceSnapshot } from "../../types/api";

type LearningCanvasProps = {
  snapshot: LearningSpaceSnapshot;
};

const statusLabel = {
  focus: "当前焦点",
  learning: "学习中",
  weak: "薄弱点",
  ready: "待学习",
  mastered: "已掌握"
} as const;

export function LearningCanvas({ snapshot }: LearningCanvasProps) {
  const [selectedNode, setSelectedNode] = useState<KnowledgeNode | null>(null);

  return (
    <section className="learning-canvas" role="region" aria-label="知识学习画布">
      <div className="canvas-header">
        <div>
          <p className="section-kicker">知识画布</p>
          <h2>{snapshot.currentCourse.title}</h2>
          <p>{snapshot.currentCourse.description}</p>
        </div>
        <div className="course-focus">
          <Compass size={20} weight="duotone" aria-hidden="true" />
          <span>{snapshot.currentCourse.progressPercent}%</span>
          <small>学习进度</small>
        </div>
      </div>
      <div className="canvas-map">
        <div className="canvas-map-label" aria-hidden="true">
          资料流入知识画布
        </div>
        <div className="canvas-flow-line" aria-hidden="true" />
        <div className="canvas-path" aria-hidden="true" />
        {snapshot.knowledgeNodes.map((node) => (
          <button
            key={node.id}
            className={`knowledge-node ${node.status} ${selectedNode?.id === node.id ? "active" : ""}`}
            style={{ left: `${node.x}%`, top: `${node.y}%` }}
            type="button"
            aria-label={`${node.title}，${statusLabel[node.status]}`}
            aria-pressed={selectedNode?.id === node.id}
            onClick={() => setSelectedNode(node)}
          >
            <span className="node-icon" aria-hidden="true">
              {node.status === "focus" ? (
                <Lightning size={18} weight="fill" />
              ) : (
                <Brain size={18} weight="duotone" />
              )}
            </span>
            <strong>{node.title}</strong>
            <small>{node.chapter}</small>
          </button>
        ))}
      </div>
      {selectedNode ? (
        <section className="canvas-node-detail" role="region" aria-label="当前知识点详情">
          <span>{statusLabel[selectedNode.status]}</span>
          <strong>{selectedNode.title}</strong>
          <p>
            {selectedNode.chapter} 会被用于课程对话、练习生成和掌握度更新。后续接入真实图谱后，这里会显示先修关系和证据来源。
          </p>
        </section>
      ) : null}
      <SourceCluster materials={snapshot.materials} />
    </section>
  );
}

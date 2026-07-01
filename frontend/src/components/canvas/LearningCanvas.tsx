import { Brain, Compass, Lightning } from "@phosphor-icons/react";

import { SourceCluster } from "./SourceCluster";
import { type LearningSpaceSnapshot } from "../../types/api";

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
        <div className="canvas-path" aria-hidden="true" />
        {snapshot.knowledgeNodes.map((node) => (
          <button
            key={node.id}
            className={`knowledge-node ${node.status}`}
            style={{ left: `${node.x}%`, top: `${node.y}%` }}
            type="button"
            aria-label={`${node.title}，${statusLabel[node.status]}`}
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
      <SourceCluster materials={snapshot.materials} />
    </section>
  );
}

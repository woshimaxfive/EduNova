import { useMemo } from "react";
import {
  Background,
  Controls,
  MarkerType,
  ReactFlow,
  type Edge,
  type Node
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import type { CourseMasteryPoint } from "../../api/courses";

type CourseKnowledgeGraphProps = {
  points: CourseMasteryPoint[];
  selectedId?: string | null;
  onSelect: (pointId: string) => void;
};

const statusLabels: Record<string, string> = {
  weak: "薄弱",
  learning: "学习中",
  mastered: "已掌握",
  recommended_review: "建议复习",
  not_started: "未开始"
};

export function CourseKnowledgeGraph({ points, selectedId, onSelect }: CourseKnowledgeGraphProps) {
  const { nodes, edges } = useMemo(() => buildGraph(points, selectedId), [points, selectedId]);

  if (points.length === 0) return null;

  return (
    <section className="course-knowledge-graph" role="region" aria-label="课程知识图谱">
      <div className="course-knowledge-graph-heading">
        <strong>知识依赖与掌握状态</strong>
        <span>{points.length} 个知识点</span>
      </div>
      <div className="course-knowledge-graph-canvas">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          fitView
          fitViewOptions={{ padding: 0.22 }}
          minZoom={0.45}
          maxZoom={1.5}
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable
          onNodeClick={(_, node) => onSelect(node.id)}
          proOptions={{ hideAttribution: true }}
        >
          <Background gap={22} size={1} color="rgba(11, 143, 127, 0.12)" />
          <Controls showInteractive={false} />
        </ReactFlow>
      </div>
      <div className="course-knowledge-graph-legend" aria-label="知识图谱图例">
        <span className="weak">薄弱</span>
        <span className="learning">学习中</span>
        <span className="mastered">已掌握</span>
        <span>未开始</span>
      </div>
    </section>
  );
}

function buildGraph(points: CourseMasteryPoint[], selectedId?: string | null) {
  const pointById = new Map(points.map((point) => [point.id, point]));
  const hasDependencies = points.some((point) =>
    (point.prerequisite_ids ?? []).some((id) => pointById.has(id))
  );
  const fallbackColumns = Math.min(4, Math.max(2, Math.ceil(Math.sqrt(points.length))));
  const levelCache = new Map<string, number>();
  const findLevel = (point: CourseMasteryPoint, visiting = new Set<string>()): number => {
    const cached = levelCache.get(point.id);
    if (cached !== undefined) return cached;
    if (visiting.has(point.id)) return 0;
    const nextVisiting = new Set(visiting).add(point.id);
    const parentLevels = (point.prerequisite_ids ?? [])
      .map((id) => pointById.get(id))
      .filter((item): item is CourseMasteryPoint => Boolean(item))
      .map((parent) => findLevel(parent, nextVisiting));
    const level = parentLevels.length > 0 ? Math.max(...parentLevels) + 1 : 0;
    levelCache.set(point.id, level);
    return level;
  };
  const rowsByLevel = new Map<number, number>();
  const columnsPerBand = 4;
  const nodes: Node[] = points.map((point, index) => {
    const level = findLevel(point);
    const row = rowsByLevel.get(level) ?? 0;
    rowsByLevel.set(level, row + 1);
    const band = Math.floor(level / columnsPerBand);
    const columnInBand = level % columnsPerBand;
    const column = band % 2 === 0 ? columnInBand : columnsPerBand - columnInBand - 1;
    return {
      id: point.id,
      position: hasDependencies
        ? { x: column * 208, y: band * 116 + row * 82 }
        : { x: (index % fallbackColumns) * 208, y: Math.floor(index / fallbackColumns) * 92 },
      data: {
        label: (
          <div className="course-knowledge-node-content">
            <strong>{point.title}</strong>
            <span>{statusLabels[point.status] ?? point.status} · {point.score === null ? "未评估" : `${point.score} 分`}</span>
          </div>
        )
      },
      className: `course-knowledge-node ${point.status} ${selectedId === point.id ? "selected" : ""}`,
      style: { width: 180, minHeight: 70 }
    };
  });
  const edges: Edge[] = points.flatMap((point) =>
    (point.prerequisite_ids ?? [])
      .filter((source) => pointById.has(source))
      .map((source) => ({
        id: `${source}-${point.id}`,
        source,
        target: point.id,
        markerEnd: { type: MarkerType.ArrowClosed, color: "#0b8f7f" },
        style: { stroke: "#0b8f7f", strokeWidth: 1.5 }
      }))
  );
  return { nodes, edges };
}

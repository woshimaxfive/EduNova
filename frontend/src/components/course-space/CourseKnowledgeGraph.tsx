import { useMemo, useState } from "react";
import {
  Background,
  Controls,
  MarkerType,
  Position,
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
  const chapters = useMemo(
    () => [...new Set(points.map((point) => point.chapter?.trim()).filter((chapter): chapter is string => Boolean(chapter)))],
    [points]
  );
  const selectedPoint = points.find((point) => point.id === selectedId) ?? points[0] ?? null;
  const [chapterFilter, setChapterFilter] = useState(selectedPoint?.chapter ?? "");
  const effectiveChapterFilter = !chapterFilter || selectedPoint?.chapter === chapterFilter
    ? chapterFilter
    : selectedPoint?.chapter ?? "";
  const { nodes, edges, prerequisites, dependents } = useMemo(
    () => buildFocusedGraph(points, selectedPoint?.id ?? null, effectiveChapterFilter),
    [effectiveChapterFilter, points, selectedPoint?.id]
  );

  if (!selectedPoint) return null;

  function selectChapter(chapter: string) {
    setChapterFilter(chapter);
    const firstPoint = points.find((point) => (chapter ? point.chapter === chapter : true));
    if (firstPoint) onSelect(firstPoint.id);
  }

  return (
    <section className="course-knowledge-graph" role="region" aria-label="课程知识图谱">
      <div className="course-knowledge-graph-heading">
        <div>
          <strong>当前知识点关系</strong>
          <span>只展示直接先修与后续，避免图谱拥挤</span>
        </div>
        <label className="course-knowledge-graph-filter">
          <span>章节</span>
          <select value={effectiveChapterFilter} onChange={(event) => selectChapter(event.target.value)}>
            <option value="">全部章节</option>
            {chapters.map((chapter) => <option key={chapter} value={chapter}>{chapter}</option>)}
          </select>
        </label>
      </div>
      <div className="course-knowledge-graph-context" aria-label="当前图谱范围">
        <span>先修 {prerequisites.length}</span>
        <strong>{selectedPoint.title}</strong>
        <span>后续 {dependents.length}</span>
      </div>
      <div className="course-knowledge-graph-canvas">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          fitView
          fitViewOptions={{ padding: 0.16 }}
          minZoom={0.65}
          maxZoom={1.4}
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable
          onNodeClick={(_, node) => onSelect(node.id)}
          proOptions={{ hideAttribution: true }}
        >
          <Background gap={24} size={1} color="rgba(11, 143, 127, 0.09)" />
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

function buildFocusedGraph(points: CourseMasteryPoint[], selectedId: string | null, chapterFilter: string) {
  const pointById = new Map(points.map((point) => [point.id, point]));
  const selected = selectedId ? pointById.get(selectedId) ?? null : null;
  if (!selected) return { nodes: [], edges: [], prerequisites: [], dependents: [] };
  const visibleInChapter = (point: CourseMasteryPoint) => !chapterFilter || point.chapter === chapterFilter;
  const prerequisites = (selected.prerequisite_ids ?? [])
    .map((id) => pointById.get(id))
    .filter((point): point is CourseMasteryPoint => Boolean(point))
    .filter(visibleInChapter)
    .sort((a, b) => a.order_index - b.order_index);
  const dependents = points
    .filter((point) => visibleInChapter(point) && (point.prerequisite_ids ?? []).includes(selected.id))
    .sort((a, b) => a.order_index - b.order_index);
  const columns = [
    { points: prerequisites, x: 0, role: "先修" },
    { points: [selected], x: 270, role: "当前" },
    { points: dependents, x: 540, role: "后续" }
  ];
  const maxRows = Math.max(prerequisites.length, dependents.length, 1);
  const nodes: Node[] = columns.flatMap(({ points: columnPoints, x, role }) => columnPoints.map((point, index) => {
    const y = role === "当前" ? Math.max(0, ((maxRows - 1) * 112) / 2) : index * 112;
    return {
      id: point.id,
      position: { x, y },
      data: {
        label: (
          <div className="course-knowledge-node-content">
            <em>{role}</em>
            <strong>{point.title}</strong>
            <span>{statusLabels[point.status] ?? point.status} · {point.score === null ? "未评估" : `${point.score} 分`}</span>
          </div>
        )
      },
      className: `course-knowledge-node ${point.status} ${selected.id === point.id ? "selected" : ""}`,
      sourcePosition: Position.Right,
      targetPosition: Position.Left,
      style: { width: 226, minHeight: 88 }
    };
  }));
  const edges: Edge[] = [
    ...prerequisites.map((point) => ({
      id: `${point.id}-${selected.id}`,
      source: point.id,
      target: selected.id,
      markerEnd: { type: MarkerType.ArrowClosed, color: "#0b8f7f" },
      style: { stroke: "#0b8f7f", strokeWidth: 1.7 }
    })),
    ...dependents.map((point) => ({
      id: `${selected.id}-${point.id}`,
      source: selected.id,
      target: point.id,
      markerEnd: { type: MarkerType.ArrowClosed, color: "#0b8f7f" },
      style: { stroke: "#0b8f7f", strokeWidth: 1.7 }
    }))
  ];
  return { nodes, edges, prerequisites, dependents };
}

import { ArrowCounterClockwise, ArrowRight, BookOpenText, ChartLineUp, ListChecks, X } from "@phosphor-icons/react";
import {
  Background,
  Controls,
  Handle,
  Position,
  ReactFlow,
  type Edge,
  type Node,
  type NodeProps,
  type ReactFlowInstance,
  type Viewport
} from "@xyflow/react";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import "@xyflow/react/dist/style.css";

import type { CourseMasteryPoint, CourseWeaknessReviewItem } from "../../api/courses";
import type { LearningNextAction } from "../../api/learning";
import { buildCoursePracticeWorkspacePath, PATHS } from "../../app/routePaths";
import type { GraphScope } from "../../features/course-space/courseWorkspaceState";
import { learningActionHref } from "../../features/learning-actions/learningActions";
import { ModalFrame } from "../primitives/Dialog";

type CourseKnowledgeGraphProps = {
  courseId?: number;
  points: CourseMasteryPoint[];
  selectedId?: string | null;
  scope?: GraphScope;
  chapter?: string;
  detailOpen?: boolean;
  weaknesses?: CourseWeaknessReviewItem[];
  recommendation?: LearningNextAction | null;
  currentTaskPointId?: string | null;
  onSelect: (pointId: string) => void;
  onScopeChange?: (scope: GraphScope) => void;
  onChapterChange?: (chapter: string) => void;
  onDetailClose?: () => void;
  onContinue?: (pointId: string) => void;
  resourceHref?: (pointId: string) => string;
};

type KnowledgeNodeData = {
  point: CourseMasteryPoint;
  selected: boolean;
  currentTask: boolean;
  onSelect: (pointId: string) => void;
};

const statusLabels: Record<string, string> = {
  weak: "薄弱",
  learning: "学习中",
  mastered: "已掌握",
  recommended_review: "建议复习",
  not_started: "未评估"
};

const nodeTypes = { knowledge: KnowledgeFlowNode };

export function CourseKnowledgeGraph({
  courseId = 0,
  points,
  selectedId,
  scope = "focus",
  chapter = "",
  detailOpen = false,
  weaknesses = [],
  recommendation = null,
  currentTaskPointId = null,
  onSelect,
  onScopeChange,
  onChapterChange,
  onDetailClose,
  onContinue,
  resourceHref
}: CourseKnowledgeGraphProps) {
  const selectedPoint = points.find((point) => point.id === selectedId) ?? points[0] ?? null;
  const chapters = useMemo(
    () => [...new Set(points.map((point) => point.chapter?.trim()).filter((value): value is string => Boolean(value)))],
    [points]
  );
  const graph = useMemo(
    () => buildKnowledgeGraph(points, selectedPoint?.id ?? null, scope, chapter, currentTaskPointId, onSelect),
    [chapter, currentTaskPointId, onSelect, points, scope, selectedPoint?.id]
  );
  const [instance, setInstance] = useState<ReactFlowInstance<Node<KnowledgeNodeData>, Edge> | null>(null);
  const viewportKey = `edunova.course-graph.viewport.v1:${courseId}:${scope}:${chapter || "all"}`;
  const initialViewport = readViewport(viewportKey);
  const selectedWeakness = weaknesses.find((item) => item.knowledge_point_id === selectedPoint?.id) ?? null;

  useEffect(() => {
    if (!instance) return;
    const restored = readViewport(viewportKey);
    if (restored) void instance.setViewport(restored, { duration: 0 });
    else window.requestAnimationFrame(() => instance.fitView({ padding: 0.2, duration: 0 }));
  }, [instance, viewportKey]);

  if (!selectedPoint) {
    return <div className="knowledge-graph-empty"><strong>还没有知识点</strong><p>完成资料解析与建课后，这里会显示真实学习关系。</p></div>;
  }

  function resetViewport() {
    sessionStorage.removeItem(viewportKey);
    void instance?.fitView({ padding: 0.2, duration: 220 });
  }

  function selectPoint(pointId: string) {
    onSelect(pointId);
  }

  const practiceParams = selectedPoint ? new URLSearchParams({
    knowledge_point_id: selectedPoint.id,
    new: "1",
    return_to: "course",
    return_view: "graph",
    return_detail: "knowledge"
  }) : null;

  return (
    <section className="course-knowledge-graph knowledge-flow-shell" role="region" aria-label="课程知识图谱">
      <div className="course-knowledge-graph-heading knowledge-flow-heading">
        <div>
          <strong>{scope === "focus" ? "聚焦链路" : "课程全景"}</strong>
        </div>
        <div className="knowledge-flow-tools">
          <div className="knowledge-flow-segmented" aria-label="图谱范围">
            <button type="button" className={scope === "focus" ? "active" : ""} aria-pressed={scope === "focus"} onClick={() => onScopeChange?.("focus")}>聚焦链路</button>
            <button type="button" className={scope === "course" ? "active" : ""} aria-pressed={scope === "course"} onClick={() => onScopeChange?.("course")}>课程全景</button>
          </div>
          {scope === "course" ? (
            <label className="course-knowledge-graph-filter">
              <span>章节</span>
              <select value={chapter} onChange={(event) => onChapterChange?.(event.target.value)}>
                <option value="">全部章节</option>
                {chapters.map((item) => <option value={item} key={item}>{item}</option>)}
              </select>
            </label>
          ) : null}
          <button className="knowledge-flow-reset" type="button" onClick={resetViewport}>
            <ArrowCounterClockwise size={16} aria-hidden="true" />重置视图
          </button>
        </div>
      </div>

      {graph.warningCount > 0 ? <p className="knowledge-flow-warning">已安全跳过 {graph.warningCount} 条缺失或无效先修关系。</p> : null}

      <div className="knowledge-flow-canvas" aria-label={scope === "focus" ? "当前学习链路画布" : "课程全景画布"}>
        <ReactFlow<Node<KnowledgeNodeData>, Edge>
          nodes={graph.nodes.map((node) => ({ ...node, data: { ...node.data, onSelect: selectPoint } }))}
          edges={graph.edges}
          nodeTypes={nodeTypes}
          defaultViewport={initialViewport ?? { x: 0, y: 0, zoom: 0.85 }}
          minZoom={0.35}
          maxZoom={1.5}
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable
          onlyRenderVisibleElements
          proOptions={{ hideAttribution: true }}
          onInit={setInstance}
          onMoveEnd={(_event, viewport) => writeViewport(viewportKey, viewport)}
          onNodeClick={(_event, node) => selectPoint(node.id)}
          fitView={!initialViewport}
          fitViewOptions={{ padding: 0.2 }}
        >
          <Background color="rgba(41, 83, 78, 0.12)" gap={24} size={1} />
          <Controls position="bottom-right" showInteractive={false} />
        </ReactFlow>
      </div>

      <MobileKnowledgeMap points={graph.visiblePoints} selectedId={selectedPoint.id} scope={scope} onSelect={selectPoint} />

      <div className="course-knowledge-graph-legend" aria-label="知识图谱图例">
        <span className="mastered">已掌握</span><span className="learning">学习中</span><span className="weak">薄弱</span><span className="recommended_review">建议复习</span><span>未评估</span>
      </div>

      {detailOpen ? (
        <ModalFrame title="知识点详情" layerClassName="knowledge-node-drawer-layer" onClose={() => onDetailClose?.()}>
          <aside className="knowledge-node-drawer" aria-labelledby="knowledge-node-detail-title">
            <header>
              <div><span>{selectedPoint.chapter || "课程知识点"}</span><h2 id="knowledge-node-detail-title">{selectedPoint.title}</h2></div>
              <button type="button" aria-label="关闭知识点详情" onClick={() => onDetailClose?.()}><X size={20} /></button>
            </header>
            <section className="knowledge-node-score-card">
              <div><span>当前状态</span><strong>{statusLabels[selectedPoint.status] ?? selectedPoint.status}</strong></div>
              <div><span>掌握度</span><strong>{selectedPoint.score === null ? "未评估" : `${selectedPoint.score} 分`}</strong></div>
              <div><span>置信度</span><strong>{selectedPoint.confidence == null ? "待积累" : `${Math.round(selectedPoint.confidence * 100)}%`}</strong></div>
              <div><span>证据</span><strong>{selectedPoint.evidence_count ?? 0} 条</strong></div>
            </section>
            <section className="knowledge-node-diagnosis">
              <span>最近学习证据</span>
              {selectedWeakness?.diagnosis ? (
                <><strong>{selectedWeakness.diagnosis.misconception || selectedWeakness.title}</strong><p>{selectedWeakness.diagnosis.recommended_action}</p>{selectedWeakness.diagnosis.missing_concepts.length ? <small>待补概念：{selectedWeakness.diagnosis.missing_concepts.join("、")}</small> : null}</>
              ) : <><strong>尚未形成可靠弱点证据</strong><p>完成学习或练习后，系统会依据真实结果更新诊断。</p></>}
            </section>
            {recommendation ? <section className="knowledge-node-next"><span>下一最佳行动</span><strong>{recommendation.label}</strong><p>{recommendation.description}</p></section> : null}
            <nav className="knowledge-node-actions" aria-label="知识点操作">
              <button type="button" onClick={() => onContinue?.(selectedPoint.id)}><BookOpenText size={18} />继续学习<ArrowRight size={16} /></button>
              <Link to={`${buildCoursePracticeWorkspacePath(courseId)}?${practiceParams?.toString() ?? ""}`}><ListChecks size={18} />针对练习</Link>
              <Link to={resourceHref?.(selectedPoint.id) ?? `${PATHS.studio}?course_id=${courseId}&knowledge_point_id=${selectedPoint.id}`}><ChartLineUp size={18} />查看或生成资源</Link>
              {recommendation ? <Link to={learningActionHref(recommendation)}>执行推荐行动</Link> : null}
            </nav>
          </aside>
        </ModalFrame>
      ) : null}
    </section>
  );
}

function KnowledgeFlowNode({ data }: NodeProps<Node<KnowledgeNodeData>>) {
  const point = data.point;
  return (
    <button
      type="button"
      className={`knowledge-flow-node ${point.status} ${data.selected ? "selected" : ""} ${data.currentTask ? "current-task" : ""}`}
      aria-current={data.selected ? "true" : undefined}
      aria-label={`${point.title}，${statusLabels[point.status] ?? point.status}，${point.score === null ? "未评估" : `掌握度 ${point.score} 分`}`}
      onClick={(event) => { event.stopPropagation(); data.onSelect(point.id); }}
    >
      <Handle type="target" position={Position.Left} isConnectable={false} />
      <span className="knowledge-flow-node-status">{statusLabels[point.status] ?? point.status}</span>
      <strong>{point.title}</strong>
      <small>{point.score === null ? "等待学习证据" : `掌握度 ${point.score} · ${point.evidence_count ?? 0} 条证据`}</small>
      <Handle type="source" position={Position.Right} isConnectable={false} />
    </button>
  );
}

function MobileKnowledgeMap({ points, selectedId, scope, onSelect }: { points: CourseMasteryPoint[]; selectedId: string; scope: GraphScope; onSelect: (id: string) => void }) {
  return (
    <div className="knowledge-flow-mobile" aria-label={scope === "focus" ? "聚焦学习链路" : "课程章节列表"}>
      {points.map((point, index) => (
        <button type="button" key={point.id} className={`${point.status} ${point.id === selectedId ? "selected" : ""}`} onClick={() => onSelect(point.id)}>
          <span>{String(index + 1).padStart(2, "0")}</span><div><small>{point.chapter || "课程知识点"} · {statusLabels[point.status] ?? point.status}</small><strong>{point.title}</strong></div><em>{point.score === null ? "—" : point.score}</em>
        </button>
      ))}
    </div>
  );
}

// Pure graph projection is exported for deterministic relationship tests.
// eslint-disable-next-line react-refresh/only-export-components
export function buildKnowledgeGraph(
  points: CourseMasteryPoint[],
  selectedId: string | null,
  scope: GraphScope,
  chapter: string,
  currentTaskPointId: string | null,
  onSelect: (id: string) => void
) {
  const sorted = [...points].sort((left, right) => left.order_index - right.order_index);
  const pointById = new Map(sorted.map((point) => [point.id, point]));
  const selected = selectedId ? pointById.get(selectedId) ?? sorted[0] : sorted[0];
  const focusIds = new Set<string>();
  if (selected) {
    focusIds.add(selected.id);
    selected.prerequisite_ids.forEach((id) => { if (pointById.has(id)) focusIds.add(id); });
    sorted.forEach((point) => { if (point.prerequisite_ids.includes(selected.id)) focusIds.add(point.id); });
  }
  const visiblePoints = (scope === "focus" ? sorted.filter((point) => focusIds.has(point.id)) : sorted.filter((point) => !chapter || point.chapter === chapter));
  const visibleIds = new Set(visiblePoints.map((point) => point.id));
  const chapterOrder = [...new Set(visiblePoints.map((point) => point.chapter || "课程知识点"))];
  const chapterIndexes = new Map(chapterOrder.map((value, index) => [value, index]));
  const chapterRows = new Map<string, number>();
  const nodes: Node<KnowledgeNodeData>[] = visiblePoints.map((point) => {
    let position: { x: number; y: number };
    if (scope === "focus" && selected) {
      const column = point.id === selected.id ? 1 : selected.prerequisite_ids.includes(point.id) ? 0 : 2;
      const peers = visiblePoints.filter((candidate) => candidate.id === selected.id ? column === 1 : selected.prerequisite_ids.includes(candidate.id) ? column === 0 : column === 2);
      const row = Math.max(0, peers.findIndex((candidate) => candidate.id === point.id));
      position = { x: column * 330, y: row * 132 + (column === 1 ? Math.max(0, (peers.length - 1) * 54) : 0) };
    } else {
      const currentChapter = point.chapter || "课程知识点";
      const row = chapterRows.get(currentChapter) ?? 0;
      chapterRows.set(currentChapter, row + 1);
      position = { x: (chapterIndexes.get(currentChapter) ?? 0) * 300, y: row * 118 };
    }
    return { id: point.id, type: "knowledge", position, data: { point, selected: point.id === selected?.id, currentTask: point.id === currentTaskPointId, onSelect } };
  });
  let warningCount = 0;
  const edges: Edge[] = [];
  for (const point of visiblePoints) {
    for (const prerequisiteId of point.prerequisite_ids) {
      if (!pointById.has(prerequisiteId)) { warningCount += 1; continue; }
      if (!visibleIds.has(prerequisiteId)) continue;
      if (prerequisiteId === point.id) { warningCount += 1; continue; }
      edges.push({ id: `${prerequisiteId}-${point.id}`, source: prerequisiteId, target: point.id, animated: scope === "focus", className: scope === "focus" ? "learning-edge" : "" });
    }
  }
  return { nodes, edges, visiblePoints, warningCount };
}

function readViewport(key: string): Viewport | null {
  try {
    const value = sessionStorage.getItem(key);
    if (!value) return null;
    const parsed = JSON.parse(value) as Partial<Viewport>;
    return Number.isFinite(parsed.x) && Number.isFinite(parsed.y) && Number.isFinite(parsed.zoom)
      ? { x: parsed.x as number, y: parsed.y as number, zoom: parsed.zoom as number }
      : null;
  } catch { return null; }
}

function writeViewport(key: string, viewport: Viewport) {
  try { sessionStorage.setItem(key, JSON.stringify(viewport)); } catch { /* session storage may be unavailable */ }
}

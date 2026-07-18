import { useMemo, useState, type CSSProperties } from "react";

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
  const { prerequisites, dependents } = useMemo(
    () => buildFocusedGraph(points, selectedPoint?.id ?? null),
    [points, selectedPoint?.id]
  );
  const isCourseOverview = effectiveChapterFilter === "";

  if (!selectedPoint) return null;

  function selectChapter(chapter: string) {
    setChapterFilter(chapter);
    if (!chapter || selectedPoint.chapter === chapter) return;
    const firstPoint = points.find((point) => point.chapter === chapter);
    if (firstPoint) onSelect(firstPoint.id);
  }

  function selectOverviewPoint(point: CourseMasteryPoint) {
    setChapterFilter(point.chapter ?? "");
    onSelect(point.id);
  }

  return (
    <section className="course-knowledge-graph" role="region" aria-label="课程知识图谱">
      <div className="course-knowledge-graph-heading">
        <div>
          <strong>{isCourseOverview ? "课程全景" : "学习链路"}</strong>
          <span>{isCourseOverview ? "按章节浏览全部知识点，选择一个节点打开对应内容" : "从已具备的基础，连接到下一步学习"}</span>
        </div>
        <label className="course-knowledge-graph-filter">
          <span>章节</span>
          <select value={effectiveChapterFilter} onChange={(event) => selectChapter(event.target.value)}>
            <option value="">全部章节</option>
            {chapters.map((chapter) => <option key={chapter} value={chapter}>{chapter}</option>)}
          </select>
        </label>
      </div>

      {isCourseOverview ? (
        <CourseKnowledgeOverview chapters={chapters} points={points} selectedPoint={selectedPoint} onSelect={selectOverviewPoint} />
      ) : (
        <div key={selectedPoint.id} className="course-learning-chain" aria-label="当前图谱范围">
          <RelationshipColumn label="直接先修" points={prerequisites} emptyText="这是当前范围的起点" onSelect={onSelect} />
          <CurrentKnowledgePoint point={selectedPoint} />
          <RelationshipColumn label="即将解锁" points={dependents} emptyText="继续学习将解锁更多内容" onSelect={onSelect} />
        </div>
      )}

      <div className="course-knowledge-graph-legend" aria-label="知识图谱图例">
        <span className="weak">薄弱</span>
        <span className="learning">学习中</span>
        <span className="mastered">已掌握</span>
        <span>未开始</span>
      </div>
    </section>
  );
}

function CourseKnowledgeOverview({
  chapters,
  points,
  selectedPoint,
  onSelect
}: {
  chapters: string[];
  points: CourseMasteryPoint[];
  selectedPoint: CourseMasteryPoint;
  onSelect: (point: CourseMasteryPoint) => void;
}) {
  return (
    <div className="course-knowledge-overview" aria-label="课程全部知识点">
      {chapters.map((chapter, chapterIndex) => {
        const chapterPoints = points.filter((point) => point.chapter === chapter).sort((a, b) => a.order_index - b.order_index);
        const chapterStyle = { "--chapter-index": chapterIndex } as CSSProperties;
        return (
          <section key={chapter} className="course-knowledge-overview-chapter" style={chapterStyle} aria-label={`${chapter}知识点`}>
            <div className="course-knowledge-overview-chapter-heading">
              <span>{String(chapterIndex + 1).padStart(2, "0")}</span>
              <div>
                <strong>{chapter}</strong>
                <small>{chapterPoints.length} 个知识点</small>
              </div>
            </div>
            <div className="course-knowledge-overview-points">
              {chapterPoints.map((point) => (
                <button
                  key={point.id}
                  className={`course-knowledge-overview-point ${point.status} ${selectedPoint.id === point.id ? "selected" : ""}`}
                  type="button"
                  aria-current={selectedPoint.id === point.id ? "true" : undefined}
                  onClick={() => onSelect(point)}
                >
                  <span>{point.order_index + 1}</span>
                  <strong>{point.title}</strong>
                  <em>{statusLabels[point.status] ?? point.status}</em>
                </button>
              ))}
            </div>
          </section>
        );
      })}
    </div>
  );
}

function RelationshipColumn({
  label,
  points,
  emptyText,
  onSelect
}: {
  label: string;
  points: CourseMasteryPoint[];
  emptyText: string;
  onSelect: (pointId: string) => void;
}) {
  return (
    <div className="course-learning-chain-column">
      <div className="course-learning-chain-column-heading">
        <span>{label}</span>
        <strong>{points.length}</strong>
      </div>
      {points.length > 0 ? (
        <div className="course-learning-chain-list">
          {points.map((point) => (
            <button
              key={point.id}
              className={`course-learning-chain-node ${point.status}`}
              type="button"
              onClick={() => onSelect(point.id)}
            >
              <span>{statusLabels[point.status] ?? point.status}</span>
              <strong>{point.title}</strong>
              <small>{point.score === null ? "未评估" : `${point.score} 分`}</small>
            </button>
          ))}
        </div>
      ) : <p className="course-learning-chain-empty">{emptyText}</p>}
    </div>
  );
}

function CurrentKnowledgePoint({ point }: { point: CourseMasteryPoint }) {
  const progress = getKnowledgeProgress(point);
  const progressStyle = { "--knowledge-progress": `${progress}%` } as CSSProperties;

  return (
    <article className={`course-learning-focus ${point.status}`} aria-label={`当前知识点：${point.title}`}>
      <div className="course-learning-focus-eyebrow">
        <span>当前学习焦点</span>
        <em>{statusLabels[point.status] ?? point.status}</em>
      </div>
      <strong>{point.title}</strong>
      <div className="course-learning-progress" style={progressStyle} aria-label={`掌握度 ${progress}%`}>
        <span />
      </div>
      <div className="course-learning-focus-meta">
        <span>掌握度</span>
        <strong>{point.score === null ? "未评估" : `${point.score} 分`}</strong>
      </div>
    </article>
  );
}

function buildFocusedGraph(points: CourseMasteryPoint[], selectedId: string | null) {
  const pointById = new Map(points.map((point) => [point.id, point]));
  const selected = selectedId ? pointById.get(selectedId) ?? null : null;
  if (!selected) return { prerequisites: [], dependents: [] };
  const prerequisites = (selected.prerequisite_ids ?? [])
    .map((id) => pointById.get(id))
    .filter((point): point is CourseMasteryPoint => Boolean(point))
    .sort((a, b) => a.order_index - b.order_index);
  const dependents = points
    .filter((point) => (point.prerequisite_ids ?? []).includes(selected.id))
    .sort((a, b) => a.order_index - b.order_index);
  return { prerequisites, dependents };
}

function getKnowledgeProgress(point: CourseMasteryPoint) {
  if (point.score !== null) return Math.min(100, Math.max(0, point.score));
  return ({ mastered: 100, learning: 50, weak: 30, recommended_review: 35 } as Record<string, number>)[point.status] ?? 0;
}

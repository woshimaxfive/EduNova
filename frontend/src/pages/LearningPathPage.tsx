import { ArrowRight, CheckCircle, Compass, FileText, Sparkle, Target } from "@phosphor-icons/react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type ChangeEvent, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { buildCoursePath } from "../app/routePaths";
import { getMasteryMap, listCourses, type CourseMasteryPoint, type CourseMasteryStatus } from "../api/courses";
import {
  generatePath,
  getCurrentPath,
  updatePathTask,
  type GeneratePathRequest,
  type LearningPathTask,
  type PathTaskStatus
} from "../api/paths";
import { InlineFeedback } from "../components/feedback/InlineFeedback";
import { PageFrame } from "./PageFrame";

const durationOptions: Array<{ label: string; value: GeneratePathRequest["duration_days"] }> = [
  { label: "3 天", value: 3 },
  { label: "7 天", value: 7 },
  { label: "14 天", value: 14 }
];

function parseCourseId(value: string | null) {
  if (!value) {
    return null;
  }

  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) ? parsed : null;
}

function taskStatusLabel(status: PathTaskStatus) {
  if (status === "doing") {
    return "进行中";
  }
  if (status === "completed") {
    return "已完成";
  }
  return "待开始";
}

function taskAction(task: LearningPathTask): { label: string; status: PathTaskStatus } | null {
  if (task.status === "todo") {
    return { label: `开始 ${task.title}`, status: "doing" };
  }
  if (task.status === "doing") {
    return { label: `完成 ${task.title}`, status: "completed" };
  }
  return null;
}

function masteryStatusLabel(status: CourseMasteryStatus) {
  if (status === "weak") {
    return "薄弱";
  }
  if (status === "learning") {
    return "学习中";
  }
  if (status === "mastered") {
    return "已掌握";
  }
  if (status === "recommended_review") {
    return "建议复习";
  }
  return "未开始";
}

function formatDateTime(value: string | null) {
  if (!value) {
    return "未安排";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleDateString("zh-CN", {
    month: "2-digit",
    day: "2-digit"
  });
}

export function LearningPathPage() {
  const queryClient = useQueryClient();
  const [searchParams] = useSearchParams();
  const queryCourseId = parseCourseId(searchParams.get("course_id"));
  const [selectedCourseId, setSelectedCourseId] = useState<number | null>(queryCourseId);
  const [durationDays, setDurationDays] = useState<GeneratePathRequest["duration_days"]>(7);
  const [goal, setGoal] = useState("");
  const [localFeedback, setLocalFeedback] = useState<string | null>(null);

  const coursesQuery = useQuery({
    queryKey: ["courses", "list"],
    queryFn: () => listCourses(),
    staleTime: 30_000
  });
  const courses = useMemo(() => coursesQuery.data?.data ?? [], [coursesQuery.data?.data]);
  const firstCourseId = courses[0] ? Number.parseInt(courses[0].id, 10) : null;
  const effectiveCourseId = selectedCourseId ?? queryCourseId ?? firstCourseId;
  const hasCourse = effectiveCourseId !== null && Number.isFinite(effectiveCourseId);

  const currentPathQuery = useQuery({
    queryKey: ["paths", "current", effectiveCourseId],
    queryFn: () => getCurrentPath(effectiveCourseId ?? 0),
    enabled: hasCourse,
    staleTime: 10_000
  });
  const masteryQuery = useQuery({
    queryKey: ["courses", "mastery-map", effectiveCourseId],
    queryFn: () => getMasteryMap(effectiveCourseId ?? 0),
    enabled: hasCourse,
    staleTime: 10_000
  });

  const selectedCourse = useMemo(
    () => courses.find((course) => Number.parseInt(course.id, 10) === effectiveCourseId) ?? null,
    [courses, effectiveCourseId]
  );
  const pathDetail = currentPathQuery.data?.data ?? null;
  const tasks = pathDetail?.tasks ?? [];
  const evidenceBasis = pathDetail?.evidence_summary.basis ?? [];
  const masteryMap = masteryQuery.data?.data ?? null;
  const hasPath = Boolean(pathDetail?.path);
  const hasReadError = coursesQuery.isError || currentPathQuery.isError || masteryQuery.isError;

  const generateMutation = useMutation({
    mutationFn: (payload: GeneratePathRequest) => generatePath(payload),
    onSuccess: (result, payload) => {
      setLocalFeedback(null);
      queryClient.setQueryData(["paths", "current", payload.course_id], result);
      void queryClient.invalidateQueries({ queryKey: ["paths", "current", payload.course_id] });
      void queryClient.invalidateQueries({ queryKey: ["courses", "mastery-map", payload.course_id] });
      void queryClient.invalidateQueries({ queryKey: ["courses", "learning-state", payload.course_id] });
    },
    onError: () => {
      setLocalFeedback("学习路径生成失败，请稍后重试。");
    }
  });
  const updateTaskMutation = useMutation({
    mutationFn: ({ taskId, status }: { taskId: number; status: PathTaskStatus }) => updatePathTask(taskId, { status }),
    onSuccess: () => {
      setLocalFeedback(null);
      if (effectiveCourseId !== null) {
        void queryClient.invalidateQueries({ queryKey: ["paths", "current", effectiveCourseId] });
        void queryClient.invalidateQueries({ queryKey: ["courses", "mastery-map", effectiveCourseId] });
        void queryClient.invalidateQueries({ queryKey: ["courses", "learning-state", effectiveCourseId] });
      }
    },
    onError: () => {
      setLocalFeedback("任务状态更新失败，请稍后重试。");
    }
  });

  function handleCourseChange(event: ChangeEvent<HTMLSelectElement>) {
    setSelectedCourseId(parseCourseId(event.target.value));
    setLocalFeedback(null);
  }

  function handleDurationChange(event: ChangeEvent<HTMLSelectElement>) {
    const value = Number.parseInt(event.target.value, 10);
    if (value === 3 || value === 7 || value === 14) {
      setDurationDays(value);
    }
  }

  function submitGeneratePath() {
    if (effectiveCourseId === null || !hasCourse || generateMutation.isPending) {
      return;
    }

    generateMutation.mutate({
      course_id: effectiveCourseId,
      duration_days: durationDays,
      goal: goal.trim()
    });
  }

  function submitTaskStatus(task: LearningPathTask, status: PathTaskStatus) {
    const taskId = Number.parseInt(task.id, 10);
    if (!Number.isFinite(taskId) || updateTaskMutation.isPending) {
      return;
    }

    updateTaskMutation.mutate({ taskId, status });
  }

  return (
    <PageFrame title="学习路径">
      <div className="student-workspace learning-path-workspace">
        <section className="student-panel path-stage-panel" role="region" aria-label="阶段任务">
          <div className="student-panel-heading">
            <div>
              <h2>课程路径</h2>
            </div>
            <span className="panel-count">
              <Target size={17} weight="duotone" aria-hidden="true" />
              {tasks.length} 任务
            </span>
          </div>

          <div className="path-control-row">
            <label>
              <span>课程</span>
              <select value={effectiveCourseId ?? ""} onChange={handleCourseChange} disabled={courses.length === 0}>
                {courses.length === 0 ? (
                  <option value="">暂无课程</option>
                ) : (
                  courses.map((course) => (
                    <option key={course.id} value={course.id}>
                      {course.title}
                    </option>
                  ))
                )}
              </select>
            </label>
            <label>
              <span>周期</span>
              <select value={durationDays} onChange={handleDurationChange}>
                {durationOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="path-goal-input">
              <span>目标</span>
              <input value={goal} placeholder="可选" onChange={(event) => setGoal(event.target.value)} />
            </label>
            <button className="primary-action" type="button" disabled={!hasCourse || generateMutation.isPending} onClick={submitGeneratePath}>
              <span>{generateMutation.isPending ? "生成中" : "生成学习路径"}</span>
              <ArrowRight size={17} weight="bold" aria-hidden="true" />
            </button>
          </div>

          <InlineFeedback
            message={hasReadError ? "学习路径数据读取失败，请稍后重试。" : localFeedback}
            tone="warning"
          />

          {pathDetail && hasPath ? (
            <div className="path-current-summary">
              <strong>{pathDetail.message}</strong>
              <span>{selectedCourse ? selectedCourse.title : `课程 ${pathDetail.course_id}`}</span>
            </div>
          ) : currentPathQuery.isPending && hasCourse ? (
            <p className="path-empty-state">正在读取学习路径。</p>
          ) : null}

          {hasPath && tasks.length > 0 ? (
            <ol className="path-stage-list">
              {tasks.map((task, index) => {
                const action = taskAction(task);

                return (
                  <li className={task.status === "doing" ? "active" : ""} key={task.id}>
                    <span className="path-stage-index">{index + 1}</span>
                    <div className="path-stage-content">
                      <span className="path-stage-meta">
                        {taskStatusLabel(task.status)} · 截止 {formatDateTime(task.due_at)}
                      </span>
                      <strong>{task.title}</strong>
                      <ul>
                        <li>
                          <CheckCircle size={15} weight="duotone" aria-hidden="true" />
                          <span>{task.reason}</span>
                        </li>
                        {task.recommended_resources.map((resource) => (
                          <li key={resource.id}>
                            <FileText size={15} weight="duotone" aria-hidden="true" />
                            <span>{resource.title}</span>
                          </li>
                        ))}
                      </ul>
                      <span className="path-stage-source">
                        <Sparkle size={15} weight="duotone" aria-hidden="true" />
                        {task.task_type === "review" ? "弱点复习" : task.task_type === "resource" ? "资源学习" : "知识点学习"}
                      </span>
                    </div>
                    {action ? (
                      <button
                        className="path-task-action"
                        type="button"
                        disabled={updateTaskMutation.isPending}
                        onClick={() => submitTaskStatus(task, action.status)}
                      >
                        {action.label}
                      </button>
                    ) : (
                      <span className="path-stage-status">已完成</span>
                    )}
                  </li>
                );
              })}
            </ol>
          ) : pathDetail && !hasReadError ? (
            <p className="path-empty-state">学习路径尚未生成。</p>
          ) : null}
        </section>

        <aside className="path-side-stack">
          <section className="student-panel path-evidence-panel" role="region" aria-label="路径依据">
            <div className="student-panel-heading compact">
              <div>
                <h2>路径依据</h2>
              </div>
            </div>
            <ul className="path-evidence-list">
              {(evidenceBasis.length > 0 ? evidenceBasis : ["暂无可展示依据。"]).map((item) => (
                <li key={item}>
                  <Sparkle size={17} weight="duotone" aria-hidden="true" />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </section>

          <section className="student-panel mastery-map-panel" role="region" aria-label="掌握度图">
            <div className="student-panel-heading compact">
              <div>
                <h2>掌握度图</h2>
              </div>
            </div>
            {masteryMap && masteryMap.points.length > 0 ? (
              <div className="mastery-map-list">
                {masteryMap.points.map((point: CourseMasteryPoint) => (
                  <article key={point.id} className={`mastery-map-point ${point.status}`}>
                    <div>
                      <strong>{point.title}</strong>
                      <span>{point.chapter ?? "未分章"}</span>
                    </div>
                    <em>{masteryStatusLabel(point.status)}</em>
                    <div className="mastery-score-bar" aria-label={`${point.title} 掌握度 ${point.score}`}>
                      <span style={{ width: `${point.score}%` }} />
                    </div>
                  </article>
                ))}
              </div>
            ) : masteryQuery.isPending && hasCourse ? (
              <p className="path-empty-state">正在读取掌握度图。</p>
            ) : (
              <p className="path-empty-state">暂无掌握度数据。</p>
            )}
          </section>

          <section className="student-panel path-action-panel" role="region" aria-label="下一步行动">
            <Compass size={26} weight="duotone" aria-hidden="true" />
            <div>
              <span className="path-action-eyebrow">下一步行动</span>
              <strong>{tasks.find((task) => task.status === "doing") ? "继续当前路径" : "先生成课程路径。"}</strong>
              <p>{hasPath ? "完成当前任务后，掌握度图会按规则刷新。" : "路径会优先安排已确认和复习中的薄弱点。"}</p>
            </div>
            {effectiveCourseId !== null ? (
              <Link className="primary-action" to={buildCoursePath(effectiveCourseId)}>
                <span>回到课程</span>
                <ArrowRight size={17} weight="bold" aria-hidden="true" />
              </Link>
            ) : null}
          </section>
        </aside>
      </div>
    </PageFrame>
  );
}

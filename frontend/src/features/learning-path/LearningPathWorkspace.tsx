import {
  ChartBar,
  Check,
  CheckCircle,
  CirclesThreePlus,
  FileText,
  Info,
  ListChecks,
  Play,
  Sparkle,
  X
} from "@phosphor-icons/react";
import { type ChangeEvent, type ReactNode } from "react";

import type { CourseMasteryPoint, CourseMasteryStatus } from "../../api/courses";
import type { LearningPathDetail, LearningPathTask, PathTaskStatus } from "../../api/paths";
import { AgentTraceDisclosure } from "../../components/evidence/AgentTraceDisclosure";
import { ModalFrame } from "../../components/primitives/Dialog";
import { InlineFeedback } from "../../components/feedback/InlineFeedback";
import { MasteryOverviewChart } from "../../components/visualization/LearningCharts";

export type PathTaskFilter = "all" | PathTaskStatus;
export type PathDetailTab = "mastery" | "evidence" | "trace";

type CourseOption = {
  id: string;
  title: string;
};

type LearningPathToolbarProps = {
  returnLink: ReactNode;
  courses: CourseOption[];
  courseId: number | null;
  courseTitle: string;
  completedCount: number;
  totalCount: number;
  hasPlan: boolean;
  generatePending: boolean;
  onCourseChange: (event: ChangeEvent<HTMLSelectElement>) => void;
  onGenerate: () => void;
  onOpenDetails: () => void;
};

export function LearningPathToolbar({
  returnLink,
  courses,
  courseId,
  courseTitle,
  completedCount,
  totalCount,
  hasPlan,
  generatePending,
  onCourseChange,
  onGenerate,
  onOpenDetails
}: LearningPathToolbarProps) {
  const progressPercent = totalCount > 0 ? Math.round((completedCount / totalCount) * 100) : 0;

  return (
    <header className="path-workspace-toolbar">
      <div className="path-toolbar-identity">
        {returnLink ? <div className="path-toolbar-return">{returnLink}</div> : null}
        <div>
          <span>学习路径</span>
          <strong>个性化学习安排</strong>
        </div>
      </div>

      <label className="path-course-select">
        <span>当前课程</span>
        <select value={courseId ?? ""} onChange={onCourseChange} disabled={courses.length === 0}>
          {courses.length === 0 ? <option value="">暂无课程</option> : null}
          {courses.map((course) => (
            <option key={course.id} value={course.id}>{course.title}</option>
          ))}
        </select>
      </label>

      <div className="path-toolbar-progress" aria-label={`${courseTitle}完成进度 ${progressPercent}%`}>
        <span>学习进度</span>
        <strong>{completedCount}/{totalCount} 已完成</strong>
        <div><span style={{ width: `${progressPercent}%` }} /></div>
      </div>

      <div className="path-toolbar-actions">
        <button className={hasPlan ? "soft-button" : "primary-action"} type="button" disabled={courseId === null || generatePending} onClick={onGenerate}>
          <Sparkle size={17} weight="duotone" aria-hidden="true" />
          {generatePending ? "正在规划" : hasPlan ? "更新学习路径" : "生成学习路径"}
        </button>
        <button className="soft-button" type="button" disabled={!hasPlan} onClick={onOpenDetails}>
          <Info size={17} weight="duotone" aria-hidden="true" />
          路径详情
        </button>
      </div>
    </header>
  );
}

type PathStatusRailProps = {
  filter: PathTaskFilter;
  tasks: LearningPathTask[];
  onChange: (filter: PathTaskFilter) => void;
};

export function PathStatusRail({ filter, tasks, onChange }: PathStatusRailProps) {
  const items: Array<{ value: PathTaskFilter; label: string }> = [
    { value: "all", label: "全部任务" },
    { value: "doing", label: "进行中" },
    { value: "todo", label: "待开始" },
    { value: "completed", label: "已完成" }
  ];

  return (
    <nav className="path-workspace-rail" aria-label="任务状态">
      <div className="path-rail-heading">
        <span>任务状态</span>
        <strong>{tasks.length}</strong>
      </div>
      {items.map((item) => {
        const count = item.value === "all" ? tasks.length : tasks.filter((task) => task.status === item.value).length;
        return (
          <button key={item.value} type="button" aria-current={filter === item.value ? "page" : undefined} onClick={() => onChange(item.value)}>
            <span>{item.label}</span>
            <small>{count}</small>
          </button>
        );
      })}
    </nav>
  );
}

function taskStatusLabel(status: PathTaskStatus) {
  if (status === "doing") return "进行中";
  if (status === "completed") return "已完成";
  return "待开始";
}

function taskTypeLabel(taskType: string) {
  if (taskType === "review") return "弱点复习";
  if (taskType === "resource") return "资源学习";
  return "知识点学习";
}

type PathTaskCanvasProps = {
  pathDetail: LearningPathDetail | null;
  tasks: LearningPathTask[];
  filter: PathTaskFilter;
  isPending: boolean;
  errorMessage: string | null;
  mutationPending: boolean;
  onGenerate: () => void;
  onUpdateTask: (task: LearningPathTask, status: PathTaskStatus) => void;
};

export function PathTaskCanvas({
  pathDetail,
  tasks,
  filter,
  isPending,
  errorMessage,
  mutationPending,
  onGenerate,
  onUpdateTask
}: PathTaskCanvasProps) {
  const currentTask = tasks.find((task) => task.status === "doing") ?? tasks.find((task) => task.status === "todo") ?? null;
  const filteredTasks = tasks.filter((task) => filter === "all" || task.status === filter);
  const visibleTasks = filter === "all" && currentTask
    ? [currentTask, ...filteredTasks.filter((task) => task.id !== currentTask.id)]
    : filteredTasks;

  if (isPending && !pathDetail) {
    return <div className="path-workspace-state"><span className="path-state-spinner" />正在读取学习路径</div>;
  }

  if (!pathDetail?.path) {
    return (
      <div className="path-workspace-state path-workspace-empty">
        <ListChecks size={34} weight="duotone" aria-hidden="true" />
        <strong>还没有个性化学习路径</strong>
        <p>系统会根据课程知识点、学习画像、掌握度和薄弱点确定学习顺序。</p>
        <button className="primary-action" type="button" disabled={mutationPending} onClick={onGenerate}>
          {mutationPending ? "正在规划" : "一键生成学习路径"}
        </button>
        <InlineFeedback message={errorMessage} tone="warning" />
      </div>
    );
  }

  return (
    <section className="path-task-canvas" aria-label="个性化路径任务">
      <header className="path-canvas-heading">
        <h2>{filter === "all" ? "学习任务" : taskStatusLabel(filter as PathTaskStatus)}</h2>
        <small>{pathDetail.message}</small>
      </header>
      {pathDetail.path.plan_json.trigger === "assessment" ? (
        <div className="path-reflow-band">
          <Sparkle size={17} weight="duotone" aria-hidden="true" />
          <span>由练习结果更新 · 保留 {Number(pathDetail.path.plan_json.preserved_task_count ?? 0)} 个既有任务</span>
        </div>
      ) : null}
      {pathDetail.path.personalization?.status === "stale" ? (
        <div className="path-reflow-band">
          <Sparkle size={17} weight="duotone" aria-hidden="true" />
          <span>学习画像已变化，可更新学习路径以应用新的安排依据。</span>
        </div>
      ) : null}
      <InlineFeedback message={errorMessage} tone="warning" />
      {visibleTasks.length === 0 ? (
        <div className="path-filter-empty">当前筛选下没有任务。</div>
      ) : (
        <ol className="path-task-list">
          {visibleTasks.map((task, index) => {
            const isCurrent = task.id === currentTask?.id && task.status !== "completed";
            const nextStatus: PathTaskStatus | null = task.status === "todo" ? "doing" : task.status === "doing" ? "completed" : null;
            return (
              <li key={task.id} className={isCurrent ? "current" : task.status}>
                <div className="path-task-marker">
                  {task.status === "completed" ? <Check size={16} weight="bold" aria-hidden="true" /> : <span>{index + 1}</span>}
                </div>
                <article>
                  <div className="path-task-meta">
                    <span>{taskStatusLabel(task.status)}</span>
                    <span>{taskTypeLabel(task.task_type)}</span>
                    {isCurrent ? <b>当前任务</b> : null}
                  </div>
                  <h3>{task.title}</h3>
                  <p>{task.reason}</p>
                  {task.learning_bundle?.items.length ? (
                    <section className="path-learning-bundle" aria-label="个性化学习包">
                      <strong>推荐学习包</strong>
                      <p>{task.learning_bundle.rationale}</p>
                      <div>
                        {task.learning_bundle.items.map((item, itemIndex) => (
                          <span key={`${item.resource_type}-${itemIndex}`}>
                            {item.resource_type} · {item.role}{item.resource_id ? " · 已就绪" : " · 待生成"}
                          </span>
                        ))}
                      </div>
                    </section>
                  ) : null}
                  {task.recommended_resources.length > 0 ? (
                    <div className="path-task-resources" aria-label="推荐资源">
                      {task.recommended_resources.map((resource) => (
                        <span key={resource.id}><FileText size={14} aria-hidden="true" />{resource.title}</span>
                      ))}
                    </div>
                  ) : null}
                </article>
                {nextStatus ? (
                  <button className={task.status === "doing" ? "primary-action" : "soft-button"} type="button" disabled={mutationPending} onClick={() => onUpdateTask(task, nextStatus)}>
                    {task.status === "doing" ? <CheckCircle size={17} weight="duotone" aria-hidden="true" /> : <Play size={17} weight="duotone" aria-hidden="true" />}
                    {task.status === "doing" ? "标记完成" : "开始学习"}
                  </button>
                ) : <span className="path-task-complete"><CheckCircle size={17} weight="fill" aria-hidden="true" />已完成</span>}
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}

function masteryStatusLabel(status: CourseMasteryStatus) {
  if (status === "weak") return "薄弱";
  if (status === "learning") return "学习中";
  if (status === "mastered") return "已掌握";
  if (status === "recommended_review") return "建议复习";
  return "未开始";
}

type LearningPathDrawerProps = {
  detailTab: PathDetailTab;
  courseTitle: string;
  pathDetail: LearningPathDetail | null;
  masteryPoints: CourseMasteryPoint[];
  onClose: () => void;
  onDetailTabChange: (tab: PathDetailTab) => void;
};

export function LearningPathDrawer({
  detailTab,
  courseTitle,
  pathDetail,
  masteryPoints,
  onClose,
  onDetailTabChange
}: LearningPathDrawerProps) {
  const evidence = pathDetail?.evidence_summary.basis ?? [];
  const traceId = pathDetail?.agent_trace_id;

  return (
    <ModalFrame title="路径详情" layerClassName="path-drawer-layer" testId="path-drawer-layer" onClose={onClose}>
      <aside className="path-drawer" aria-label="路径详情">
        <header className="path-drawer-header">
          <div><h2>路径详情</h2><small>{courseTitle}</small></div>
          <button type="button" aria-label="关闭" onClick={onClose}><X size={18} aria-hidden="true" /></button>
        </header>

        <div className="path-drawer-scroll">
          <div className="path-detail-tabs" role="tablist" aria-label="路径详情分类">
            <button type="button" role="tab" aria-selected={detailTab === "mastery"} onClick={() => onDetailTabChange("mastery")}><ChartBar size={16} aria-hidden="true" />掌握度</button>
            <button type="button" role="tab" aria-selected={detailTab === "evidence"} onClick={() => onDetailTabChange("evidence")}><FileText size={16} aria-hidden="true" />规划依据</button>
            <button type="button" role="tab" aria-selected={detailTab === "trace"} onClick={() => onDetailTabChange("trace")}><CirclesThreePlus size={16} aria-hidden="true" />协作轨迹</button>
          </div>
          {detailTab === "mastery" ? (
            <div className="path-detail-panel" role="tabpanel">
              {masteryPoints.length > 0 ? <><MasteryOverviewChart points={masteryPoints} /><div className="path-mastery-list">{masteryPoints.map((point) => <article key={point.id}><div><strong>{point.title}</strong><span>{point.chapter ?? "未分章"}</span></div><em>{masteryStatusLabel(point.status)} · {point.score === null ? "未评估" : `${point.score} 分`}</em><div><span style={{ width: `${point.score ?? 0}%` }} /></div></article>)}</div></> : <p className="path-drawer-empty">暂无掌握度数据。</p>}
            </div>
          ) : null}
          {detailTab === "evidence" ? (
            <div className="path-detail-panel" role="tabpanel">
              <div className="path-plan-metadata">
                <span>{pathDetail?.path?.goal || "暂无学习路径"}</span>
                {pathDetail?.path ? (
                  <strong>
                    {String(pathDetail.path.plan_json.generation_mode ?? "deterministic_source") === "model_enhanced" ? "模型增强" : "规则底稿"}
                    {" · "}
                    {String(pathDetail.path.plan_json.review_mode ?? "rules_only") === "model_and_rules" ? "模型与规则审核" : "规则审核"}
                  </strong>
                ) : null}
              </div>
              <ul className="path-detail-evidence">{(evidence.length > 0 ? evidence : ["暂无可展示依据。"]).map((item) => <li key={item}><Sparkle size={16} weight="duotone" aria-hidden="true" /><span>{item}</span></li>)}</ul>
            </div>
          ) : null}
          {detailTab === "trace" ? (
            <div className="path-detail-panel" role="tabpanel">
              {traceId ? <AgentTraceDisclosure traceId={traceId} label="查看 PathPlanningGraph" /> : <p className="path-drawer-empty">当前路径没有可展示的协作轨迹。</p>}
            </div>
          ) : null}
        </div>
      </aside>
    </ModalFrame>
  );
}

export function WorkspacePane({ rail, children }: { rail: ReactNode; children: ReactNode }) {
  return <div className="path-workspace-body">{rail}<main className="path-workspace-main">{children}</main></div>;
}

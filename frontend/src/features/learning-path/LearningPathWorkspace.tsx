import {
  ArrowRight,
  CalendarBlank,
  ChartBar,
  Check,
  CheckCircle,
  CirclesThreePlus,
  Clock,
  FileText,
  Info,
  ListChecks,
  Play,
  Sparkle,
  Target,
  X
} from "@phosphor-icons/react";
import { type ChangeEvent, type ReactNode } from "react";
import { Link } from "react-router-dom";

import type { CourseMasteryPoint, CourseMasteryStatus } from "../../api/courses";
import type { ExamSprintDailyTask, ExamSprintPlan } from "../../api/examSprint";
import type { MaterialComparisonResult } from "../../api/materials";
import type { LearningPathDetail, LearningPathTask, PathTaskStatus } from "../../api/paths";
import { AgentTraceDisclosure } from "../../components/evidence/AgentTraceDisclosure";
import { InlineFeedback } from "../../components/feedback/InlineFeedback";
import { MasteryOverviewChart } from "../../components/visualization/LearningCharts";

export type LearningPathView = "path" | "sprint";
export type PathTaskFilter = "all" | PathTaskStatus;
export type PathDrawerMode = "generate" | "details";
export type PathDetailTab = "mastery" | "evidence" | "trace";

type CourseOption = {
  id: string;
  title: string;
};

type LearningPathToolbarProps = {
  courses: CourseOption[];
  courseId: number | null;
  courseTitle: string;
  view: LearningPathView;
  completedCount: number;
  totalCount: number;
  hasPlan: boolean;
  onCourseChange: (event: ChangeEvent<HTMLSelectElement>) => void;
  onViewChange: (view: LearningPathView) => void;
  onOpenGenerate: () => void;
  onOpenDetails: () => void;
};

export function LearningPathToolbar({
  courses,
  courseId,
  courseTitle,
  view,
  completedCount,
  totalCount,
  hasPlan,
  onCourseChange,
  onViewChange,
  onOpenGenerate,
  onOpenDetails
}: LearningPathToolbarProps) {
  const progressPercent = totalCount > 0 ? Math.round((completedCount / totalCount) * 100) : 0;

  return (
    <header className="path-workspace-toolbar">
      <label className="path-course-select">
        <span>当前课程</span>
        <select value={courseId ?? ""} onChange={onCourseChange} disabled={courses.length === 0}>
          {courses.length === 0 ? <option value="">暂无课程</option> : null}
          {courses.map((course) => (
            <option key={course.id} value={course.id}>{course.title}</option>
          ))}
        </select>
      </label>

      <div className="path-view-switch" role="tablist" aria-label="路径模式">
        <button type="button" role="tab" aria-selected={view === "path"} onClick={() => onViewChange("path")}>
          <ListChecks size={17} weight="duotone" aria-hidden="true" />
          个性化路径
        </button>
        <button type="button" role="tab" aria-selected={view === "sprint"} onClick={() => onViewChange("sprint")}>
          <Target size={17} weight="duotone" aria-hidden="true" />
          期末冲刺
        </button>
      </div>

      <div className="path-toolbar-progress" aria-label={`${courseTitle}完成进度 ${progressPercent}%`}>
        <span>{completedCount}/{totalCount} 已完成</span>
        <div><span style={{ width: `${progressPercent}%` }} /></div>
      </div>

      <div className="path-toolbar-actions">
        <button className="soft-button" type="button" onClick={onOpenGenerate}>
          <Sparkle size={17} weight="duotone" aria-hidden="true" />
          {hasPlan ? "重新规划" : "生成计划"}
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

function formatDate(value: string | null) {
  if (!value) return "未安排";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString("zh-CN", { month: "2-digit", day: "2-digit" });
}

type PathTaskCanvasProps = {
  pathDetail: LearningPathDetail | null;
  tasks: LearningPathTask[];
  filter: PathTaskFilter;
  isPending: boolean;
  errorMessage: string | null;
  mutationPending: boolean;
  onOpenGenerate: () => void;
  onUpdateTask: (task: LearningPathTask, status: PathTaskStatus) => void;
};

export function PathTaskCanvas({
  pathDetail,
  tasks,
  filter,
  isPending,
  errorMessage,
  mutationPending,
  onOpenGenerate,
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
        <p>根据课程知识点、弱点和练习证据安排下一步学习任务。</p>
        <button className="primary-action" type="button" onClick={onOpenGenerate}>生成学习路径</button>
        <InlineFeedback message={errorMessage} tone="warning" />
      </div>
    );
  }

  return (
    <section className="path-task-canvas" aria-label="个性化路径任务">
      <header className="path-canvas-heading">
        <div>
          <span>{pathDetail.path.goal || "按当前学习状态持续推进"}</span>
          <h2>{filter === "all" ? "学习任务" : taskStatusLabel(filter as PathTaskStatus)}</h2>
        </div>
        <small>{pathDetail.message}</small>
      </header>
      {pathDetail.path.plan_json.trigger === "assessment" ? (
        <div className="path-reflow-band">
          <Sparkle size={17} weight="duotone" aria-hidden="true" />
          <span>由练习结果更新 · 保留 {Number(pathDetail.path.plan_json.preserved_task_count ?? 0)} 个既有任务</span>
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
                    <span><Clock size={14} aria-hidden="true" />截止 {formatDate(task.due_at)}</span>
                    {isCurrent ? <b>当前任务</b> : null}
                  </div>
                  <h3>{task.title}</h3>
                  <p>{task.reason}</p>
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

type SprintDayRailProps = {
  days: Array<[number, ExamSprintDailyTask[]]>;
  selectedDay: number;
  onChange: (day: number) => void;
};

export function SprintDayRail({ days, selectedDay, onChange }: SprintDayRailProps) {
  return (
    <nav className="path-workspace-rail sprint-day-rail" aria-label="冲刺日期">
      <div className="path-rail-heading"><span>冲刺日程</span><strong>{days.length}</strong></div>
      {days.map(([day, tasks]) => (
        <button key={day} type="button" aria-current={selectedDay === day ? "page" : undefined} onClick={() => onChange(day)}>
          <span>第 {day} 天</span>
          <small>{tasks.filter((task) => task.status === "completed").length}/{tasks.length}</small>
        </button>
      ))}
    </nav>
  );
}

type SprintTaskCanvasProps = {
  plan: ExamSprintPlan | null;
  selectedDay: number;
  comparison: MaterialComparisonResult | null;
  courseId: number | null;
  isPending: boolean;
  errorMessage: string | null;
  onOpenGenerate: () => void;
};

export function SprintTaskCanvas({ plan, selectedDay, comparison, courseId, isPending, errorMessage, onOpenGenerate }: SprintTaskCanvasProps) {
  if (isPending && !plan) {
    return <div className="path-workspace-state"><span className="path-state-spinner" />正在读取冲刺计划</div>;
  }
  if (!plan) {
    return (
      <div className="path-workspace-state path-workspace-empty">
        <Target size={34} weight="duotone" aria-hidden="true" />
        <strong>还没有期末冲刺计划</strong>
        <p>{comparison ? `资料对比 #${comparison.id} 已就绪，确认后可用于本次冲刺。` : "基于当前课程证据生成 3、7 或 14 天冲刺任务。"}</p>
        <button className="primary-action" type="button" onClick={onOpenGenerate}>生成冲刺计划</button>
        <InlineFeedback message={errorMessage} tone="warning" />
      </div>
    );
  }

  const dayTasks = plan.daily_tasks.filter((task) => (task.day_index || 1) === selectedDay);
  return (
    <section className="path-task-canvas sprint-task-canvas" aria-label="期末冲刺计划">
      <header className="path-canvas-heading">
        <div><span>{plan.goal || "聚焦高频考点与薄弱环节"}</span><h2>第 {selectedDay} 天任务</h2></div>
        <small>{plan.duration_days} 天冲刺 · {plan.generation_mode === "model_enhanced" ? "模型增强" : "规则底稿"}</small>
      </header>
      <InlineFeedback message={errorMessage} tone="warning" />
      {comparison ? (
        <div className="sprint-comparison-band">
          <CirclesThreePlus size={18} weight="duotone" aria-hidden="true" />
          <div><strong>资料对比 #{comparison.id}</strong><span>{comparison.summary.comparable_material_count} 份资料 · {comparison.summary.matched_concept_count} 个共同重点 · {comparison.summary.citation_count} 条引用</span></div>
        </div>
      ) : null}
      <div className="sprint-focus-strip">
        <div><span>高频点</span><strong>{plan.high_frequency_points.slice(0, 3).map((point) => point.title).join("、") || "暂无"}</strong></div>
        <div><span>薄弱点</span><strong>{plan.weak_points.slice(0, 3).map((point) => point.title).join("、") || "暂无"}</strong></div>
      </div>
      {(plan.warnings ?? []).map((warning) => <InlineFeedback key={warning} message={warning} tone="warning" />)}
      {dayTasks.length === 0 ? <div className="path-filter-empty">当天没有安排任务。</div> : (
        <ol className="path-task-list sprint-task-list">
          {dayTasks.map((task, index) => (
            <li key={task.id} className={task.status === "completed" ? "completed" : task.status === "doing" ? "current" : "todo"}>
              <div className="path-task-marker">{task.status === "completed" ? <Check size={16} weight="bold" aria-hidden="true" /> : <span>{index + 1}</span>}</div>
              <article>
                <div className="path-task-meta"><span>{task.status === "completed" ? "已完成" : task.status === "doing" ? "进行中" : "待开始"}</span><span>{task.task_type === "sprint_practice" ? "必刷题" : task.task_type === "sprint_resource" ? "资源阅读" : "重点复习"}</span><span><CalendarBlank size={14} aria-hidden="true" />{formatDate(task.due_at)}</span></div>
                <h3>{task.title}</h3>
                {task.reason ? <p>{task.reason}</p> : null}
                {task.recommended_resources.length > 0 ? <div className="path-task-resources">{task.recommended_resources.map((resource) => <span key={resource.id}><FileText size={14} aria-hidden="true" />{resource.title}</span>)}</div> : null}
              </article>
              {task.task_type === "sprint_practice" && task.knowledge_point_id && courseId ? (
                <Link className="primary-action" to={`/app/practice?course_id=${courseId}&knowledge_point_id=${task.knowledge_point_id}&sprint_plan_id=${plan.id}&sprint_task_id=${task.id}&new=1`}>
                  开始针对性练习<ArrowRight size={16} weight="bold" aria-hidden="true" />
                </Link>
              ) : null}
            </li>
          ))}
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
  mode: PathDrawerMode;
  view: LearningPathView;
  detailTab: PathDetailTab;
  duration: 3 | 7 | 14;
  goal: string;
  courseTitle: string;
  hasCourse: boolean;
  pending: boolean;
  feedback: string | null;
  pathDetail: LearningPathDetail | null;
  sprintPlan: ExamSprintPlan | null;
  comparison: MaterialComparisonResult | null;
  masteryPoints: CourseMasteryPoint[];
  onClose: () => void;
  onDetailTabChange: (tab: PathDetailTab) => void;
  onDurationChange: (event: ChangeEvent<HTMLSelectElement>) => void;
  onGoalChange: (value: string) => void;
  onSubmit: () => void;
};

export function LearningPathDrawer({
  mode,
  view,
  detailTab,
  duration,
  goal,
  courseTitle,
  hasCourse,
  pending,
  feedback,
  pathDetail,
  sprintPlan,
  comparison,
  masteryPoints,
  onClose,
  onDetailTabChange,
  onDurationChange,
  onGoalChange,
  onSubmit
}: LearningPathDrawerProps) {
  const activePlan = view === "path" ? pathDetail?.path : sprintPlan;
  const evidence = view === "path" ? pathDetail?.evidence_summary.basis ?? [] : sprintPlan?.evidence_summary.basis ?? [];
  const traceId = view === "path" ? pathDetail?.agent_trace_id : sprintPlan?.agent_trace_id;

  return (
    <div className="path-drawer-layer" role="presentation" data-testid="path-drawer-layer" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <aside className="path-drawer" role="dialog" aria-modal="true" aria-label={mode === "generate" ? `${view === "path" ? "学习路径" : "期末冲刺"}生成设置` : "路径详情"}>
        <header className="path-drawer-header">
          <div><span>{mode === "generate" ? "生成设置" : "路径详情"}</span><h2>{view === "path" ? "个性化路径" : "期末冲刺"}</h2><small>{courseTitle}</small></div>
          <button type="button" aria-label="关闭" onClick={onClose}><X size={18} aria-hidden="true" /></button>
        </header>

        <div className="path-drawer-scroll">
          {mode === "generate" ? (
            <div className="path-generate-form">
              <label><span>{view === "path" ? "学习周期" : "冲刺天数"}</span><select aria-label={view === "path" ? "学习周期" : "冲刺天数"} value={duration} onChange={onDurationChange}><option value={3}>3 天</option><option value={7}>7 天</option><option value={14}>14 天</option></select></label>
              <label><span>{view === "path" ? "学习目标" : "冲刺目标"}</span><textarea value={goal} placeholder={view === "path" ? "例如：补齐基础并完成一次综合练习" : "例如：优先突破高频考点与错题"} onChange={(event) => onGoalChange(event.target.value)} /></label>
              {view === "sprint" ? (
                <section className="path-drawer-source">
                  <strong>资料依据</strong>
                  {comparison ? <><span>资料对比 #{comparison.id}</span><p>{comparison.summary.comparable_material_count} 份可比较资料，命中 {comparison.summary.matched_concept_count} 个共同重点。</p></> : <p>本次未指定资料对比，将只使用课程、画像、弱点、练习、资源和报告证据。</p>}
                </section>
              ) : null}
              <InlineFeedback message={feedback} tone="warning" />
            </div>
          ) : (
            <>
              <div className="path-detail-tabs" role="tablist" aria-label="路径详情分类">
                <button type="button" role="tab" aria-selected={detailTab === "mastery"} onClick={() => onDetailTabChange("mastery")}><ChartBar size={16} aria-hidden="true" />掌握度</button>
                <button type="button" role="tab" aria-selected={detailTab === "evidence"} onClick={() => onDetailTabChange("evidence")}><FileText size={16} aria-hidden="true" />规划依据</button>
                <button type="button" role="tab" aria-selected={detailTab === "trace"} onClick={() => onDetailTabChange("trace")}><CirclesThreePlus size={16} aria-hidden="true" />协作轨迹</button>
              </div>
              {detailTab === "mastery" ? (
                <div className="path-detail-panel" role="tabpanel">
                  {masteryPoints.length > 0 ? <><MasteryOverviewChart points={masteryPoints} /><div className="path-mastery-list">{masteryPoints.map((point) => <article key={point.id}><div><strong>{point.title}</strong><span>{point.chapter ?? "未分章"}</span></div><em>{masteryStatusLabel(point.status)} · {point.score}</em><div><span style={{ width: `${point.score}%` }} /></div></article>)}</div></> : <p className="path-drawer-empty">暂无掌握度数据。</p>}
                </div>
              ) : null}
              {detailTab === "evidence" ? (
                <div className="path-detail-panel" role="tabpanel">
                  <div className="path-plan-metadata">
                    <span>{activePlan ? "计划已生效" : "暂无计划"}</span>
                    {view === "path" && pathDetail?.path ? (
                      <strong>
                        {String(pathDetail.path.plan_json.generation_mode ?? "deterministic_source") === "model_enhanced" ? "模型增强" : "规则底稿"}
                        {" · "}
                        {String(pathDetail.path.plan_json.review_mode ?? "rules_only") === "model_and_rules" ? "模型与规则审核" : "规则审核"}
                      </strong>
                    ) : null}
                    {view === "sprint" && sprintPlan ? <strong>{sprintPlan.review_mode === "model_and_rules" ? "模型与规则审核" : "规则审核"}</strong> : null}
                  </div>
                  <ul className="path-detail-evidence">{(evidence.length > 0 ? evidence : ["暂无可展示依据。"]).map((item) => <li key={item}><Sparkle size={16} weight="duotone" aria-hidden="true" /><span>{item}</span></li>)}</ul>
                  {view === "sprint" && sprintPlan?.must_do_questions.length ? <section className="path-detail-section"><h3>必刷题</h3>{sprintPlan.must_do_questions.slice(0, 5).map((question) => <p key={question.id}>{question.prompt}</p>)}</section> : null}
                  {view === "sprint" && sprintPlan?.easy_mistake_warnings.length ? <section className="path-detail-section"><h3>易错提醒</h3>{sprintPlan.easy_mistake_warnings.slice(0, 5).map((warning) => <p key={`${warning.knowledge_point_id ?? warning.title}-${warning.warning}`}>{warning.warning}</p>)}</section> : null}
                </div>
              ) : null}
              {detailTab === "trace" ? (
                <div className="path-detail-panel" role="tabpanel">
                  {traceId ? <AgentTraceDisclosure traceId={traceId} label={view === "path" ? "查看 PathPlanningGraph" : "查看 ExamSprintGraph"} /> : <p className="path-drawer-empty">当前计划没有可展示的协作轨迹。</p>}
                  {view === "sprint" && comparison?.agent_trace_id ? <AgentTraceDisclosure traceId={comparison.agent_trace_id} label="查看 MaterialComparisonGraph" /> : null}
                </div>
              ) : null}
            </>
          )}
        </div>

        {mode === "generate" ? (
          <footer className="path-drawer-footer">
            <p>{duration} 天 · {goal.trim() || (view === "path" ? "按当前学习状态规划" : "按当前冲刺证据规划")}</p>
            <button className="primary-action" type="button" disabled={!hasCourse || pending} onClick={onSubmit}>{pending ? "生成中" : view === "path" ? "生成学习路径" : "生成期末冲刺计划"}<ArrowRight size={17} weight="bold" aria-hidden="true" /></button>
          </footer>
        ) : null}
      </aside>
    </div>
  );
}

export function WorkspacePane({ rail, children }: { rail: ReactNode; children: ReactNode }) {
  return <div className="path-workspace-body">{rail}<main className="path-workspace-main">{children}</main></div>;
}

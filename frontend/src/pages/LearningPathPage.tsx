import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type ChangeEvent, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { getMasteryMap, listCourses } from "../api/courses";
import { generateExamSprintPlan, getCurrentExamSprintPlan, type ExamSprintDuration, type ExamSprintPlan } from "../api/examSprint";
import { getMaterialComparison } from "../api/materials";
import { generatePath, getCurrentPath, updatePathTask, type GeneratePathRequest, type LearningPathTask, type PathTaskStatus } from "../api/paths";
import {
  LearningPathDrawer,
  LearningPathToolbar,
  PathStatusRail,
  PathTaskCanvas,
  SprintDayRail,
  SprintTaskCanvas,
  WorkspacePane,
  type LearningPathView,
  type PathDetailTab,
  type PathDrawerMode,
  type PathTaskFilter
} from "../features/learning-path/LearningPathWorkspace";
import { courseLoopQueryKeys, invalidateCourseLearningLoop } from "../features/course-space/courseLoopQueries";
import { PageFrame } from "./PageFrame";
import "../styles/learning-path.css";

function parsePositiveId(value: string | null) {
  if (!value) return null;
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

function groupSprintTasks(tasks: ExamSprintPlan["daily_tasks"]) {
  const groups = new Map<number, ExamSprintPlan["daily_tasks"]>();
  tasks.forEach((task) => {
    const day = task.day_index || 1;
    groups.set(day, [...(groups.get(day) ?? []), task]);
  });
  return [...groups.entries()].sort(([left], [right]) => left - right);
}

function resolveView(searchParams: URLSearchParams): LearningPathView {
  const explicitView = searchParams.get("view");
  if (explicitView === "path" || explicitView === "sprint") return explicitView;
  return searchParams.has("comparison_id") || searchParams.has("sprint_plan_id") ? "sprint" : "path";
}

export function LearningPathPage() {
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const queryCourseId = parsePositiveId(searchParams.get("course_id"));
  const queryComparisonId = parsePositiveId(searchParams.get("comparison_id"));
  const view = resolveView(searchParams);

  const [selectedCourseId, setSelectedCourseId] = useState<number | null>(queryCourseId);
  const [pathFilter, setPathFilter] = useState<PathTaskFilter>("all");
  const [selectedSprintDay, setSelectedSprintDay] = useState(1);
  const [drawerMode, setDrawerMode] = useState<PathDrawerMode | null>(null);
  const [detailTab, setDetailTab] = useState<PathDetailTab>("mastery");
  const [durationDays, setDurationDays] = useState<GeneratePathRequest["duration_days"]>(7);
  const [goal, setGoal] = useState("");
  const [sprintDurationDays, setSprintDurationDays] = useState<ExamSprintDuration>(7);
  const [sprintGoal, setSprintGoal] = useState("");
  const [generatedSprintPlan, setGeneratedSprintPlan] = useState<ExamSprintPlan | null>(null);
  const [pathFeedback, setPathFeedback] = useState<string | null>(null);
  const [sprintFeedback, setSprintFeedback] = useState<string | null>(null);

  const coursesQuery = useQuery({
    queryKey: ["courses", "list"],
    queryFn: () => listCourses(),
    staleTime: 30_000
  });
  const courses = useMemo(() => coursesQuery.data?.data ?? [], [coursesQuery.data?.data]);
  const firstCourseId = courses[0] ? parsePositiveId(courses[0].id) : null;
  const effectiveCourseId = selectedCourseId ?? queryCourseId ?? firstCourseId;
  const hasCourse = effectiveCourseId !== null;

  const currentPathQuery = useQuery({
    queryKey: courseLoopQueryKeys.currentPath(effectiveCourseId ?? 0),
    queryFn: () => getCurrentPath(effectiveCourseId ?? 0),
    enabled: hasCourse,
    staleTime: 10_000
  });
  const masteryQuery = useQuery({
    queryKey: courseLoopQueryKeys.masteryMap(effectiveCourseId ?? 0),
    queryFn: () => getMasteryMap(effectiveCourseId ?? 0),
    enabled: hasCourse,
    staleTime: 10_000
  });
  const currentSprintQuery = useQuery({
    queryKey: ["exam-sprint", "current", effectiveCourseId],
    queryFn: () => getCurrentExamSprintPlan(effectiveCourseId ?? 0),
    enabled: hasCourse,
    staleTime: 10_000
  });
  const comparisonQuery = useQuery({
    queryKey: ["materials", "comparison", queryComparisonId],
    queryFn: () => getMaterialComparison(queryComparisonId ?? 0),
    enabled: queryComparisonId !== null
  });

  const selectedCourse = courses.find((course) => parsePositiveId(course.id) === effectiveCourseId) ?? null;
  const pathDetail = currentPathQuery.data?.data ?? null;
  const tasks = pathDetail?.tasks ?? [];
  const sprintPlan = generatedSprintPlan ?? currentSprintQuery.data?.data ?? null;
  const sprintGroups = useMemo(() => groupSprintTasks(sprintPlan?.daily_tasks ?? []), [sprintPlan?.daily_tasks]);
  const effectiveSprintDay = sprintGroups.some(([day]) => day === selectedSprintDay)
    ? selectedSprintDay
    : sprintGroups[0]?.[0] ?? 1;
  const selectedComparison = comparisonQuery.data?.data ?? null;
  const masteryPoints = masteryQuery.data?.data?.points ?? [];
  const activeTasks = view === "path" ? tasks : sprintPlan?.daily_tasks ?? [];
  const completedCount = activeTasks.filter((task) => task.status === "completed").length;
  const hasActivePlan = view === "path" ? Boolean(pathDetail?.path) : Boolean(sprintPlan);

  useEffect(() => {
    if (!drawerMode) return;
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setDrawerMode(null);
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [drawerMode]);

  const generateMutation = useMutation({
    mutationFn: (payload: GeneratePathRequest) => generatePath(payload),
    onSuccess: (result, payload) => {
      setPathFeedback(null);
      queryClient.setQueryData(courseLoopQueryKeys.currentPath(payload.course_id), result);
      void invalidateCourseLearningLoop(queryClient, payload.course_id);
      setDrawerMode(null);
    },
    onError: () => setPathFeedback("学习路径生成失败，请稍后重试。")
  });
  const updateTaskMutation = useMutation({
    mutationFn: ({ taskId, status }: { taskId: number; status: PathTaskStatus }) => updatePathTask(taskId, { status }),
    onSuccess: () => {
      setPathFeedback(null);
      if (effectiveCourseId) void invalidateCourseLearningLoop(queryClient, effectiveCourseId);
    },
    onError: () => setPathFeedback("任务状态更新失败，请稍后重试。")
  });
  const sprintMutation = useMutation({
    mutationFn: (payload: { course_id: number; duration_days: ExamSprintDuration; material_ids: number[]; comparison_id?: number; goal: string }) => generateExamSprintPlan(payload),
    onSuccess: (result, payload) => {
      setSprintFeedback(null);
      setGeneratedSprintPlan(result.data);
      queryClient.setQueryData(["exam-sprint", "current", payload.course_id], result);
      const nextParams = new URLSearchParams();
      nextParams.set("course_id", String(payload.course_id));
      nextParams.set("view", "sprint");
      nextParams.set("sprint_plan_id", result.data.id);
      if (payload.comparison_id) nextParams.set("comparison_id", String(payload.comparison_id));
      setSearchParams(nextParams, { replace: true });
      void invalidateCourseLearningLoop(queryClient, payload.course_id);
      setDrawerMode(null);
    },
    onError: () => setSprintFeedback("期末冲刺计划生成失败，请稍后重试。")
  });

  function handleCourseChange(event: ChangeEvent<HTMLSelectElement>) {
    const courseId = parsePositiveId(event.target.value);
    setSelectedCourseId(courseId);
    setGeneratedSprintPlan(null);
    setPathFeedback(null);
    setSprintFeedback(null);
    setPathFilter("all");
    setSelectedSprintDay(1);
    const nextParams = new URLSearchParams();
    if (courseId) nextParams.set("course_id", String(courseId));
    nextParams.set("view", view);
    setSearchParams(nextParams, { replace: true });
  }

  function handleViewChange(nextView: LearningPathView) {
    const nextParams = new URLSearchParams(searchParams);
    nextParams.set("view", nextView);
    if (effectiveCourseId) nextParams.set("course_id", String(effectiveCourseId));
    setSearchParams(nextParams, { replace: true });
    setDrawerMode(null);
  }

  function handleDurationChange(event: ChangeEvent<HTMLSelectElement>) {
    const value = Number.parseInt(event.target.value, 10);
    if (value !== 3 && value !== 7 && value !== 14) return;
    if (view === "path") setDurationDays(value);
    else setSprintDurationDays(value);
  }

  function submitPlan() {
    if (!effectiveCourseId) return;
    if (view === "path") {
      generateMutation.mutate({ course_id: effectiveCourseId, duration_days: durationDays, goal: goal.trim() });
      return;
    }
    sprintMutation.mutate({
      course_id: effectiveCourseId,
      duration_days: sprintDurationDays,
      material_ids: [],
      comparison_id: queryComparisonId ?? undefined,
      goal: sprintGoal.trim()
    });
  }

  function updateTask(task: LearningPathTask, status: PathTaskStatus) {
    const taskId = parsePositiveId(task.id);
    if (!taskId || updateTaskMutation.isPending) return;
    updateTaskMutation.mutate({ taskId, status });
  }

  const pathReadError = coursesQuery.isError || currentPathQuery.isError
    ? "学习路径数据读取失败，请稍后重试。"
    : pathFeedback;
  const sprintReadError = currentSprintQuery.isError
    ? "当前冲刺计划读取失败，请稍后重试。"
    : comparisonQuery.isError
      ? "资料对比读取失败，本次不会隐式使用旧结果。"
      : sprintFeedback;

  return (
    <>
      <PageFrame title="学习路径" variant="wide-workspace">
        <div className="learning-path-workspace">
        <LearningPathToolbar
          courses={courses}
          courseId={effectiveCourseId}
          courseTitle={selectedCourse?.title ?? "未选择课程"}
          view={view}
          completedCount={completedCount}
          totalCount={activeTasks.length}
          hasPlan={hasActivePlan}
          onCourseChange={handleCourseChange}
          onViewChange={handleViewChange}
          onOpenGenerate={() => setDrawerMode("generate")}
          onOpenDetails={() => { setDetailTab("mastery"); setDrawerMode("details"); }}
        />

        {view === "path" ? (
          <WorkspacePane rail={<PathStatusRail filter={pathFilter} tasks={tasks} onChange={setPathFilter} />}>
            <PathTaskCanvas
              pathDetail={pathDetail}
              tasks={tasks}
              filter={pathFilter}
              isPending={currentPathQuery.isPending}
              errorMessage={pathReadError}
              mutationPending={updateTaskMutation.isPending}
              onOpenGenerate={() => setDrawerMode("generate")}
              onUpdateTask={updateTask}
            />
          </WorkspacePane>
        ) : (
          <WorkspacePane rail={<SprintDayRail days={sprintGroups} selectedDay={effectiveSprintDay} onChange={setSelectedSprintDay} />}>
            <SprintTaskCanvas
              plan={sprintPlan}
              selectedDay={effectiveSprintDay}
              comparison={selectedComparison}
              courseId={effectiveCourseId}
              isPending={currentSprintQuery.isPending}
              errorMessage={sprintReadError}
              onOpenGenerate={() => setDrawerMode("generate")}
            />
          </WorkspacePane>
        )}
        </div>
      </PageFrame>
      {drawerMode ? (
        <LearningPathDrawer
          mode={drawerMode}
          view={view}
          detailTab={detailTab}
          duration={view === "path" ? durationDays : sprintDurationDays}
          goal={view === "path" ? goal : sprintGoal}
          courseTitle={selectedCourse?.title ?? "未选择课程"}
          hasCourse={hasCourse}
          pending={view === "path" ? generateMutation.isPending : sprintMutation.isPending}
          feedback={view === "path" ? pathFeedback : sprintFeedback}
          pathDetail={pathDetail}
          sprintPlan={sprintPlan}
          comparison={selectedComparison}
          masteryPoints={masteryPoints}
          onClose={() => setDrawerMode(null)}
          onDetailTabChange={setDetailTab}
          onDurationChange={handleDurationChange}
          onGoalChange={view === "path" ? setGoal : setSprintGoal}
          onSubmit={submitPlan}
        />
      ) : null}
    </>
  );
}

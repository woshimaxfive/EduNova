import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type ChangeEvent, useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { getMasteryMap, listCourses } from "../api/courses";
import { getCurrentPath, updatePathTask, type LearningPathTask, type PathTaskStatus } from "../api/paths";
import { createIdempotencyKey, createPathPlanningJob, createPathTaskResourceJob } from "../api/aiJobs";
import { useAiJobs } from "../features/aiJobs/AiJobProvider";
import {
  LearningPathDrawer,
  LearningPathToolbar,
  PathStatusRail,
  PathTaskCanvas,
  WorkspacePane,
  type PathDetailTab,
  type PathTaskFilter
} from "../features/learning-path/LearningPathWorkspace";
import { courseLoopQueryKeys, invalidateCourseLearningLoop } from "../features/course-space/courseLoopQueries";
import { PageFrame } from "./PageFrame";
import { CourseReturnLink } from "../components/course-space/CourseReturnLink";
import { PATHS } from "../app/routePaths";
import "../styles/learning-path.css";

function parsePositiveId(value: string | null) {
  if (!value) return null;
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

export function LearningPathPage() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const queryCourseId = parsePositiveId(searchParams.get("course_id"));
  const [selectedCourseId, setSelectedCourseId] = useState<number | null>(queryCourseId);
  const [pathFilter, setPathFilter] = useState<PathTaskFilter>("all");
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [detailTab, setDetailTab] = useState<PathDetailTab>("mastery");
  const [feedback, setFeedback] = useState<string | null>(null);
  const { jobs, trackJob, cancelJob } = useAiJobs();

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

  const selectedCourse = courses.find((course) => parsePositiveId(course.id) === effectiveCourseId) ?? null;
  const pathDetail = currentPathQuery.data?.data ?? null;
  const tasks = pathDetail?.tasks ?? [];
  const masteryPoints = masteryQuery.data?.data?.points ?? [];
  const completedCount = tasks.filter((task) => task.status === "completed").length;
  const pathJob = jobs.find((job) => (
    job.workflow === "path_planning"
    && Number(job.request.course_id ?? job.course_id) === effectiveCourseId
    && ["queued", "running", "cancelling", "failed"].includes(job.status)
  ));
  const pathJobActive = pathJob ? ["queued", "running", "cancelling"].includes(pathJob.status) : false;

  useEffect(() => {
    const hasDeprecatedParams = ["view", "comparison_id", "sprint_plan_id"].some((key) => searchParams.has(key));
    if (!hasDeprecatedParams) return;
    const nextParams = new URLSearchParams(searchParams);
    nextParams.delete("view");
    nextParams.delete("comparison_id");
    nextParams.delete("sprint_plan_id");
    setSearchParams(nextParams, { replace: true });
  }, [searchParams, setSearchParams]);

  const generateMutation = useMutation({
    mutationFn: (courseId: number) => createPathPlanningJob(
      { course_id: courseId },
      createIdempotencyKey(`path-${courseId}`)
    ),
    onSuccess: (job) => {
      setFeedback(null);
      trackJob(job);
    },
    onError: () => setFeedback("学习路径任务创建失败，请稍后重试。")
  });
  const updateTaskMutation = useMutation({
    mutationFn: ({ task, status }: { task: LearningPathTask; status: PathTaskStatus }) => updatePathTask(Number(task.id), { status }),
    onSuccess: (_result, variables) => {
      setFeedback(null);
      if (effectiveCourseId) void invalidateCourseLearningLoop(queryClient, effectiveCourseId);
      if (variables.status !== "doing" || !effectiveCourseId) return;
      const bundleResourceId = variables.task.learning_bundle?.items.find((item) => (
        item.resource_id && item.learning_status !== "completed"
      ))?.resource_id ?? variables.task.learning_bundle?.items.find((item) => item.resource_id)?.resource_id;
      const resourceId = bundleResourceId ?? variables.task.recommended_resources[0]?.id ?? variables.task.recommended_resource_ids[0];
      if (resourceId) {
        navigate(`${PATHS.studio}?course_id=${effectiveCourseId}&resource_id=${resourceId}&path_task_id=${variables.task.id}`);
      }
    },
    onError: () => setFeedback("任务状态更新失败，请稍后重试。")
  });
  const generateResourcesMutation = useMutation({
    mutationFn: (task: LearningPathTask) => createPathTaskResourceJob(
      Number(task.id),
      createIdempotencyKey(`path-task-resources-${task.id}`)
    ),
    onSuccess: (job) => {
      setFeedback(null);
      trackJob(job);
    },
    onError: () => setFeedback("本节学习资源任务创建失败，请稍后重试。")
  });

  function handleCourseChange(event: ChangeEvent<HTMLSelectElement>) {
    const courseId = parsePositiveId(event.target.value);
    setSelectedCourseId(courseId);
    setFeedback(null);
    setPathFilter("all");
    setDetailsOpen(false);
    const nextParams = new URLSearchParams();
    if (courseId) nextParams.set("course_id", String(courseId));
    setSearchParams(nextParams, { replace: true });
  }

  function generateLearningPath() {
    if (!effectiveCourseId || generateMutation.isPending || pathJobActive) return;
    generateMutation.mutate(effectiveCourseId);
  }

  function updateTask(task: LearningPathTask, status: PathTaskStatus) {
    if (!parsePositiveId(task.id) || updateTaskMutation.isPending) return;
    updateTaskMutation.mutate({ task, status });
  }

  function openTaskLearning(task: LearningPathTask) {
    if (!effectiveCourseId) return;
    const readyItems = task.learning_bundle?.items.filter((item) => item.resource_id) ?? [];
    const resourceId = readyItems.find((item) => item.learning_status !== "completed")?.resource_id
      ?? readyItems[0]?.resource_id;
    if (!resourceId) return;
    navigate(`${PATHS.studio}?course_id=${effectiveCourseId}&resource_id=${resourceId}&path_task_id=${task.id}`);
  }

  const readError = coursesQuery.isError || currentPathQuery.isError
    ? "学习路径数据读取失败，请稍后重试。"
    : pathJob?.status === "failed"
      ? pathJob.error_message ?? "学习路径规划失败，可从任务托盘重试。"
      : feedback;
  const planningPending = generateMutation.isPending || pathJobActive;

  return (
    <>
      <PageFrame title="学习路径" titleMode="sr-only" variant="wide-workspace">
        <div className="learning-path-workspace">
          <LearningPathToolbar
            returnLink={<CourseReturnLink courseId={effectiveCourseId} compact />}
            courses={courses}
            courseId={effectiveCourseId}
            courseTitle={selectedCourse?.title ?? "未选择课程"}
            completedCount={completedCount}
            totalCount={tasks.length}
            hasPlan={Boolean(pathDetail?.path)}
            generatePending={planningPending}
            onCourseChange={handleCourseChange}
            onGenerate={generateLearningPath}
            onOpenDetails={() => {
              setDetailTab("mastery");
              setDetailsOpen(true);
            }}
          />
          <WorkspacePane rail={<PathStatusRail filter={pathFilter} tasks={tasks} onChange={setPathFilter} />}>
            <PathTaskCanvas
              pathDetail={pathDetail}
              tasks={tasks}
              filter={pathFilter}
              isPending={currentPathQuery.isPending}
              errorMessage={readError}
              mutationPending={planningPending || updateTaskMutation.isPending || generateResourcesMutation.isPending}
              resourceJobs={jobs.filter((job) => job.workflow === "resource_generation" && Boolean(job.request.path_task_id))}
              onGenerate={generateLearningPath}
              onGenerateResources={(task) => generateResourcesMutation.mutate(task)}
              onOpenLearning={openTaskLearning}
              onCancelResourceJob={(jobId) => void cancelJob(jobId)}
              onUpdateTask={updateTask}
            />
          </WorkspacePane>
        </div>
      </PageFrame>
      {detailsOpen ? (
        <LearningPathDrawer
          detailTab={detailTab}
          courseTitle={selectedCourse?.title ?? "未选择课程"}
          pathDetail={pathDetail}
          masteryPoints={masteryPoints}
          onClose={() => setDetailsOpen(false)}
          onDetailTabChange={setDetailTab}
        />
      ) : null}
    </>
  );
}

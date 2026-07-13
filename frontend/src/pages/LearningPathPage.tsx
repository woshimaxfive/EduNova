import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type ChangeEvent, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { getMasteryMap, listCourses } from "../api/courses";
import { generatePath, getCurrentPath, updatePathTask, type LearningPathTask, type PathTaskStatus } from "../api/paths";
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
import "../styles/learning-path.css";

function parsePositiveId(value: string | null) {
  if (!value) return null;
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

export function LearningPathPage() {
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const queryCourseId = parsePositiveId(searchParams.get("course_id"));
  const [selectedCourseId, setSelectedCourseId] = useState<number | null>(queryCourseId);
  const [pathFilter, setPathFilter] = useState<PathTaskFilter>("all");
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [detailTab, setDetailTab] = useState<PathDetailTab>("mastery");
  const [feedback, setFeedback] = useState<string | null>(null);

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

  useEffect(() => {
    const hasDeprecatedParams = ["view", "comparison_id", "sprint_plan_id"].some((key) => searchParams.has(key));
    if (!hasDeprecatedParams) return;
    const nextParams = new URLSearchParams(searchParams);
    nextParams.delete("view");
    nextParams.delete("comparison_id");
    nextParams.delete("sprint_plan_id");
    setSearchParams(nextParams, { replace: true });
  }, [searchParams, setSearchParams]);

  useEffect(() => {
    if (!detailsOpen) return;
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setDetailsOpen(false);
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [detailsOpen]);

  const generateMutation = useMutation({
    mutationFn: (courseId: number) => generatePath({ course_id: courseId }),
    onSuccess: (result, courseId) => {
      setFeedback(null);
      queryClient.setQueryData(courseLoopQueryKeys.currentPath(courseId), result);
      void invalidateCourseLearningLoop(queryClient, courseId);
    },
    onError: () => setFeedback("学习路径生成失败，请稍后重试。")
  });
  const updateTaskMutation = useMutation({
    mutationFn: ({ taskId, status }: { taskId: number; status: PathTaskStatus }) => updatePathTask(taskId, { status }),
    onSuccess: () => {
      setFeedback(null);
      if (effectiveCourseId) void invalidateCourseLearningLoop(queryClient, effectiveCourseId);
    },
    onError: () => setFeedback("任务状态更新失败，请稍后重试。")
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
    if (!effectiveCourseId || generateMutation.isPending) return;
    generateMutation.mutate(effectiveCourseId);
  }

  function updateTask(task: LearningPathTask, status: PathTaskStatus) {
    const taskId = parsePositiveId(task.id);
    if (!taskId || updateTaskMutation.isPending) return;
    updateTaskMutation.mutate({ taskId, status });
  }

  const readError = coursesQuery.isError || currentPathQuery.isError
    ? "学习路径数据读取失败，请稍后重试。"
    : feedback;

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
            generatePending={generateMutation.isPending}
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
              mutationPending={generateMutation.isPending || updateTaskMutation.isPending}
              onGenerate={generateLearningPath}
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

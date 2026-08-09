import { useQuery } from "@tanstack/react-query";

import {
  getCourse,
  getCourseLearningState,
  getCourseOverview,
  getKnowledgePoints,
  getMasteryMap
} from "../../api/courses";
import { getCurrentPath } from "../../api/paths";
import { getLatestPracticeSession } from "../../api/practice";
import { getLatestReport } from "../../api/reports";
import { listResources } from "../../api/resources";
import { listTutorSessions } from "../../api/tutor";
import { courseLoopQueryKeys } from "./courseLoopQueries";

export function useCourseWorkspaceData(courseId: number, enabled: boolean) {
  const courseQuery = useQuery({
    queryKey: ["courses", "detail", courseId],
    queryFn: () => getCourse(courseId),
    enabled,
    staleTime: 30_000
  });
  const knowledgePointsQuery = useQuery({
    queryKey: ["courses", "knowledge-points", courseId],
    queryFn: () => getKnowledgePoints(courseId),
    enabled,
    staleTime: 30_000
  });
  const courseOverviewQuery = useQuery({
    queryKey: ["courses", "overview", courseId],
    queryFn: () => getCourseOverview(courseId),
    enabled,
    staleTime: 30_000
  });
  const learningStateQuery = useQuery({
    queryKey: courseLoopQueryKeys.learningState(courseId),
    queryFn: () => getCourseLearningState(courseId),
    enabled,
    staleTime: 10_000
  });
  const masteryMapQuery = useQuery({
    queryKey: courseLoopQueryKeys.masteryMap(courseId),
    queryFn: () => getMasteryMap(courseId),
    enabled,
    staleTime: 10_000,
    retry: false
  });
  const courseSessionsQuery = useQuery({
    queryKey: ["tutor", "sessions", "course", courseId],
    queryFn: () => listTutorSessions("course", courseId),
    enabled,
    staleTime: 10_000
  });
  const courseResourcesQuery = useQuery({
    queryKey: courseLoopQueryKeys.resources(courseId),
    queryFn: () => listResources({ courseId }),
    enabled,
    staleTime: 10_000
  });
  const currentPathQuery = useQuery({
    queryKey: courseLoopQueryKeys.currentPath(courseId),
    queryFn: () => getCurrentPath(courseId),
    enabled,
    staleTime: 10_000
  });
  const latestReportQuery = useQuery({
    queryKey: courseLoopQueryKeys.latestReport(courseId),
    queryFn: () => getLatestReport(courseId),
    enabled,
    staleTime: 10_000
  });
  const latestPracticeQuery = useQuery({
    queryKey: courseLoopQueryKeys.latestPractice(courseId),
    queryFn: () => getLatestPracticeSession(courseId),
    enabled,
    staleTime: 10_000
  });

  return {
    courseOverviewQuery,
    courseQuery,
    courseResourcesQuery,
    courseSessionsQuery,
    currentPathQuery,
    knowledgePointsQuery,
    latestPracticeQuery,
    latestReportQuery,
    learningStateQuery,
    masteryMapQuery
  };
}

import { type QueryClient } from "@tanstack/react-query";
import { invalidateLearningNextActions, learningActionKeys } from "../learning-actions/learningActions";

export const courseLoopQueryKeys = {
  learningState: (courseId: number) => ["courses", "learning-state", courseId] as const,
  masteryMap: (courseId: number) => ["courses", "mastery-map", courseId] as const,
  resources: (courseId: number) => ["resources", "course", courseId] as const,
  currentPath: (courseId: number) => ["paths", "current", courseId] as const,
  latestReport: (courseId: number) => ["reports", "latest", courseId] as const,
  latestPractice: (courseId: number) => ["practice", "latest", courseId] as const,
  recentPractices: (courseId: number) => ["practice", "recent", courseId] as const,
  nextAction: (courseId: number) => learningActionKeys.detail(courseId)
};

export function courseLoopKeys(courseId: number) {
  return [
    courseLoopQueryKeys.learningState(courseId),
    courseLoopQueryKeys.masteryMap(courseId),
    courseLoopQueryKeys.resources(courseId),
    courseLoopQueryKeys.currentPath(courseId),
    courseLoopQueryKeys.latestReport(courseId),
    courseLoopQueryKeys.latestPractice(courseId),
    courseLoopQueryKeys.recentPractices(courseId),
    courseLoopQueryKeys.nextAction(courseId)
  ] as const;
}

export async function invalidateCourseLearningLoop(queryClient: QueryClient, courseId: number) {
  await Promise.all([
    invalidateLearningNextActions(queryClient, courseId),
    ...courseLoopKeys(courseId).map((queryKey) => queryClient.invalidateQueries({ queryKey, exact: true }))
  ]);
}

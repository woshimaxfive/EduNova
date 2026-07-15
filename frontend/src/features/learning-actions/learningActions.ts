import { type QueryClient, useQuery } from "@tanstack/react-query";

import { getLearningNextAction, type LearningNextAction } from "../../api/learning";
import { buildCoursePath, PATHS } from "../../app/routePaths";

export const learningActionKeys = {
  all: ["learning", "next-action"] as const,
  detail: (courseId?: number | null) => ["learning", "next-action", courseId ?? "global"] as const
};

export function useLearningNextAction(courseId?: number | null) {
  return useQuery({
    queryKey: learningActionKeys.detail(courseId),
    queryFn: () => getLearningNextAction(courseId),
    staleTime: 5_000,
    retry: false
  });
}

export function invalidateLearningNextActions(queryClient: QueryClient, courseId?: number | null) {
  const keys = [learningActionKeys.detail(null)];
  if (courseId != null) keys.push(learningActionKeys.detail(courseId));
  return Promise.all(keys.map((queryKey) => queryClient.invalidateQueries({ queryKey, exact: true })));
}

function withParams(path: string, params: Record<string, string | null | undefined>) {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value) search.set(key, value);
  });
  const query = search.toString();
  return query ? `${path}?${query}` : path;
}

export function learningActionHref(action: LearningNextAction) {
  if (["upload_material", "wait_for_material", "review_material", "retry_material", "create_course"].includes(action.kind)) {
    return withParams(PATHS.library, { material_id: action.material_id });
  }
  if (action.kind === "wait_for_course") return PATHS.app;
  if (action.kind === "generate_path") return withParams(PATHS.path, { course_id: action.course_id });
  if (action.kind === "continue_path_task") {
    if (action.resource_id) {
      return withParams(PATHS.studio, {
        course_id: action.course_id,
        resource_id: action.resource_id,
        path_task_id: action.path_task_id
      });
    }
    return withParams(action.course_id ? buildCoursePath(action.course_id) : PATHS.app, {
      knowledge_point_id: action.knowledge_point_id,
      path_task_id: action.path_task_id
    });
  }
  if (action.kind === "practice_weakness") {
    return withParams(PATHS.practice, {
      course_id: action.course_id,
      knowledge_point_id: action.knowledge_point_id,
      new: "1"
    });
  }
  if (action.kind === "study_knowledge_point") {
    return withParams(action.course_id ? buildCoursePath(action.course_id) : PATHS.app, {
      knowledge_point_id: action.knowledge_point_id
    });
  }
  if (["update_report", "review_report"].includes(action.kind)) {
    return withParams(PATHS.reports, { course_id: action.course_id });
  }
  if (action.course_id) return buildCoursePath(action.course_id);
  return PATHS.app;
}

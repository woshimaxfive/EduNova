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
  if (["generate_path", "wait_for_path"].includes(action.kind)) return withParams(PATHS.path, { course_id: action.course_id });
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

const ACTION_BUTTON_LABELS: Record<string, string> = {
  upload_material: "上传资料",
  wait_for_material: "查看进度",
  retry_material: "重新解析",
  review_material: "确认目录",
  create_course: "生成课程",
  wait_for_course: "查看进度",
  confirm_weakness: "确认薄弱点",
  continue_path_task: "继续任务",
  practice_weakness: "开始练习",
  generate_path: "生成路径",
  wait_for_path: "查看规划进度",
  study_knowledge_point: "开始学习",
  update_report: "更新报告",
  review_report: "查看报告"
};

export function learningActionButtonLabel(action: LearningNextAction) {
  return ACTION_BUTTON_LABELS[action.kind] ?? (action.status === "waiting" ? "查看进度" : "继续");
}

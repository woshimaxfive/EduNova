import type { CourseMasteryPoint } from "../../api/courses";
import type { CourseAnswerPanelKind } from "../../components/course-space/CourseClosedLoopActions";
import type { CourseContentMode } from "../../components/course-space/CourseContentView";
import type { CourseWorkspaceMode } from "../../components/course-space/CourseWorkspaceHeader";

export type GraphScope = "focus" | "course";

export type CourseWorkspaceUrlState = {
  mode: CourseWorkspaceMode;
  view: CourseContentMode;
  knowledgePointId: string | null;
  graphScope: GraphScope;
  graphChapter: string;
  detailKnowledge: boolean;
  courseSessionId: string | null;
  courseMessageId: string | null;
  panel: CourseAnswerPanelKind | null;
  mentorOpen: boolean;
};

const coursePanels = new Set<CourseAnswerPanelKind>(["citations", "resources", "why", "thinking"]);

export function parseCourseWorkspaceUrl(searchParams: URLSearchParams): CourseWorkspaceUrlState {
  const requestedMode = searchParams.get("mode");
  const requestedView = searchParams.get("view");
  const requestedScope = searchParams.get("graph_scope");
  const panelValue = searchParams.get("panel");
  const requestedPanel = (panelValue === "trace" ? "thinking" : panelValue) as CourseAnswerPanelKind | null;
  const mentorOpen = searchParams.get("mentor") === "open";
  const hasConversationTarget = Boolean(searchParams.get("course_message_id") || (searchParams.get("course_session_id") && !mentorOpen));
  const hasStudyTarget = Boolean(searchParams.get("knowledge_point_id"));
  return {
    mode: requestedMode === "chat" || requestedMode === "study"
      ? requestedMode
      : hasConversationTarget ? "chat" : "study",
    view: requestedView === "overview" || requestedView === "graph"
      ? requestedView
      : requestedMode === "chat" || hasConversationTarget || hasStudyTarget ? "overview" : "graph",
    knowledgePointId: searchParams.get("knowledge_point_id"),
    graphScope: requestedScope === "course" ? "course" : "focus",
    graphChapter: searchParams.get("graph_chapter") ?? "",
    detailKnowledge: searchParams.get("detail") === "knowledge",
    courseSessionId: searchParams.get("course_session_id"),
    courseMessageId: searchParams.get("course_message_id"),
    panel: requestedPanel && coursePanels.has(requestedPanel) ? requestedPanel : null,
    mentorOpen
  };
}

export function selectCourseWorkspacePoint(
  points: CourseMasteryPoint[],
  requestedId: string | null,
  recommendedPointId: string | null,
  weaknessPointIds: string[]
) {
  const pointById = new Map(points.map((point) => [point.id, point]));
  if (requestedId && pointById.has(requestedId)) return requestedId;
  if (recommendedPointId && pointById.has(recommendedPointId)) {
    return recommendedPointId;
  }
  const weaknessPoint = weaknessPointIds.find((id) => pointById.has(id));
  if (weaknessPoint) return weaknessPoint;
  const lowestAssessed = points
    .filter((point) => point.score !== null)
    .sort((left, right) => (left.score ?? 101) - (right.score ?? 101) || left.order_index - right.order_index)[0];
  return lowestAssessed?.id ?? [...points].sort((left, right) => left.order_index - right.order_index)[0]?.id ?? null;
}

export function normalizeCourseWorkspaceParams(
  current: URLSearchParams,
  state: CourseWorkspaceUrlState,
  pointId: string | null,
  validChapters: Set<string>
) {
  const next = new URLSearchParams(current);
  next.set("mode", state.mode);
  next.set("view", state.view);
  next.set("graph_scope", state.graphScope);
  if (pointId) next.set("knowledge_point_id", pointId);
  else next.delete("knowledge_point_id");
  if (state.graphChapter && validChapters.has(state.graphChapter)) next.set("graph_chapter", state.graphChapter);
  else next.delete("graph_chapter");
  if (state.detailKnowledge && pointId) next.set("detail", "knowledge");
  else next.delete("detail");
  if (!state.courseMessageId || !state.panel) next.delete("panel");
  if (state.mode === "study" && state.mentorOpen) next.set("mentor", "open");
  else next.delete("mentor");
  return next;
}

export function sameSearchParams(left: URLSearchParams, right: URLSearchParams) {
  return left.toString() === right.toString();
}

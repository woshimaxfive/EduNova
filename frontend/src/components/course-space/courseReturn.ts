import { buildCoursePath } from "../../app/routePaths";

export function buildCourseReturnHref(searchParams: URLSearchParams, courseId: number | null, alwaysShow = false) {
  const returnCourseId = Number.parseInt(searchParams.get("course_id") ?? "", 10);
  if (!courseId) return null;
  if (!alwaysShow && (searchParams.get("return_to") !== "course" || (Number.isFinite(returnCourseId) && returnCourseId !== courseId))) return null;

  const params = new URLSearchParams();
  const sessionId = searchParams.get("course_session_id");
  const messageId = searchParams.get("course_message_id");
  const knowledgePointId = searchParams.get("knowledge_point_id");
  if (sessionId) params.set("course_session_id", sessionId);
  if (messageId) params.set("course_message_id", messageId);
  if (knowledgePointId) params.set("knowledge_point_id", knowledgePointId);
  const suffix = params.size > 0 ? `?${params.toString()}` : "";
  return `${buildCoursePath(courseId)}${suffix}`;
}

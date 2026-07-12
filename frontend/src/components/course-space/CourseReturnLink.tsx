import { ArrowLeft } from "@phosphor-icons/react";
import { Link, useSearchParams } from "react-router-dom";

import { buildCoursePath } from "../../app/routePaths";

export function CourseReturnLink({ courseId }: { courseId: number | null }) {
  const [searchParams] = useSearchParams();
  const returnCourseId = Number.parseInt(searchParams.get("course_id") ?? "", 10);
  if (searchParams.get("return_to") !== "course" || !courseId || returnCourseId !== courseId) return null;

  const params = new URLSearchParams();
  const sessionId = searchParams.get("course_session_id");
  const messageId = searchParams.get("course_message_id");
  const knowledgePointId = searchParams.get("knowledge_point_id");
  if (sessionId) params.set("course_session_id", sessionId);
  if (messageId) params.set("course_message_id", messageId);
  if (knowledgePointId) params.set("knowledge_point_id", knowledgePointId);
  const suffix = params.size > 0 ? `?${params.toString()}` : "";

  return (
    <Link className="course-return-link" to={`${buildCoursePath(courseId)}${suffix}`}>
      <ArrowLeft size={16} weight="bold" aria-hidden="true" />
      <span>返回课程空间继续学习</span>
    </Link>
  );
}

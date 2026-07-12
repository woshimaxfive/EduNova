import { ArrowLeft } from "@phosphor-icons/react";
import { Link, useSearchParams } from "react-router-dom";

import { buildCourseReturnHref } from "./courseReturn";

export function CourseReturnLink({ courseId }: { courseId: number | null }) {
  const [searchParams] = useSearchParams();
  const href = buildCourseReturnHref(searchParams, courseId);
  if (!href) return null;

  return (
    <Link className="course-return-link" to={href}>
      <ArrowLeft size={16} weight="bold" aria-hidden="true" />
      <span>返回课程空间继续学习</span>
    </Link>
  );
}

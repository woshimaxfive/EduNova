import { ArrowLeft } from "@phosphor-icons/react";
import { Link, useSearchParams } from "react-router-dom";

import { buildCourseReturnHref } from "./courseReturn";

export function CourseReturnLink({ courseId, compact = false }: { courseId: number | null; compact?: boolean }) {
  const [searchParams] = useSearchParams();
  const href = buildCourseReturnHref(searchParams, courseId);
  if (!href) return null;

  return (
    <Link
      className={compact ? "course-return-link course-return-link-compact" : "course-return-link"}
      to={href}
      aria-label={compact ? "返回课程空间" : undefined}
      title={compact ? "返回课程空间" : undefined}
    >
      <ArrowLeft size={16} weight="bold" aria-hidden="true" />
      <span>返回课程空间继续学习</span>
    </Link>
  );
}

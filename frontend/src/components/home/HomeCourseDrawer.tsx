import { BookOpen, MagnifyingGlass, X } from "@phosphor-icons/react";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { listCourses } from "../../api/courses";
import { buildCoursePath } from "../../app/routePaths";

type HomeCourseDrawerProps = {
  onClose: () => void;
};

const sourceLabels = {
  builtin: "示例课程",
  uploaded: "资料课程",
  generated: "智能建课",
} as const;

export function HomeCourseDrawer({ onClose }: HomeCourseDrawerProps) {
  const [searchTerm, setSearchTerm] = useState("");
  const coursesQuery = useQuery({
    queryKey: ["courses", "list"],
    queryFn: () => listCourses(),
    staleTime: 30_000,
  });
  const courses = useMemo(() => coursesQuery.data?.data ?? [], [coursesQuery.data?.data]);
  const visibleCourses = useMemo(() => {
    const normalizedSearch = searchTerm.trim().toLowerCase();
    if (!normalizedSearch) return courses;

    return courses.filter((course) =>
      `${course.title} ${course.subject} ${course.description}`.toLowerCase().includes(normalizedSearch),
    );
  }, [courses, searchTerm]);

  useEffect(() => {
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }

    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [onClose]);

  return (
    <div
      className="home-course-drawer-layer"
      role="presentation"
      data-testid="home-course-drawer-layer"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <aside className="home-course-drawer" role="dialog" aria-modal="true" aria-labelledby="home-course-drawer-title">
        <header className="home-course-drawer-header">
          <h2 id="home-course-drawer-title">全部课程</h2>
          <button type="button" aria-label="关闭全部课程" onClick={onClose}>
            <X size={19} weight="bold" aria-hidden="true" />
          </button>
        </header>

        <div className="home-course-drawer-toolbar">
          <label>
            <MagnifyingGlass size={17} weight="duotone" aria-hidden="true" />
            <input
              aria-label="搜索课程"
              placeholder="搜索课程名称或学科"
              value={searchTerm}
              onChange={(event) => setSearchTerm(event.target.value)}
            />
          </label>
          <span>{coursesQuery.isSuccess ? `${courses.length} 门课程` : "正在同步课程"}</span>
        </div>

        <div className="home-course-drawer-content">
          {coursesQuery.isPending ? (
            <div className="home-course-drawer-skeleton" aria-label="正在加载全部课程">
              <span />
              <span />
              <span />
            </div>
          ) : null}

          {coursesQuery.isError ? (
            <div className="home-course-drawer-state" role="alert">
              <BookOpen size={24} weight="duotone" aria-hidden="true" />
              <strong>课程列表暂时没有读取成功</strong>
              <button type="button" onClick={() => void coursesQuery.refetch()}>重新读取</button>
            </div>
          ) : null}

          {coursesQuery.isSuccess && visibleCourses.length === 0 ? (
            <div className="home-course-drawer-state">
              <BookOpen size={24} weight="duotone" aria-hidden="true" />
              <strong>{courses.length === 0 ? "还没有课程" : "没有匹配的课程"}</strong>
              <p>{courses.length === 0 ? "上传资料并生成课程后，会在这里集中展示。" : "换一个课程名或学科关键词试试。"}</p>
            </div>
          ) : null}

          {coursesQuery.isSuccess && visibleCourses.length > 0 ? (
            <ul className="home-course-drawer-list" aria-label="全部课程列表">
              {visibleCourses.map((course) => (
                <li key={course.id}>
                  <Link to={buildCoursePath(course.id)} aria-label={`打开课程${course.title}`} onClick={onClose}>
                    <span className="home-course-drawer-icon">
                      <BookOpen size={19} weight="duotone" aria-hidden="true" />
                    </span>
                    <span className="home-course-drawer-copy">
                      <strong>{course.title}</strong>
                      <small>{`${course.subject || "未标注学科"} · ${sourceLabels[course.source_type]}`}</small>
                      <span>{`${course.material_count} 份资料 · ${course.knowledge_point_count} 个知识点`}</span>
                    </span>
                    <span className="home-course-drawer-progress">
                      <em>{`${Math.round(course.progress_percent)}%`}</em>
                      <progress max={100} value={Math.max(0, Math.min(100, course.progress_percent))} aria-label={`${course.title}课程进度`} />
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      </aside>
    </div>
  );
}

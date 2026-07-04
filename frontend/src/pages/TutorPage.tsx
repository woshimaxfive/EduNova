import { ArrowRight, Books, HouseLine, UploadSimple } from "@phosphor-icons/react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { buildCoursePath, PATHS } from "../app/routePaths";
import { listCourses } from "../api/courses";
import { PageFrame } from "./PageFrame";

export function TutorPage() {
  const coursesQuery = useQuery({
    queryKey: ["courses", "tutor-entry"],
    queryFn: () => listCourses(),
    staleTime: 30_000
  });
  const courses = coursesQuery.data?.data ?? [];
  const hasCourses = courses.length > 0;

  return (
    <PageFrame title="AI 辅导">
      <div className="student-workspace tutor-entry-workspace">
        <section className="student-panel tutor-entry-panel" role="region" aria-label="课程辅导入口">
          <div className="student-panel-heading">
            <span className="student-panel-icon" aria-hidden="true">
              <Books size={20} weight="duotone" />
            </span>
            <div>
              <h2>选择课程开始辅导</h2>
            </div>
          </div>

          <p className="tutor-entry-copy">
            AI 辅导已经收敛到课程空间：进入一门课程后提问，回答会基于该课程资料检索、生成引用，并保存到课程历史。
          </p>

          {coursesQuery.isLoading ? <p className="tutor-entry-state">正在读取你的课程...</p> : null}

          {!coursesQuery.isLoading && hasCourses ? (
            <div className="tutor-course-list" aria-label="可辅导课程">
              {courses.map((course) => (
                <Link className="tutor-course-card" to={buildCoursePath(course.id)} key={course.id}>
                  <span>
                    <strong>{course.title}</strong>
                    <small>
                      {course.material_count} 份资料 · {course.knowledge_point_count} 个知识点 ·{" "}
                      {course.progress_percent > 0 ? `${course.progress_percent}%` : "未开始"}
                    </small>
                  </span>
                  <ArrowRight size={18} weight="bold" aria-hidden="true" />
                </Link>
              ))}
            </div>
          ) : null}

          {!coursesQuery.isLoading && !hasCourses ? (
            <div className="tutor-empty-state">
              <strong>还没有可辅导的课程</strong>
              <p>先上传 TXT 或 Markdown 资料生成课程，再进入课程空间提问。这样回答才能带上真实引用。</p>
              <div className="tutor-empty-actions">
                <Link className="primary-action" to={PATHS.library}>
                  <UploadSimple size={17} weight="bold" aria-hidden="true" />
                  <span>去资料库上传资料</span>
                </Link>
                <Link className="secondary-action" to={PATHS.app}>
                  <HouseLine size={17} weight="bold" aria-hidden="true" />
                  <span>回到学习主页</span>
                </Link>
              </div>
            </div>
          ) : null}
        </section>

        <aside className="student-panel tutor-entry-note" role="region" aria-label="辅导说明">
          <strong>当前边界</strong>
          <p>这里不再展示静态问答。真实课程问答、RAG 引用、流式输出和历史恢复都在对应课程空间完成。</p>
        </aside>
      </div>
    </PageFrame>
  );
}

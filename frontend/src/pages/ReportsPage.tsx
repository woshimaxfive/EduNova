import { ChartLineUp, DownloadSimple, FileText, Graph, ShieldCheck } from "@phosphor-icons/react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useSearchParams } from "react-router-dom";

import { listCourses } from "../api/courses";
import { exportLearningDossier } from "../api/exports";
import { generateReport, getLatestReport } from "../api/reports";
import { PageFrame } from "./PageFrame";

function downloadMarkdownFile(filename: string, markdown: string, contentType: string) {
  const blob = new Blob([markdown], { type: contentType });
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}

export function ReportsPage() {
  const [searchParams] = useSearchParams();
  const initialCourseId = searchParams.get("course_id") ?? "";
  const [selectedCourseId, setSelectedCourseId] = useState(initialCourseId);
  const [localError, setLocalError] = useState("");
  const [exportError, setExportError] = useState("");
  const [exportMessage, setExportMessage] = useState("");

  const coursesQuery = useQuery({
    queryKey: ["report-courses"],
    queryFn: () => listCourses()
  });
  const courses = coursesQuery.data?.data ?? [];
  const effectiveCourseId = selectedCourseId || courses[0]?.id || "";
  const numericCourseId = Number(effectiveCourseId);
  const canUseCourse = Number.isFinite(numericCourseId) && numericCourseId > 0;
  const latestReportQuery = useQuery({
    queryKey: ["latest-report", numericCourseId],
    queryFn: () => getLatestReport(numericCourseId),
    enabled: canUseCourse
  });

  const generateMutation = useMutation({
    mutationFn: () => generateReport({ course_id: numericCourseId }),
    onSuccess: () => {
      setLocalError("");
      setExportMessage("");
      void latestReportQuery.refetch();
    },
    onError: () => {
      setLocalError("学习报告生成失败，请稍后重试。");
    }
  });

  const exportMutation = useMutation({
    mutationFn: () => exportLearningDossier({ course_id: numericCourseId }),
    onSuccess: (response) => {
      setExportError("");
      downloadMarkdownFile(response.data.filename, response.data.markdown, response.data.content_type);
      setExportMessage("已生成 Markdown 学习档案。");
    },
    onError: () => {
      setExportMessage("");
      setExportError("学习档案导出失败，请稍后重试。");
    }
  });

  const report = latestReportQuery.data?.data;
  const reportBody = report?.report;
  const isReadyReport = report?.status === "ready";
  const isEmptyReport = report?.status === "empty";
  const reportTitle = isReadyReport ? "课程学习报告" : "还没有真实学习报告";
  const reportSummary = isEmptyReport
    ? "完成一次课程练习后可生成报告"
    : reportBody?.summary ?? "还没有真实学习报告";
  const readError = latestReportQuery.isError && !isEmptyReport ? "学习报告读取失败，请稍后重试。" : "";

  return (
    <PageFrame title="学习报告">
      <div className="student-workspace reports-workspace">
        <section className="student-panel mastery-map" role="region" aria-label="掌握度地图">
          <div className="student-panel-heading">
            <div>
              <h2>知识掌握度</h2>
            </div>
            <ChartLineUp size={24} weight="duotone" aria-hidden="true" />
          </div>
          <label className="report-course-picker">
            <span>课程</span>
            <select aria-label="选择课程" value={effectiveCourseId} onChange={(event) => setSelectedCourseId(event.target.value)}>
              {courses.map((course) => (
                <option key={course.id} value={course.id}>
                  {course.title}
                </option>
              ))}
            </select>
          </label>
          <div className="mastery-list">
            <article>
              <div>
                <strong>薄弱点</strong>
                <span>{reportBody?.mastery_update.weak_count ?? 0}</span>
              </div>
              <div className="mastery-meter" aria-label={`薄弱点 ${reportBody?.mastery_update.weak_count ?? 0}`}>
                <span style={{ width: `${Math.min((reportBody?.mastery_update.weak_count ?? 0) * 20, 100)}%` }} />
              </div>
            </article>
            <article>
              <div>
                <strong>已掌握</strong>
                <span>{reportBody?.mastery_update.mastered_count ?? 0}</span>
              </div>
              <div className="mastery-meter" aria-label={`已掌握 ${reportBody?.mastery_update.mastered_count ?? 0}`}>
                <span style={{ width: `${Math.min((reportBody?.mastery_update.mastered_count ?? 0) * 20, 100)}%` }} />
              </div>
            </article>
          </div>
        </section>

        <section className="student-panel learning-report-panel" role="region" aria-label="学习报告">
          <div className="report-brief">
            <FileText size={24} weight="duotone" aria-hidden="true" />
            <div>
              <strong>{reportTitle}</strong>
              <p>{reportSummary}</p>
            </div>
          </div>
          {readError || localError ? <p className="form-error">{readError || localError}</p> : null}
          <ul className="report-evidence-list">
            {(reportBody?.weakness_list ?? []).map((item) => (
              <li key={`${item.knowledge_point_id}-${item.title}`}>
                <ShieldCheck size={17} weight="duotone" aria-hidden="true" />
                <span>{item.title}</span>
              </li>
            ))}
            {(reportBody?.next_step_suggestions ?? []).map((item) => (
              <li key={item}>
                <Graph size={17} weight="duotone" aria-hidden="true" />
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </section>

        <aside className="student-panel export-panel" role="region" aria-label="生成学习报告">
          <div>
            <h2>生成报告</h2>
            <p>基于真实练习、弱点和掌握度生成，不包含密钥或隐私原文。</p>
          </div>
          <button className="soft-button" type="button" disabled={!canUseCourse || generateMutation.isPending} onClick={() => generateMutation.mutate()}>
            <FileText size={17} aria-hidden="true" />
            <span>生成学习报告</span>
          </button>
          <button className="soft-button" type="button" disabled={!canUseCourse || exportMutation.isPending} onClick={() => exportMutation.mutate()}>
            <DownloadSimple size={17} aria-hidden="true" />
            <span>导出学习档案</span>
          </button>
          {exportMessage ? <p className="inline-feedback inline-feedback-success">{exportMessage}</p> : null}
          {exportError ? <p className="form-error">{exportError}</p> : null}
        </aside>
      </div>
    </PageFrame>
  );
}
